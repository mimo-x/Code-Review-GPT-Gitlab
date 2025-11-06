from rest_framework import serializers
from datetime import datetime, timedelta
from django.utils import timezone
from .models import WebhookLog, MergeRequestReview, Project


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
        fields = ['review_enabled', 'auto_review_on_mr', 'exclude_file_types', 'ignore_file_patterns']


class WebhookLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookLog
        fields = '__all__'
        read_only_fields = ['_id', 'created_at', 'processed_at']


class MergeRequestReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = MergeRequestReview
        fields = '__all__'
        read_only_fields = ['_id', 'created_at', 'updated_at', 'completed_at']
