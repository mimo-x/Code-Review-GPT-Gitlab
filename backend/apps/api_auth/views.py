"""
认证相关视图
"""
import os
import secrets
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from utils.redis_client import redis_client


# Token 过期时间（秒）
TOKEN_EXPIRE_SECONDS = int(os.environ.get('TOKEN_EXPIRE_SECONDS', 604800))  # 默认 7 天


@csrf_exempt
@require_http_methods(["POST"])
def login(request):
    """
    登录接口
    从环境变量读取默认账号密码进行验证
    使用 HttpOnly Cookie 存储 token
    """
    try:
        # 解析请求数据
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        # 从环境变量读取配置的账号密码
        default_username = os.environ.get('DEFAULT_USERNAME', '')
        default_password = os.environ.get('DEFAULT_PASSWORD', '')

        if not default_username or not default_password:
            return JsonResponse({
                'success': False,
                'message': '服务端未配置登录凭据'
            }, status=500)

        # 验证账号密码
        if username == default_username and password == default_password:
            # 生成 token（使用 secrets 生成安全的随机 token）
            token = secrets.token_urlsafe(32)

            # 将 token 存储到 Redis，设置过期时间
            if not redis_client.set_token(token, username, TOKEN_EXPIRE_SECONDS):
                return JsonResponse({
                    'success': False,
                    'message': 'Token 存储失败'
                }, status=503)

            # 创建响应
            response = JsonResponse({
                'success': True,
                'message': '登录成功',
                'data': {
                    'username': username,
                    'expire_days': TOKEN_EXPIRE_SECONDS // 86400
                }
            })

            # 设置 HttpOnly Cookie
            response.set_cookie(
                key='auth_token',
                value=token,
                max_age=TOKEN_EXPIRE_SECONDS,  # Cookie 过期时间
                httponly=True,  # 防止 JavaScript 访问
                secure=False,  # 生产环境应设置为 True（需要 HTTPS）
                samesite='Lax'  # 防止 CSRF 攻击
            )

            return response
        else:
            return JsonResponse({
                'success': False,
                'message': '用户名或密码错误'
            }, status=401)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': '请求数据格式错误'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'登录失败: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def logout(request):
    """
    登出接口
    删除 Redis 中的 token 并清除 Cookie
    """
    try:
        # 从 Cookie 获取 token
        token = request.COOKIES.get('auth_token')

        if token:
            # 从 Redis 删除 token
            redis_client.delete_token(token)

        # 创建响应
        response = JsonResponse({
            'success': True,
            'message': '登出成功'
        })

        # 删除 Cookie
        response.delete_cookie('auth_token')

        return response
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'登出失败: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def check_auth(request):
    """
    检查认证状态接口
    从 Cookie 读取 token 并验证 Redis 中是否存在
    """
    try:
        # 从 Cookie 获取 token
        token = request.COOKIES.get('auth_token')

        if not token:
            return JsonResponse({
                'success': False,
                'message': '未提供认证信息'
            }, status=401)

        # 从 Redis 验证 token
        username = redis_client.get_token(token)

        if username:
            return JsonResponse({
                'success': True,
                'message': '已登录',
                'data': {
                    'username': username
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Token 已过期或无效'
            }, status=401)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'验证失败: {str(e)}'
        }, status=500)

