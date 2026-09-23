import json
import time
from django.utils import timezone
from .models import RequestHistory
from .variable_resolver import VariableResolver


def execute_assertions(response, assertions):
    """执行断言验证"""
    results = []
    
    for assertion in assertions:
        result = {
            'name': assertion.get('name', '未命名断言'),
            'type': assertion.get('type'),
            'passed': False,
            'expected': assertion.get('expected'),
            'actual': None,
            'error': None
        }
        
        try:
            assertion_type = assertion.get('type')
            expected = assertion.get('expected')
            actual = None
            passed = False
            
            if assertion_type == 'status_code':
                actual = response.status_code
                passed = actual == expected
                
            elif assertion_type == 'response_time':
                # 响应时间断言在调用方处理
                actual = assertion.get('actual_time')
                passed = actual <= expected if actual else False
                
            elif assertion_type == 'contains':
                text = response.text or ''
                pattern = str(expected)
                actual = text[:200] + '...' if len(text) > 200 else text
                passed = pattern in str(text)
                
            elif assertion_type == 'json_path':
                json_path = assertion.get('json_path', '')
                expected_value = assertion.get('expected')
                actual = None
                passed = False
                
                try:
                    # 检查响应是否为JSON格式
                    content_type = response.headers.get('content-type', '').lower()
                    if 'application/json' not in content_type:
                        raise ValueError(f"响应不是JSON格式，Content-Type: {content_type}")
                    
                    response_json = json.loads(response.text)
                    
                    # 检查JSONPath表达式是否为空
                    if not json_path:
                        raise ValueError("JSON路径表达式不能为空")
                    
                    from jsonpath_ng import parse
                    matches = parse(json_path).find(response_json)
                    actual = matches[0].value if matches else None
                    passed = str(actual) == str(expected_value)
                    
                    # 确保actual值被正确设置到result中
                    result['actual'] = actual
                except json.JSONDecodeError as e:
                    actual = None
                    passed = False
                    result['error'] = f"JSON解析失败: {str(e)}"
                    result['actual'] = actual
                except ImportError as e:
                    actual = None
                    passed = False
                    result['error'] = f"缺少依赖库: {str(e)}，请安装jsonpath-ng"
                    result['actual'] = actual
                except Exception as e:
                    actual = None
                    passed = False
                    result['error'] = f"执行错误: {str(e)}"
                    result['actual'] = actual
                    
            elif assertion_type == 'header':
                header_name = assertion.get('header_name', '')
                expected_value = assertion.get('expected_value')
                actual = response.headers.get(header_name)
                passed = actual == expected_value
                
            elif assertion_type == 'equals':
                actual = response.text.strip()
                passed = actual == str(expected).strip()
            
            # 确保在所有情况下都设置actual值
            if 'actual' not in result or result['actual'] is None:
                result['actual'] = actual
            result['passed'] = passed
            
        except Exception as e:
            result['error'] = str(e)
            result['passed'] = False
        
        results.append(result)
    
    return results


def extract_response_variables(response, rules):
    """
    从响应中提取变量（响应变量提取规则）

    rules 格式: [{"name": "token", "source": "body|header", "expression": "$.data.token"}]
    - source=body: expression 为 JSONPath（支持 $.data.token 或 data.token 点路径）
    - source=header: expression 为响应头名称

    Returns:
        {变量名: 值}
    """
    import json as _json

    extracted = {}
    if not rules:
        return extracted

    # 解析响应体（JSON）
    body = None
    try:
        body = response.json()
    except Exception:
        try:
            body = _json.loads(response.text)
        except Exception:
            body = None

    for rule in rules:
        if not rule or not isinstance(rule, dict):
            continue
        name = str(rule.get('name', '')).strip()
        expression = str(rule.get('expression', '')).strip()
        source = str(rule.get('source', 'body')).strip().lower()
        if not name or not expression:
            continue

        try:
            value = None
            if source == 'header':
                value = response.headers.get(expression)
            else:
                value = _extract_jsonpath_value(body, expression)

            if value is not None:
                extracted[name] = value
        except Exception as e:
            print(f"[WARNING] 变量提取失败: {name} - {str(e)}")

    return extracted


