"""DRF 认证：校验登录接口下发的 auth_token Cookie。"""
from dataclasses import dataclass

from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import SAFE_METHODS

from utils.redis_client import redis_client


@dataclass(frozen=True)
class ApiUser:
    """已登录的后台用户。账号来自环境变量，不对应 Django User。"""

    username: str
    is_authenticated = True


class CookieTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = request.COOKIES.get('auth_token')
        username = redis_client.get_token(token) if token else None
        if not username:
            return None
        _reject_cross_site_write(request)
        return ApiUser(username), token

    def authenticate_header(self, request):
        # 提供该响应头后，DRF 对未登录请求返回 401，前端据此跳转登录页
        return 'Cookie'


def _reject_cross_site_write(request) -> None:
    """Cookie 会随同站请求自动携带，写操作必须来自本站或 CORS 白名单。"""
    if request.method in SAFE_METHODS:
        return
    if request.META.get('HTTP_SEC_FETCH_SITE') not in {'cross-site', 'same-site'}:
        return
    if request.META.get('HTTP_ORIGIN') not in settings.CORS_ALLOWED_ORIGINS:
        raise exceptions.PermissionDenied('拒绝跨站请求')
