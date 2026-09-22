# -*- coding: utf-8 -*-
"""APP设备管理视图"""
import subprocess
import base64
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
import logging

from .test_case_views import AppPagination
from ..models import AppDevice
from ..serializers import AppDeviceSerializer
from ..managers.device_manager import DeviceManager

logger = logging.getLogger(__name__)


def get_adb_path() -> str:
    """
    获取 ADB 路径：优先使用数据库配置，否则使用默认值 'adb'
    """
    try:
        from ..models import AppTestConfig
        config = AppTestConfig.objects.first()
        return config.adb_path if config else 'adb'
    except Exception as e:
        logger.warning(f"获取 ADB 配置失败，使用默认路径: {e}")
        return 'adb'


class AppDeviceViewSet(viewsets.ModelViewSet):
    """APP设备管理 ViewSet"""
    queryset = AppDevice.objects.all()
    serializer_class = AppDeviceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AppPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'connection_type']
    search_fields = ['device_id', 'name']
    
    @action(detail=False, methods=['get'])
    def discover(self, request):
        """发现ADB设备"""
        try:
            adb_path = get_adb_path()
            logger.info(f"使用 ADB 路径: {adb_path}")
            
            manager = DeviceManager(adb_path=adb_path)
            devices_info = manager.list_devices()
            
            # 更新或创建设备记录
            db_devices = []
            for device_info in devices_info:
                # 判断连接类型和 IP 地址
                device_id = device_info['device_id']
                if ':' in device_id:
                    # 远程设备（IP:端口格式）
                    connection_type = 'remote_emulator'
                    ip_address = device_info.get('ip_address') or ''
                elif device_id.startswith('emulator-'):
                    # 本地模拟器 - 使用 localhost
                    connection_type = 'emulator'
                    ip_address = '127.0.0.1'
                else:
                    # USB 连接的真机
                    connection_type = 'usb'
                    ip_address = device_info.get('ip_address') or ''
                
                device, created = AppDevice.objects.update_or_create(
                    device_id=device_info['device_id'],
                    defaults={
                        'name': device_info.get('name') or '',
                        'status': device_info.get('status') or 'offline',
                        'android_version': device_info.get('android_version') or '',
                        'ip_address': ip_address,
                        'port': device_info.get('port') or 5555,
                        'connection_type': connection_type,
                    }
                )
                db_devices.append(device)
            
            # 返回序列化后的数据库对象
            return Response({
                'success': True,
                'message': f'发现 {len(db_devices)} 个设备',
                'devices': AppDeviceSerializer(db_devices, many=True).data
            })
        except Exception as e:
            logger.error(f"发现设备失败: {str(e)}")
            return Response({
                'success': False,
                'message': f'发现设备失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """锁定设备"""
        device = self.get_object()
        
        if device.status == 'locked':
            return Response({
                'success': False,
                'message': '设备已被锁定'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        device.lock(request.user)
        
        return Response({
            'success': True,
            'message': '设备锁定成功',
            'device': AppDeviceSerializer(device).data
        })
    
    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        """释放设备"""
        device = self.get_object()
        
        if device.locked_by and device.locked_by != request.user:
            return Response({
                'success': False,
                'message': '无权释放他人锁定的设备'
            }, status=status.HTTP_403_FORBIDDEN)
        
        device.unlock()
        
        return Response({
            'success': True,
            'message': '设备释放成功',
            'device': AppDeviceSerializer(device).data
        })
    
    @action(detail=True, methods=['post'])
    def disconnect(self, request, pk=None):
        """断开远程设备连接"""
        device = self.get_object()
        
        # 只有远程设备可以断开
        if device.connection_type not in ['remote', 'remote_emulator']:
            return Response({
                'success': False,
                'message': '只能断开远程设备的连接'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            adb_path = get_adb_path()
            manager = DeviceManager(adb_path=adb_path)
            success = manager.disconnect_device(f'{device.ip_address}:{device.port}')
            
            if not success:
                return Response({
                    'success': False,
                    'message': '断开设备失败'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 更新设备状态为离线
            device.status = 'offline'
            device.save()
            
            return Response({
                'success': True,
                'message': f'设备 {device.name or device.device_id} 已断开连接',
                'device': AppDeviceSerializer(device).data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'断开设备失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def connect(self, request):
        """连接远程设备"""
        try:
            ip_address = request.data.get('ip_address')
            port = request.data.get('port', 5555)
            
            if not ip_address:
                return Response({
                    'success': False,
                    'message': '请提供设备IP地址'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            adb_path = get_adb_path()
            manager = DeviceManager(adb_path=adb_path)
            device_info = manager.connect_device(ip_address, port)
            
            # 创建或更新设备记录
            device, created = AppDevice.objects.update_or_create(
                device_id=device_info['device_id'],
                defaults={
                    'name': device_info.get('name') or '',
                    'status': 'online',
                    'android_version': device_info.get('android_version', ''),
                    'ip_address': ip_address,
                    'port': port,
                    'connection_type': 'remote_emulator',
                }
            )
            
            return Response({
                'success': True,
                'message': '设备连接成功',
                'device': AppDeviceSerializer(device).data
            })
        except Exception as e:
            logger.error(f"连接设备失败: {str(e)}")
            return Response({
                'success': False,
                'message': f'连接设备失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], url_path='screenshot')
    def screenshot(self, request, pk=None):
        """
        获取设备实时截图
        
        功能：
        1. 使用 adb screencap 获取设备截图
        2. 转换为 Base64
        3. 返回 data URL 格式
        """
        device = self.get_object()
        
        if device.status == 'offline':
            return Response({
                'code': 400,
                'msg': '设备离线，无法截图',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            adb_path = get_adb_path()
            
            # 使用 adb screencap 命令截图
            result = subprocess.run(
                [adb_path, '-s', device.device_id, 'exec-out', 'screencap', '-p'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=10
            )
            
            if not result.stdout:
                return Response({
                    'code': 500,
                    'msg': '截图失败：无返回数据',
                    'success': False
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 转换为 Base64
            image_base64 = base64.b64encode(result.stdout).decode('utf-8')
            
            logger.info(f"设备 {device.device_id} 截图成功")
            
            return Response({
                'code': 0,
                'msg': '截图成功',
                'success': True,
                'data': {
                    'filename': f"device_{device.id}_{int(timezone.now().timestamp())}.png",
                    'content': f"data:image/png;base64,{image_base64}",
                    'device_id': device.device_id,
                    'timestamp': int(timezone.now().timestamp())
                }
            })
            
        except subprocess.TimeoutExpired:
            logger.error(f"设备 {device.device_id} 截图超时")
            return Response({
                'code': 500,
                'msg': '截图超时，请检查设备连接',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"设备 {device.device_id} 截图失败: {str(e)}")
            return Response({
                'code': 500,
                'msg': f'截图失败: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='action')
    def device_action(self, request, pk=None):
        """
        执行设备操作（脚本录制/回放用）

        支持的动作类型（params 为动作参数）:
        - tap:        点击坐标      {x, y}
        - long_press: 长按坐标      {x, y, duration(秒, 默认2)}
        - swipe:      滑动          {x1, y1, x2, y2, duration(秒, 默认0.5)}
        - text:       输入文本      {text}
        - keyevent:   按键          {keycode} 如 4=返回, 3=Home, 66=回车
        - sleep:      等待          {seconds}
        """
        device = self.get_object()

        if device.status == 'offline':
            return Response({
                'code': 400,
                'msg': '设备离线，无法执行操作',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        action_type = request.data.get('action', '').strip().lower()
        params = request.data.get('params') or {}

        if not action_type:
            return Response({
                'code': 400,
                'msg': '缺少 action 参数',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        adb_path = get_adb_path()
        serial = device.device_id

        try:
            if action_type == 'tap':
                x = int(params.get('x'))
                y = int(params.get('y'))
                if x is None or y is None:
                    raise ValueError('tap 需要 x, y 参数')
                result = subprocess.run(
                    [adb_path, '-s', serial, 'shell', 'input', 'tap', str(x), str(y)],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode != 0:
                    raise RuntimeError(result.stderr or 'adb tap 失败')
                message = f"点击 ({x}, {y})"

            elif action_type == 'long_press':
                x = int(params.get('x'))
                y = int(params.get('y'))
                if x is None or y is None:
                    raise ValueError('long_press 需要 x, y 参数')
                duration = float(params.get('duration', 2.0))
                # adb 无直接长按命令，使用同点 swipe 模拟
                duration_ms = int(duration * 1000)
                result = subprocess.run(
                    [adb_path, '-s', serial, 'shell', 'input', 'swipe',
                     str(x), str(y), str(x), str(y), str(duration_ms)],
                    capture_output=True, text=True, timeout=20
                )
                if result.returncode != 0:
                    raise RuntimeError(result.stderr or 'adb 长按失败')
                message = f"长按 ({x}, {y}) {duration}s"

            elif action_type == 'swipe':
                x1 = int(params.get('x1'))
                y1 = int(params.get('y1'))
                x2 = int(params.get('x2'))
                y2 = int(params.get('y2'))
                if None in (x1, y1, x2, y2):
                    raise ValueError('swipe 需要 x1, y1, x2, y2 参数')
                duration = float(params.get('duration', 0.5))
                duration_ms = int(duration * 1000)
                result = subprocess.run(
                    [adb_path, '-s', serial, 'shell', 'input', 'swipe',
                     str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
                    capture_output=True, text=True, timeout=20
                )
                if result.returncode != 0:
                    raise RuntimeError(result.stderr or 'adb 滑动失败')
                message = f"滑动 ({x1},{y1})->({x2},{y2})"

            elif action_type == 'text':
                text = str(params.get('text', ''))
                if not text:
                    raise ValueError('text 不能为空')
                # adb shell input text 的空格需转义为 %s，避免被拆分为多个参数
                escaped = text.replace(' ', '%s')
                result = subprocess.run(
                    [adb_path, '-s', serial, 'shell', 'input', 'text', escaped],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode != 0:
                    raise RuntimeError(result.stderr or 'adb 输入文本失败')
                message = f"输入文本: {text}"

            elif action_type == 'keyevent':
                keycode = int(params.get('keycode'))
                if keycode is None:
                    raise ValueError('keyevent 需要 keycode 参数')
                result = subprocess.run(
                    [adb_path, '-s', serial, 'shell', 'input', 'keyevent', str(keycode)],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode != 0:
                    raise RuntimeError(result.stderr or 'adb 按键失败')
                message = f"按键 keycode={keycode}"

            elif action_type == 'sleep':
                seconds = float(params.get('seconds', 1.0))
                import time as _time
                _time.sleep(seconds)
                message = f"等待 {seconds}s"

            else:
                return Response({
                    'code': 400,
                    'msg': f'不支持的动作类型: {action_type}',
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"设备 {serial} 执行操作成功: {message}")
            return Response({
                'code': 0,
                'msg': '操作执行成功',
                'success': True,
                'data': {'action': action_type, 'message': message}
            })

        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"设备 {serial} 操作参数错误: {e}")
            return Response({
                'code': 400,
                'msg': f'参数错误: {str(e)}',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        except subprocess.TimeoutExpired:
            return Response({
                'code': 500,
                'msg': '设备操作超时',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"设备 {serial} 操作失败: {str(e)}")
            return Response({
                'code': 500,
                'msg': f'操作失败: {str(e)}',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