def _extract_jsonpath_value(data, expression):
    """从 JSON 数据中按 JSONPath 或点路径提取值"""
    if data is None:
        return None

    expr = expression.strip()
    if expr.startswith('$'):
        # JSONPath 语法，如 $.data.token / $['data']['token']
        try:
            from jsonpath_ng import parse
            matches = parse(expr).find(data)
            if matches:
                return matches[0].value
        except Exception:
            pass
        # 去掉 $ 前缀后按点路径再试
        path = expr[1:].lstrip('.')
        if path.startswith('['):
            path = path.replace("['", '.').replace("']", '').replace('["', '.').replace('"]', '')
            path = path.lstrip('.')
    else:
        path = expr

    # 简单点路径解析
    current = data
    for part in path.split('.'):
        part = part.strip()
        if part == '':
            continue
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            if idx < len(current):
                current = current[idx]
            else:
                return None
        else:
            return None
    return current


def apply_extract_rules(response, rules, environment, variables):
    """
    执行变量提取并写入环境变量与本地变量字典

    Returns:
        {变量名: 值} 提取结果
    """
    extracted = extract_response_variables(response, rules)
    if not extracted:
        return {}

    if variables is not None:
        variables.update(extracted)

    if environment is not None:
        env_vars = dict(environment.variables or {})
        env_vars.update(extracted)
        environment.variables = env_vars
        environment.save(update_fields=['variables'])

    return extracted



TOKEN_FIELD_KEYS = ('token', 'access_token', 'accessToken', 'access', 'jwt', 'id_token', 'refresh', 'refresh_token')


def auto_extract_token(response, variables):
    """自动识别响应中的鉴权 token 字段并写入共享变量（登录步骤自动继承）

    无需手动配置 extract_rules：登录接口的响应中若包含 token/access 等字段，
    会自动提取并写入 variables，供后续步骤通过 {{token}} / {{access}} 等引用。
    仅在变量尚未存在时写入，避免覆盖已提取或环境变量中的值。
    """
    if not isinstance(variables, dict):
        return {}

    data = None
    try:
        data = response.json()
    except Exception:
        try:
            data = json.loads(response.text or '')
        except Exception:
            data = None

    if not isinstance(data, dict):
        return {}

    extracted = {}

    def _collect(obj):
        if not isinstance(obj, dict):
            return
        for key in TOKEN_FIELD_KEYS:
            if key in extracted:
                continue
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                extracted[key] = value

    _collect(data)
    for sub_key in ('data', 'result', 'results'):
        sub = data.get(sub_key)
        if isinstance(sub, dict):
            _collect(sub)
        elif isinstance(sub, list):
            for item in sub:
                if isinstance(item, dict):
                    _collect(item)
                    break

    if not extracted:
        return {}

    # 规范化：优先使用 token 字段，否则用 access_token/access 作为 {{token}} 别名
    if 'token' not in extracted:
        for key in ('access_token', 'accessToken', 'access', 'jwt', 'id_token'):
            if key in extracted:
                extracted['token'] = extracted[key]
                break

    for key, value in extracted.items():
        if key not in variables:
            variables[key] = value

    return extracted


