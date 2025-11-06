from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from .models import LLMConfig, GitLabConfig, NotificationConfig, NotificationChannel
from .serializers import (
    LLMConfigSerializer,
    GitLabConfigSerializer,
    NotificationConfigSerializer,
    NotificationChannelSerializer,
    ConfigSummarySerializer
)


class LLMConfigViewSet(viewsets.ModelViewSet):
    """LLM配置管理API"""
    serializer_class = LLMConfigSerializer
    permission_classes = [AllowAny]  # 临时允许所有访问，生产环境应该使用IsAuthenticated

    def get_queryset(self):
        return LLMConfig.objects.all()

    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取当前激活的LLM配置"""
        config = LLMConfig.objects.filter(is_active=True).first()
        if config:
            serializer = self.get_serializer(config)
            return Response(serializer.data)
        return Response({'error': 'No active LLM config found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活指定的LLM配置"""
        config = self.get_object()
        # 先禁用所有其他配置
        LLMConfig.objects.filter(is_active=True).update(is_active=False)
        # 激活当前配置
        config.is_active = True
        config.save()
        return Response({'message': 'LLM config activated successfully'})


class GitLabConfigViewSet(viewsets.ModelViewSet):
    """GitLab配置管理API"""
    serializer_class = GitLabConfigSerializer
    permission_classes = [AllowAny]  # 临时允许所有访问，生产环境应该使用IsAuthenticated

    def get_queryset(self):
        return GitLabConfig.objects.all()

    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取当前激活的GitLab配置"""
        config = GitLabConfig.objects.filter(is_active=True).first()
        if config:
            serializer = self.get_serializer(config)
            return Response(serializer.data)
        return Response({'error': 'No active GitLab config found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活指定的GitLab配置"""
        config = self.get_object()
        # 先禁用所有其他配置
        GitLabConfig.objects.filter(is_active=True).update(is_active=False)
        # 激活当前配置
        config.is_active = True
        config.save()
        return Response({'message': 'GitLab config activated successfully'})


class NotificationConfigViewSet(viewsets.ModelViewSet):
    """通知配置管理API"""
    serializer_class = NotificationConfigSerializer
    permission_classes = [AllowAny]  # 临时允许所有访问，生产环境应该使用IsAuthenticated

    def get_queryset(self):
        return NotificationConfig.objects.all()

    def create(self, request, *args, **kwargs):
        """创建通知配置，确保同一类型的配置唯一性"""
        notification_type = request.data.get('notification_type')
        if notification_type:
            # 检查是否已存在相同类型的配置
            existing_config = NotificationConfig.objects.filter(
                notification_type=notification_type
            ).first()

            if existing_config:
                # 更新现有配置
                serializer = self.get_serializer(existing_config, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()
                return Response(serializer.data)

        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """根据类型获取通知配置"""
        notification_type = request.query_params.get('type')
        if notification_type:
            config = NotificationConfig.objects.filter(
                notification_type=notification_type,
                is_active=True
            ).first()
            if config:
                serializer = self.get_serializer(config)
                return Response(serializer.data)
        return Response({'error': 'Config not found'}, status=status.HTTP_404_NOT_FOUND)


class NotificationChannelViewSet(viewsets.ModelViewSet):
    """通知渠道管理API"""
    serializer_class = NotificationChannelSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = NotificationChannel.objects.all()
        notif_type = self.request.query_params.get('type')
        if notif_type:
            queryset = queryset.filter(notification_type=notif_type)
        return queryset.order_by('name', '-updated_at')


class ConfigViewSet(viewsets.GenericViewSet):
    """配置统一管理API"""
    permission_classes = [AllowAny]  # 临时允许所有访问，生产环境应该使用IsAuthenticated

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """获取所有配置的摘要信息"""
        active_llm_config = LLMConfig.objects.filter(is_active=True).first()
        active_gitlab_config = GitLabConfig.objects.filter(is_active=True).first()
        notification_configs = NotificationConfig.objects.filter(is_active=True)
        notification_channels = NotificationChannel.objects.all()

        data = {
            'llm': LLMConfigSerializer(active_llm_config).data if active_llm_config else None,
            'gitlab': GitLabConfigSerializer(active_gitlab_config).data if active_gitlab_config else None,
            'notifications': NotificationConfigSerializer(notification_configs, many=True).data,
            'channels': NotificationChannelSerializer(notification_channels, many=True).data
        }

        return Response(data)

    @action(detail=False, methods=['post'])
    def batch_update(self, request):
        """批量更新配置"""
        data = request.data
        errors = {}

        try:
            # 更新LLM配置
            if 'llm' in data:
                llm_data = data['llm']
                active_llm = LLMConfig.objects.filter(is_active=True).first()

                if active_llm:
                    llm_serializer = LLMConfigSerializer(active_llm, data=llm_data, partial=True)
                    if llm_serializer.is_valid():
                        llm_serializer.save()
                    else:
                        errors['llm'] = llm_serializer.errors
                else:
                    llm_serializer = LLMConfigSerializer(data=llm_data)
                    if llm_serializer.is_valid():
                        llm_serializer.save()
                    else:
                        errors['llm'] = llm_serializer.errors

            # 更新GitLab配置
            if 'gitlab' in data:
                gitlab_data = data['gitlab']
                active_gitlab = GitLabConfig.objects.filter(is_active=True).first()

                if active_gitlab:
                    gitlab_serializer = GitLabConfigSerializer(active_gitlab, data=gitlab_data, partial=True)
                    if gitlab_serializer.is_valid():
                        gitlab_serializer.save()
                    else:
                        errors['gitlab'] = gitlab_serializer.errors
                else:
                    gitlab_serializer = GitLabConfigSerializer(data=gitlab_data)
                    if gitlab_serializer.is_valid():
                        gitlab_serializer.save()
                    else:
                        errors['gitlab'] = gitlab_serializer.errors

            # 通知渠道维护改为单独接口，这里仅做兼容忽略
            data.pop('notifications', None)
            data.pop('channels', None)

            if errors:
                return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

            return Response({'message': 'All configs updated successfully'})

        except Exception as e:
            return Response(
                {'error': f'Failed to update configs: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
