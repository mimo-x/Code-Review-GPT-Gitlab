from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# 创建路由器并注册视图集
router = DefaultRouter()
router.register(r'llm-configs', views.LLMConfigViewSet, basename='llm-config')
router.register(r'gitlab-configs', views.GitLabConfigViewSet, basename='gitlab-config')
router.register(r'notification-configs', views.NotificationConfigViewSet, basename='notification-config')
router.register(r'configs', views.ConfigViewSet, basename='config')
router.register(r'notification-channels', views.NotificationChannelViewSet, basename='notification-channel')
router.register(r'webhook-event-rules', views.WebhookEventRuleViewSet, basename='webhook-event-rule')

# API URL配置
urlpatterns = [
    path('', include(router.urls)),
]
