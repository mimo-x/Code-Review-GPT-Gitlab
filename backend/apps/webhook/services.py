"""
Webhook services for project and event management
"""
import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db import models
import pytz
from .models import Project, WebhookLog, MergeRequestReview

logger = logging.getLogger(__name__)


class ProjectService:
    """
    Service for managing GitLab projects
    """

    @staticmethod
    def _to_local_iso(dt):
        """Convert aware datetimes to the configured local ISO string."""
        if not dt:
            return None

        local_tz = pytz.timezone(getattr(settings, 'TIME_ZONE', 'Asia/Shanghai'))
        
        if timezone.is_naive(dt):
            dt = local_tz.localize(dt)
        else:
            dt = dt.astimezone(local_tz)

        return dt.replace(microsecond=0).isoformat()

    @staticmethod
    def get_or_create_project(project_data):
        """
        Get existing project or create a new one with review disabled by default

        Args:
            project_data: Dictionary containing project information from GitLab webhook

        Returns:
            tuple: (Project instance, created: bool)
        """
        project_id = project_data.get('id')

        if not project_id:
            logger.error("Project ID not found in webhook payload")
            return None, False

        # Check if project exists
        try:
            project = Project.objects.get(project_id=project_id)
            created = False

            # Update last webhook time
            project.last_webhook_at = timezone.now()
            project.save(update_fields=['last_webhook_at', 'updated_at'])

            logger.info(f"Project {project.project_name} (ID: {project_id}) found - Review enabled: {project.review_enabled}")

        except Project.DoesNotExist:
            # Create new project with review disabled by default
            project = Project.objects.create(
                project_id=project_id,
                project_name=project_data.get('name', ''),
                project_path=project_data.get('path_with_namespace', ''),
                project_url=project_data.get('web_url', ''),
                namespace=project_data.get('namespace', ''),
                review_enabled=False,  # Default: disabled
                auto_review_on_mr=True,
                last_webhook_at=timezone.now()
            )
            # Set gitlab_data using the property
            project.gitlab_data_dict = project_data
            project.save()
            created = True

            logger.info(f"New project created: {project.project_name} (ID: {project_id}) - Review disabled by default")

        return project, created

    @staticmethod
    def enable_review(project_id):
        """
        Enable code review for a project

        Args:
            project_id: GitLab project ID

        Returns:
            Project instance or None
        """
        try:
            project = Project.objects.get(project_id=project_id)
            project.review_enabled = True
            project.save(update_fields=['review_enabled', 'updated_at'])

            logger.info(f"Review enabled for project: {project.project_name} (ID: {project_id})")
            return project

        except Project.DoesNotExist:
            logger.error(f"Project with ID {project_id} not found")
            return None

    @staticmethod
    def disable_review(project_id):
        """
        Disable code review for a project

        Args:
            project_id: GitLab project ID

        Returns:
            Project instance or None
        """
        try:
            project = Project.objects.get(project_id=project_id)
            project.review_enabled = False
            project.save(update_fields=['review_enabled', 'updated_at'])

            logger.info(f"Review disabled for project: {project.project_name} (ID: {project_id})")
            return project

        except Project.DoesNotExist:
            logger.error(f"Project with ID {project_id} not found")
            return None

    @staticmethod
    def is_review_enabled(project_id):
        """
        Check if code review is enabled for a project

        Args:
            project_id: GitLab project ID

        Returns:
            bool: True if review is enabled, False otherwise
        """
        try:
            project = Project.objects.get(project_id=project_id)
            return project.review_enabled
        except Project.DoesNotExist:
            # If project doesn't exist, return False (will be created on first webhook)
            return False

    @staticmethod
    def update_project_settings(project_id, **kwargs):
        """
        Update project settings

        Args:
            project_id: GitLab project ID
            **kwargs: Settings to update (review_enabled, auto_review_on_mr, etc.)

        Returns:
            Project instance or None
        """
        try:
            project = Project.objects.get(project_id=project_id)

            # Update allowed fields
            allowed_fields = [
                'review_enabled',
                'auto_review_on_mr',
                'exclude_file_types',
                'ignore_file_patterns'
            ]

            updated_fields = []
            for field, value in kwargs.items():
                if field in allowed_fields:
                    setattr(project, field, value)
                    updated_fields.append(field)

            if updated_fields:
                updated_fields.append('updated_at')
                project.save(update_fields=updated_fields)
                logger.info(f"Updated settings for project {project.project_name}: {updated_fields}")

            return project

        except Project.DoesNotExist:
            logger.error(f"Project with ID {project_id} not found")
            return None

    @staticmethod
    def get_all_projects():
        """
        Get all projects

        Returns:
            QuerySet of all projects
        """
        return Project.objects.all()

    @staticmethod
    def get_enabled_projects():
        """
        Get all projects with review enabled

        Returns:
            QuerySet of projects with review enabled
        """
        return Project.objects.filter(review_enabled=True)

    @staticmethod
    def get_project_stats():
        """
        Get comprehensive project statistics

        Returns:
            dict: Statistics about projects
        """
        total = Project.objects.count()
        enabled = Project.objects.filter(review_enabled=True).count()
        disabled = total - enabled

        # Weekly statistics
        week_ago = timezone.now() - timedelta(days=7)
        weekly_reviews = MergeRequestReview.objects.filter(
            created_at__gte=week_ago,
            status='completed'
        ).count()

        # Recent events (last 24 hours)
        day_ago = timezone.now() - timedelta(hours=24)
        recent_events = WebhookLog.objects.filter(
            created_at__gte=day_ago
        ).count()

        # Active projects (projects with recent webhook events)
        active_projects = Project.objects.filter(
            last_webhook_at__gte=week_ago
        ).count()

        return {
            'total_projects': total,
            'active_projects': active_projects,
            'review_enabled': enabled,
            'review_disabled': disabled,
            'weekly_reviews': weekly_reviews,
            'recent_events': recent_events,
            'recent_events_24h': recent_events
        }

    @staticmethod
    def get_project_detail_stats(project_id):
        """
        Get detailed statistics for a specific project

        Args:
            project_id: GitLab project ID

        Returns:
            dict: Detailed statistics for the project
        """
        try:
            project = Project.objects.get(project_id=project_id)
        except Project.DoesNotExist:
            return None

        # Time ranges
        week_ago = timezone.now() - timedelta(days=7)
        day_ago = timezone.now() - timedelta(hours=24)

        # Webhook statistics
        total_webhooks = WebhookLog.objects.filter(project_id=project_id).count()
        recent_webhooks = WebhookLog.objects.filter(
            project_id=project_id,
            created_at__gte=week_ago
        ).count()

        # Merge request statistics
        total_mrs = WebhookLog.objects.filter(
            project_id=project_id,
            event_type='merge_request'
        ).values('merge_request_iid').distinct().count()

        # Review statistics
        total_reviews = MergeRequestReview.objects.filter(project_id=project_id).count()
        completed_reviews = MergeRequestReview.objects.filter(
            project_id=project_id,
            status='completed'
        ).count()
        weekly_reviews = MergeRequestReview.objects.filter(
            project_id=project_id,
            created_at__gte=week_ago,
            status='completed'
        ).count()

        # Member statistics
        unique_members = WebhookLog.objects.filter(
            project_id=project_id
        ).values('user_email').distinct().count()

        # Event type distribution
        event_types = WebhookLog.objects.filter(
            project_id=project_id
        ).values('event_type').annotate(count=models.Count('event_type'))

        return {
            'project': {
                'id': project.project_id,
                'name': project.project_name,
                'review_enabled': project.review_enabled,
                'created_at': ProjectService._to_local_iso(project.created_at),
                'last_webhook_at': ProjectService._to_local_iso(project.last_webhook_at)
            },
            'webhooks': {
                'total': total_webhooks,
                'recent': recent_webhooks,
                'event_types': list(event_types)
            },
            'merge_requests': {
                'total': total_mrs
            },
            'reviews': {
                'total': total_reviews,
                'completed': completed_reviews,
                'weekly': weekly_reviews,
                'completion_rate': (completed_reviews / total_reviews * 100) if total_reviews > 0 else 0
            },
            'members': {
                'unique_count': unique_members
            }
        }

    @staticmethod
    def get_recent_webhook_logs(project_id=None, limit=50):
        """
        Get recent webhook logs with optional project filtering

        Args:
            project_id: Optional project ID to filter by
            limit: Maximum number of logs to return

        Returns:
            QuerySet: Webhook logs ordered by creation time
        """
        queryset = WebhookLog.objects.all().order_by('-created_at')

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        return queryset[:limit]

    @staticmethod
    def get_project_review_history(project_id, days=30):
        """
        Get review history for a project over the specified period

        Args:
            project_id: GitLab project ID
            days: Number of days to look back

        Returns:
            QuerySet: Review history ordered by creation time
        """
        start_date = timezone.now() - timedelta(days=days)

        return MergeRequestReview.objects.filter(
            project_id=project_id,
            created_at__gte=start_date
        ).order_by('-created_at')
