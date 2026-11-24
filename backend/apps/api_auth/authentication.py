"""DRF 认证：校验登录接口下发的 auth_token Cookie。"""
from dataclasses import dataclass

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
    """Cookie 会随同站请求自动携带，写操作必须带上本站前端才会发送的请求头。

    普通表单无法设置自定义请求头；脚本跨域设置时浏览器会先发起 CORS 预检，
    不在白名单中的来源会被拦截。这个检查不依赖 Origin 或 Host，经过反向代理也能正常工作。
    """
    if request.method in SAFE_METHODS:
        return
    if request.META.get('HTTP_X_REQUESTED_WITH') != 'XMLHttpRequest':
        raise exceptions.PermissionDenied('拒绝跨站请求')