def execute_test_suite(test_suite, environment, executed_by):
    """执行测试套件并返回结果"""
    from .models import TestExecution, RequestHistory
    import requests
    import time
    
    try:
        # 创建变量解析器
        resolver = VariableResolver()
        
        # 创建执行记录
        execution = TestExecution.objects.create(
            test_suite=test_suite,
            status='RUNNING',
            start_time=timezone.now(),
            executed_by=executed_by
        )
        
        # 获取套件中的请求
        suite_requests = test_suite.testsuiterequest_set.filter(enabled=True).order_by('order')
        
        execution.total_requests = suite_requests.count()
        execution.save()
        
        results = []
        passed_count = 0
        failed_count = 0
        # 初始化共享变量上下文（环境变量 + 步骤间提取的变量，供后续步骤 {{变量}} 引用）
        variables = {}
        if environment:
            variables.update(environment.variables)

        # 执行每个请求
        for suite_request in suite_requests:
            api_request = suite_request.request

            try:
                # 使用共享变量上下文（登录步骤提取的 token 会在此累积，供后续步骤继承）

                # 替换URL中的变量（先解析动态函数，再替换环境变量）
                url = _replace_variables(api_request.url, variables)
                url = resolver.resolve(url)
                
                # 准备请求头
                headers = {}
                if isinstance(api_request.headers, list):
                    for header_item in api_request.headers:
                        if header_item.get('enabled', True) and header_item.get('key'):
                            key = header_item['key']
                            value = _replace_variables(str(header_item.get('value', '')), variables)
                            value = resolver.resolve(value)
                            headers[key] = value
                else:
                    headers = api_request.headers.copy()
                    for key, value in headers.items():
                        headers[key] = _replace_variables(str(value), variables)
                        headers[key] = resolver.resolve(headers[key])
                
                # 准备请求参数
                params = api_request.params.copy() if api_request.params else {}
                for key, value in params.items():
                    params[key] = _replace_variables(str(value), variables)
                    params[key] = resolver.resolve(params[key])
                
                # 准备请求体
                body_data = None
                if api_request.body and api_request.method in ['POST', 'PUT', 'PATCH']:
                    if api_request.body.get('type') == 'json':
                        body_data = api_request.body.get('data', {})
                        body_data = _replace_variables_in_dict(body_data, variables)
                        body_data = _resolve_variables_in_dict(body_data, resolver)
                
                # 执行请求
                start_time = time.time()
                response = requests.request(
                    method=api_request.method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=body_data,
                    timeout=30
                )
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                # 执行断言验证
                assertions = api_request.assertions or []
                for assertion in assertions:
                    if assertion.get('type') == 'response_time':
                        assertion['actual_time'] = response_time
                
                assertions_results = execute_assertions(response, assertions)

                # 响应变量提取：自动写入环境变量与本地上下文，供后续请求 {{变量}} 引用
                # 登录步骤自动提取 token（无需手动配置 extract_rules）
                extracted_vars = auto_extract_token(response, variables)
                if api_request.extract_rules:
                    explicit_vars = apply_extract_rules(response, api_request.extract_rules, environment, variables)
                    extracted_vars.update(explicit_vars)
                
                # 检查所有断言是否通过
                passed = True
                error_message = ''
                
                # 检查套件请求的断言
                for assertion in suite_request.assertions:
                    if assertion.get('type') == 'status_code':
                        expected = assertion.get('value')
                        if response.status_code != expected:
                            passed = False
                            error_message = f'状态码断言失败: 期望 {expected}, 实际 {response.status_code}'
                            break
                
                # 检查接口自身的断言
                if passed and assertions_results:
                    for assertion_result in assertions_results:
                        if not assertion_result.get('passed', True):
                            passed = False
                            error_message = f"断言失败: {assertion_result.get('name', '未命名断言')} - {assertion_result.get('error', '断言不通过')}"
                            break
                
                if passed:
                    passed_count += 1
                else:
                    failed_count += 1
                
                results.append({
                    'name': api_request.name,
                    'method': api_request.method,
                    'url': url,
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'passed': passed,
                    'error': error_message,
                    'assertions_results': assertions_results,
                    'extracted_variables': extracted_vars,
                    'request_data': {
                        'url': url,
                        'method': api_request.method,
                        'headers': headers,
                        'params': params,
                        'body': body_data
                    },
                    'response_data': {
                        'headers': dict(response.headers),
                        'body': response.text,
                        'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
                    }
                })
                
                # 保存请求历史
                RequestHistory.objects.create(
                    request=api_request,
                    environment=environment,
                    request_data={
                        'url': url,
                        'method': api_request.method,
                        'headers': headers,
                        '极速版params': params,
                        'body': body_data
                    },
                    response_data={
                        'headers': dict(response.headers),
                        'body': response.text,
                        'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
                    },
                    status_code=response.status_code,
                    response_time=response_time,
                    assertions_results=assertions_results,
                    executed_by=executed_by
                )
                
            except Exception as e:
                failed_count += 1
                results.append({
                    'name': api_request.name,
                    'method': api_request.method,
                    'url': api_request.url,
                    'passed': False,
                    'error': str(e)
                })
        
        # 更新执行结果
        execution.end_time = timezone.now()
        execution.passed_requests = passed_count
        execution.failed_requests = failed_count
        execution.status = 'COMPLETED' if failed_count == 0 else 'FAILED'
        execution.results = results
        execution.save()
        
        return {
            'success': True,
            'execution_id': execution.id,
            'passed_count': passed_count,
            'failed_count': failed_count,
            'total_count': execution.total_requests,
            'results': results
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def execute_api_request(api_request, environment, executed_by):
    """执行单个API请求并返回结果"""
    import requests
    import time
    
    try:
        # 创建变量解析器
        resolver = VariableResolver()
        
        # 解析环境变量
        variables = {}
        if environment:
            variables.update(environment.variables)
        
        # 替换URL中的变量（先解析动态函数，再替换环境变量）
        url = _replace_variables(api_request.url, variables)
        url = resolver.resolve(url)
        
        # 准备请求头
        headers = {}
        if isinstance(api_request.headers, list):
            for header_item in api_request.headers:
                if header_item.get('enabled', True) and header_item.get('key'):
                    key = header_item['key']
                    value = _replace_variables(str(header_item.get('value', '')), variables)
                    value = resolver.resolve(value)
                    headers[key] = value
        else:
            headers = api_request.headers.copy()
            for key, value in headers.items():
                headers[key] = _replace_variables(str(value), variables)
                headers[key] = resolver.resolve(headers[key])
        
        # 准备请求参数
        params = api_request.params.copy() if api_request.params else {}
        for key, value in params.items():
            params[key] = _replace_variables(str(value), variables)
            params[key] = resolver.resolve(params[key])
        
        # 准备请求体
        body_data = None
        if api_request.body and api_request.method in ['POST', 'PUT', 'PATCH']:
            if api_request.body.get('type') == 'json':
                body_data = api_request.body.get('data', {})
                body_data = _replace_variables_in_dict(body_data, variables)
                body_data = _resolve_variables_in_dict(body_data, resolver)
        
        # 执行请求
        start_time = time.time()
        response = requests.request(
            method=api_request.method,
            url=url,
            headers=headers,
            params=params,
            json=body_data,
            timeout=30
        )
        end_time = time.time()
        response_time = (end_time - start_time) * 1000
        
        # 执行断言验证
        assertions = api_request.assertions or []
        for assertion in assertions:
            if assertion.get('type') == 'response_time':
                assertion['actual_time'] = response_time
        
        assertions_results = execute_assertions(response, assertions)

        # 响应变量提取：自动写入环境变量，供后续请求 {{变量}} 引用
        extracted_vars = {}
        if api_request.extract_rules:
            extracted_vars = apply_extract_rules(response, api_request.extract_rules, environment, variables)

        # 保存请求历史
        history = RequestHistory.objects.create(
            request=api_request,
            environment=environment,
            request_data={
                'url': url,
                'method': api_request.method,
                'headers': headers,
                'params': params,
                'body': body_data
            },
            response_data={
                'headers': dict(response.headers),
                'body': response.text,
                'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
            },
            status_code=response.status_code,
            response_time=response_time,
            assertions_results=assertions_results,
            executed_by=executed_by
        )
        
        return {
            'success': True,
            'history_id': history.id,
            'status_code': response.status_code,
            'response_time': response_time,
            'assertions_results': assertions_results,
            'extracted_variables': extracted_vars,
            'response_data': {
                'headers': dict(response.headers),
                'body': response.text,
                'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
            }
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def _replace_variables(text, variables):
    """替换文本中的变量"""
    if not isinstance(text, str):
        return text
    
    result = text
    for key, value in (variables or {}).items():
        if isinstance(value, dict):
            replacement = str(value.get('currentValue', '') or value.get('initialValue', ''))
        else:
            replacement = str(value) if value is not None else ''
        result = result.replace(f'{{{{{key}}}}}', replacement)
    return result

def _replace_variables_in_dict(data, variables):
    """递归替换字典中的变量"""
    if isinstance(data, dict):
        return {k: _replace_variables_in_dict(v, variables) for k, v in data.items()}
    elif isinstance(data, list):
        return [_replace_variables_in_dict(item, variables) for item in data]
    elif isinstance(data, str):
        return _replace_variables(data, variables)
    else:
        return data

def _resolve_variables_in_dict(data, resolver):
    """递归解析字典中的动态函数占位符"""
    if isinstance(data, dict):
        return {k: _resolve_variables_in_dict(v, resolver) for k, v in data.items()}
    elif isinstance(data, list):
        return [_resolve_variables_in_dict(item, resolver) for item in data]
    elif isinstance(data, str):
        return resolver.resolve(data)
    else:
        return data
