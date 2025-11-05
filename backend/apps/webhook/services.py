"""
Webhook services for project and event management
"""
import logging
from django.utils import timezone
from .models import Project

logger = logging.getLogger(__name__)


class ProjectService:
    """
    Service for managing GitLab projects
    """

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
                gitlab_data=project_data,
                last_webhook_at=timezone.now()
            )
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
        Get project statistics

        Returns:
            dict: Statistics about projects
        """
        total = Project.objects.count()
        enabled = Project.objects.filter(review_enabled=True).count()
        disabled = total - enabled

        return {
            'total_projects': total,
            'review_enabled': enabled,
            'review_disabled': disabled
        }
