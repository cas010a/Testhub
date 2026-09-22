from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import render
import requests
from .models import AssistantSession, AssistantMessage, ChatMessage, DifyConfig
from .serializers import (
    AssistantSessionSerializer, 
    AssistantSessionCreateSerializer,
    AssistantMessageSerializer,
    ChatMessageSerializer
)


class AssistantSessionViewSet(viewsets.ModelViewSet):
    """智能助手会话视图集"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AssistantSessionCreateSerializer
        return AssistantSessionSerializer
    
    def get_queryset(self):
        return AssistantSession.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def add_message(self, request, pk=None):
        """添加消息到会话"""
        session = self.get_object()
        serializer = AssistantMessageSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(session=session)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """获取会话的聊天消息"""
        session = self.get_object()
        messages = session.chat_messages.all()
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)


class ChatViewSet(viewsets.ViewSet):
    """聊天功能ViewSet"""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def send_message(self, request):
        """发送消息到Dify API"""
        session_id = request.data.get('session_id')
        message = request.data.get('message')
        
        if not session_id or not message:
            return Response(
                {'error': 'session_id和message都是必填项'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取会话
        try:
            session = AssistantSession.objects.get(
                session_id=session_id,
                user=request.user
            )
        except AssistantSession.DoesNotExist:
            return Response(
                {'error': '会话不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 解析AI配置：优先使用已配置的Dify，其次使用OpenAI兼容的AI模型
        dify_config = DifyConfig.get_active_config()
        model_config = None
        if not dify_config:
            try:
                from apps.requirement_analysis.models import AIModelConfig
                model_config = AIModelConfig.objects.filter(is_active=True).first()
            except Exception:
                model_config = None
        if not dify_config and not model_config:
            return Response(
                {'error': '未配置AI模型或Dify API，请先在配置中心配置'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 保存用户消息
        user_message = ChatMessage.objects.create(
            session=session,
            role='user',
            content=message,
            conversation_id=session.conversation_id
        )
        
        try:
            if dify_config:
                answer, conversation_id = self._call_dify(session, message, dify_config)
            else:
                answer, conversation_id = self._call_openai_compatible(session, message, model_config)
        except requests.exceptions.Timeout:
            return Response({
                'error': 'API请求超时'
            }, status=status.HTTP_408_REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as e:
            return Response({
                'error': f'API请求失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 更新会话的conversation_id
        if conversation_id and not session.conversation_id:
            session.conversation_id = conversation_id
            session.save()

        # 保存助手回复
        assistant_message = ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=answer,
            conversation_id=conversation_id
        )

        return Response({
            'user_message': ChatMessageSerializer(user_message).data,
            'assistant_message': ChatMessageSerializer(assistant_message).data,
            'conversation_id': conversation_id
        })


    def _call_dify(self, session, message, dify_config):
        """调用Dify API（阻塞模式）"""
        headers = {
            'Authorization': f'Bearer {dify_config.api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'inputs': {},
            'query': message,
            'user': str(self.request.user.id),
            'response_mode': 'blocking'
        }
        if session.conversation_id:
            payload['conversation_id'] = session.conversation_id

        api_url = dify_config.api_url.rstrip('/')
        response = requests.post(
            f'{api_url}/chat-messages',
            headers=headers,
            json=payload,
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('answer', ''), data.get('conversation_id')
        raise requests.exceptions.RequestException(
            f'Dify API错误: {response.status_code} - {response.text[:500]}'
        )

    def _call_openai_compatible(self, session, message, model_config):
        """调用OpenAI兼容的AI模型接口（阿里云百炼等）"""
        # 从会话历史构建上下文（已包含刚保存的用户消息）
        history = list(session.chat_messages.order_by('created_at')[:20])
        messages = [
            {'role': m.role, 'content': m.content}
            for m in history
        ]

        headers = {
            'Authorization': f'Bearer {model_config.api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': model_config.model_name,
            'messages': messages,
            'max_tokens': model_config.max_tokens or 2048,
            'temperature': model_config.temperature,
            'top_p': model_config.top_p
        }
        # 移除为None的参数，避免接口报错
        payload = {k: v for k, v in payload.items() if v is not None}

        api_url = (model_config.base_url or '').rstrip('/')
        response = requests.post(
            f'{api_url}/chat/completions',
            headers=headers,
            json=payload,
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            try:
                answer = data['choices'][0]['message']['content']
            except (KeyError, IndexError, TypeError):
                raise requests.exceptions.RequestException('AI接口返回格式异常')
            # OpenAI兼容接口无conversation_id，上下文由消息历史维持
            return answer, None
        raise requests.exceptions.RequestException(
            f'AI接口错误: {response.status_code} - {response.text[:500]}'
        )


def assistant_view(request):
    """智能助手页面视图 - 用于iframe内嵌"""
    return render(request, 'assistant/assistant.html')
