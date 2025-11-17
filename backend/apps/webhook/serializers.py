from rest_framework import serializers
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
import pytz
from .models import WebhookLog, MergeRequestReview, Project, ProjectNotificationSetting, ProjectWebhookEventPrompt
from apps.llm.models import NotificationChannel, WebhookEventRule


class LocalDateTimeField(serializers.DateTimeField):
    """
    自定义日期时间字段，返回本地时区（Asia/Shanghai）的时间
    """
    def to_representation(self, value):
        if value is None:
            return None

        local_tz = pytz.timezone(getattr(settings, 'TIME_ZONE', 'Asia/Shanghai'))

        # 如果是 naive datetime，将其视为本地时间；否则转换到本地时区
        if timezone.is_naive(value):
            value = local_tz.localize(value)
        else:
            value = value.astimezone(local_tz)

        local_time = value.replace(microsecond=0)

        # 返回简单的日期时间格式：年月日时分秒
        return local_time.strftime('%Y-%m-%d %H:%M:%S')


class ProjectSerializer(serializers.ModelSerializer):
    """
    Serializer for Project model with enhanced statistics
    """
    # Additional computed fields
    commits_count = serializers.SerializerMethodField()
    mr_count = serializers.SerializerMethodField()
    members_count = serializers.SerializerMethodField()
    last_activity = serializers.SerializerMethodField()
    weekly_reviews = serializers.SerializerMethodField()
    recent_events_count = serializers.SerializerMethodField()
    webhook_url = serializers.SerializerMethodField()
    
    # 使用本地时区字段
    created_at = LocalDateTimeField(read_only=True)
    updated_at = LocalDateTimeField(read_only=True)
    last_webhook_at = LocalDateTimeField(read_only=True)

    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ['_id', 'created_at', 'updated_at', 'last_webhook_at']

    def get_commits_count(self, obj):
        """Get commit count from webhook logs"""
        return WebhookLog.objects.filter(
            project_id=obj.project_id,
            event_type='push'
        ).count()

    def get_mr_count(self, obj):
        """Get merge request count from webhook logs"""
        return WebhookLog.objects.filter(
            project_id=obj.project_id,
            event_type='merge_request'
        ).values('merge_request_iid').distinct().count()

    def get_members_count(self, obj):
        """Get unique members count from webhook logs"""
        return WebhookLog.objects.filter(
            project_id=obj.project_id
        ).values('user_email').distinct().count()

    def get_last_activity(self, obj):
        """Get formatted last activity time"""
        if obj.last_webhook_at:
            return self._format_time_ago(obj.last_webhook_at)
        return self._format_time_ago(obj.updated_at)

    def get_weekly_reviews(self, obj):
        """Get review count from last week"""
        week_ago = timezone.now() - timedelta(days=7)
        return MergeRequestReview.objects.filter(
            project_id=obj.project_id,
            created_at__gte=week_ago,
            status='completed'
        ).count()

    def get_recent_events_count(self, obj):
        """Get events count from last 24 hours"""
        day_ago = timezone.now() - timedelta(hours=24)
        return WebhookLog.objects.filter(
            project_id=obj.project_id,
            created_at__gte=day_ago
        ).count()

    def get_webhook_url(self, obj):
        """Generate webhook URL for this project"""
        from django.conf import settings
        base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
        return f"{base_url}/api/webhook/gitlab/"

    def _format_time_ago(self, dt):
        """Format datetime as time ago string"""
        if not dt:
            return "未知"

        now = timezone.now()
        diff = now - dt

        if diff < timedelta(minutes=1):
            return "刚刚"
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} 分钟前"
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} 小时前"
        elif diff < timedelta(days=30):
            days = diff.days
            return f"{days} 天前"
        else:
            return dt.strftime("%Y-%m-%d")


class ProjectListSerializer(ProjectSerializer):
    """
    Simplified serializer for project list views
    """
    description = serializers.SerializerMethodField()
    namespace = serializers.SerializerMethodField()

    class Meta(ProjectSerializer.Meta):
        fields = [
            'project_id', 'project_name', 'namespace', 'description',
            'review_enabled', 'commits_count', 'mr_count', 'members_count',
            'last_activity', 'weekly_reviews', 'recent_events_count',
            'webhook_url', 'created_at'
        ]

    def get_description(self, obj):
        """Get project description from gitlab_data"""
        return obj.gitlab_data_dict.get('description', '')

    def get_namespace(self, obj):
        """Get formatted namespace"""
        namespace_info = obj.gitlab_data_dict.get('namespace', {})
        if isinstance(namespace_info, dict):
            return namespace_info.get('full_path', obj.namespace)
        return obj.namespace


class ProjectUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating project settings"""
    class Meta:
        model = Project
        fields = [
            'review_enabled',
            'auto_review_on_mr',
            'exclude_file_types',
            'ignore_file_patterns',
            'gitlab_comment_notifications_enabled',
        ]


class ProjectNotificationSettingSerializer(serializers.ModelSerializer):
    channel_id = serializers.IntegerField(source='channel.id', read_only=True)
    channel_name = serializers.CharField(source='channel.name', read_only=True)
    notification_type = serializers.CharField(source='channel.notification_type', read_only=True)

    class Meta:
        model = ProjectNotificationSetting
        fields = ['channel_id', 'channel_name', 'notification_type', 'enabled']


class ProjectNotificationUpdateSerializer(serializers.Serializer):
    gitlab_comment_enabled = serializers.BooleanField(required=False)
    channel_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,
        required=False
    )

    def validate_channel_ids(self, value):
        valid_ids = set(NotificationChannel.objects.filter(id__in=value).values_list('id', flat=True))
        missing = set(value) - valid_ids
        if missing:
            raise serializers.ValidationError(f"通道不存在: {sorted(missing)}")
        return list(valid_ids)


class ProjectWebhookEventsSerializer(serializers.Serializer):
    """获取项目的webhook事件配置"""
    enabled_event_ids = serializers.ListField(
        child=serializers.IntegerField(),
        read_only=True
    )


class ProjectWebhookEventsUpdateSerializer(serializers.Serializer):
    """更新项目的webhook事件配置"""
    event_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,
        required=True
    )

    def validate_event_ids(self, value):
        from apps.llm.models import WebhookEventRule
        valid_ids = set(WebhookEventRule.objects.filter(id__in=value).values_list('id', flat=True))
        missing = set(value) - valid_ids
        if missing:
            raise serializers.ValidationError(f"事件规则不存在: {sorted(missing)}")
        return list(valid_ids)


class WebhookLogSerializer(serializers.ModelSerializer):
    # 使用本地时区字段
    created_at = LocalDateTimeField(read_only=True)
    processed_at = LocalDateTimeField(read_only=True)
    
    class Meta:
        model = WebhookLog
        fields = '__all__'
        read_only_fields = ['_id', 'created_at', 'processed_at']


class MergeRequestReviewSerializer(serializers.ModelSerializer):
    # 使用本地时区字段
    created_at = LocalDateTimeField(read_only=True)
    updated_at = LocalDateTimeField(read_only=True)
    completed_at = LocalDateTimeField(read_only=True)

    class Meta:
        model = MergeRequestReview
        fields = '__all__'
        read_only_fields = ['_id', 'created_at', 'updated_at', 'completed_at']


class ProjectWebhookEventPromptSerializer(serializers.ModelSerializer):
    """项目 Webhook 事件自定义 Prompt 序列化器"""

    event_rule_name = serializers.CharField(source='event_rule.name', read_only=True)
    event_rule_type = serializers.CharField(source='event_rule.event_type', read_only=True)
    event_rule_description = serializers.CharField(source='event_rule.description', read_only=True)

    # 使用本地时区字段
    created_at = LocalDateTimeField(read_only=True)
    updated_at = LocalDateTimeField(read_only=True)

    class Meta:
        model = ProjectWebhookEventPrompt
        fields = [
            'id',
            'project',
            'event_rule',
            'event_rule_name',
            'event_rule_type',
            'event_rule_description',
            'custom_prompt',
            'use_custom',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProjectWebhookEventPromptUpdateSerializer(serializers.Serializer):
    """更新项目 Webhook 事件 Prompt 配置"""
    event_rule_id = serializers.IntegerField(required=True)
    custom_prompt = serializers.CharField(allow_blank=True, required=False, default='')
    use_custom = serializers.BooleanField(required=False, default=False)

    def validate_event_rule_id(self, value):
        """验证事件规则是否存在"""
        if not WebhookEventRule.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"事件规则 ID {value} 不存在")
        return value
