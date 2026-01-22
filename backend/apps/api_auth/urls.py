"""
认证相关 URL 配置
"""
from django.urls import path
from . import views

urlpatterns = [
    path('login', views.login, name='auth_login'),
    path('logout', views.logout, name='auth_logout'),
    path('check', views.check_auth, name='auth_check'),
]
