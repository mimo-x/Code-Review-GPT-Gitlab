import json
import logging
import threading
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import WebhookLog, MergeRequestReview, Project
from .serializers import WebhookLogSerializer, ProjectSerializer, ProjectUpdateSerializer
from .services import ProjectService
from apps.review.services import GitlabService, ReviewService

logger = logging.getLogger(__name__)


@api_view(['POST'])
def gitlab_webhook(request):
    """
    GitLab Webhook endpoint
    Handles incoming webhook events from GitLab
    """
    try:
        payload = request.data
        event_type = payload.get('object_kind')
        project_data = payload.get('project', {})

        logger.info(f"Received webhook event: {event_type}")

        # Check or create project
        project, created = ProjectService.get_or_create_project(project_data)

        if created:
            logger.info(f"🆕 New project added: {project.project_name} (ID: {project.project_id}) - Review disabled by default")

        # Log the webhook event
        webhook_log = create_webhook_log(payload, event_type)

        # Handle different event types
        if event_type == 'merge_request':
            return handle_merge_request(payload, webhook_log)
        elif event_type == 'push':
            return handle_push(payload, webhook_log)
        else:
            return handle_other(payload, webhook_log, event_type)

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def create_webhook_log(payload, event_type):
    """Create a webhook log entry"""
    try:
        project = payload.get('project', {})
        user = payload.get('user', {})
        object_attributes = payload.get('object_attributes', {})

        webhook_log = WebhookLog.objects.create(
            event_type=event_type,
            project_id=project.get('id', 0),
            project_name=project.get('name', ''),
            merge_request_iid=object_attributes.get('iid') if event_type == 'merge_request' else None,
            user_name=user.get('name', ''),
            user_email=user.get('email', ''),
            source_branch=object_attributes.get('source_branch', ''),
            target_branch=object_attributes.get('target_branch', ''),
            payload=payload
        )
        return webhook_log
    except Exception as e:
        logger.error(f"Error creating webhook log: {str(e)}")
        return None


def handle_merge_request(payload, webhook_log):
    """
    Handle merge request events
    """
    try:
        object_attributes = payload.get('object_attributes', {})
        action = object_attributes.get('action')

        # Only process 'open' and 'reopen' actions
        if action not in ['open', 'reopen']:
            logger.info(f"Ignoring merge request action: {action}")
            return Response({'status': 'ignored', 'message': f'Action {action} is not processed'})

        project = payload.get('project', {})
        project_id = project.get('id')
        merge_request_iid = object_attributes.get('iid')

        logger.info(f"Processing merge request: Project {project_id}, MR #{merge_request_iid}")

        # Check if review is enabled for this project
        if not ProjectService.is_review_enabled(project_id):
            logger.info(f"⏸️  Review is disabled for project {project_id}. Skipping code review.")

            # Mark webhook as processed
            if webhook_log:
                webhook_log.processed = True
                webhook_log.processed_at = timezone.now()
                webhook_log.error_message = "Review disabled for this project"
                webhook_log.save()

            return Response({
                'status': 'skipped',
                'message': 'Code review is disabled for this project. Enable it in project settings to start reviewing.'
            })

        # Create or update MergeRequestReview record
        review, created = MergeRequestReview.objects.get_or_create(
            project_id=project_id,
            merge_request_iid=merge_request_iid,
            defaults={
                'project_name': project.get('name', ''),
                'merge_request_title': object_attributes.get('title', ''),
                'source_branch': object_attributes.get('source_branch', ''),
                'target_branch': object_attributes.get('target_branch', ''),
                'author_name': object_attributes.get('last_commit', {}).get('author', {}).get('name', ''),
                'author_email': object_attributes.get('last_commit', {}).get('author', {}).get('email', ''),
                'status': 'pending'
            }
        )

        # Start review process in a separate thread
        thread = threading.Thread(
            target=process_merge_request_review,
            args=(project_id, merge_request_iid, review.pk, payload)
        )
        thread.daemon = True
        thread.start()

        # Mark webhook as processed
        if webhook_log:
            webhook_log.processed = True
            webhook_log.processed_at = timezone.now()
            webhook_log.save()

        return Response({'status': 'success', 'message': 'Review process started'})

    except Exception as e:
        logger.error(f"Error handling merge request: {str(e)}", exc_info=True)
        if webhook_log:
            webhook_log.error_message = str(e)
            webhook_log.save()
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def handle_push(payload, webhook_log):
    """
    Handle push events
    """
    logger.info("Push event received but not processed yet")
    if webhook_log:
        webhook_log.processed = True
        webhook_log.processed_at = timezone.now()
        webhook_log.save()
    return Response({'status': 'success', 'message': 'Push event received'})


def handle_other(payload, webhook_log, event_type):
    """
    Handle other event types
    """
    logger.info(f"Unhandled event type: {event_type}")
    if webhook_log:
        webhook_log.processed = True
        webhook_log.processed_at = timezone.now()
        webhook_log.save()
    return Response({'status': 'ignored', 'message': f'Event type {event_type} is not processed'})


def process_merge_request_review(project_id, merge_request_iid, review_id, payload):
    """
    Process merge request review in a separate thread
    """
    try:
        from apps.review.services import ReviewService

        # Get review record
        review = MergeRequestReview.objects.get(pk=review_id)
        review.status = 'processing'
        review.save()

        # Initialize services
        gitlab_service = GitlabService()
        review_service = ReviewService()

        # Fetch merge request changes
        changes = gitlab_service.get_merge_request_changes(project_id, merge_request_iid)

        if not changes:
            review.status = 'failed'
            review.error_message = 'No changes found in merge request'
            review.save()
            return

        # Perform review
        review_result = review_service.review_merge_request(changes, payload)

        # Update review record
        review.review_content = review_result.get('content', '')
        review.review_score = review_result.get('score')
        review.files_reviewed = review_result.get('files_reviewed', [])
        review.total_files = len(review_result.get('files_reviewed', []))
        review.status = 'completed'
        review.completed_at = timezone.now()
        review.save()

        # Post comment to GitLab
        gitlab_service.post_merge_request_comment(
            project_id,
            merge_request_iid,
            review.review_content
        )

        review.response_sent = True
        review.response_type = 'gitlab_comment'
        review.save()

        logger.info(f"Review completed for MR #{merge_request_iid}")

    except Exception as e:
        logger.error(f"Error processing review: {str(e)}", exc_info=True)
        try:
            review = MergeRequestReview.objects.get(pk=review_id)
            review.status = 'failed'
            review.error_message = str(e)
            review.save()
        except:
            pass


# ==================== Project Management APIs ====================

@api_view(['GET'])
def list_projects(request):
    """
    List all projects

    Query parameters:
        - review_enabled: Filter by review status (true/false)
    """
    try:
        review_enabled = request.query_params.get('review_enabled')

        if review_enabled is not None:
            review_enabled = review_enabled.lower() == 'true'
            projects = Project.objects.filter(review_enabled=review_enabled)
        else:
            projects = Project.objects.all()

        serializer = ProjectSerializer(projects, many=True)

        return Response({
            'status': 'success',
            'count': projects.count(),
            'projects': serializer.data
        })

    except Exception as e:
        logger.error(f"Error listing projects: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_project(request, project_id):
    """
    Get project details by GitLab project ID
    """
    try:
        project = Project.objects.get(project_id=project_id)
        serializer = ProjectSerializer(project)

        return Response({
            'status': 'success',
            'project': serializer.data
        })

    except Project.DoesNotExist:
        return Response(
            {'status': 'error', 'message': f'Project {project_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error getting project: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
def update_project(request, project_id):
    """
    Update project settings

    Body parameters:
        - review_enabled: Enable/disable code review (boolean)
        - auto_review_on_mr: Auto review on MR (boolean)
        - exclude_file_types: Array of file types to exclude
        - ignore_file_patterns: Array of file patterns to ignore
    """
    try:
        project = Project.objects.get(project_id=project_id)

        serializer = ProjectUpdateSerializer(project, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()

            logger.info(f"Project {project.project_name} settings updated: {request.data}")

            return Response({
                'status': 'success',
                'message': 'Project settings updated successfully',
                'project': ProjectSerializer(project).data
            })
        else:
            return Response(
                {'status': 'error', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

    except Project.DoesNotExist:
        return Response(
            {'status': 'error', 'message': f'Project {project_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error updating project: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def enable_project_review(request, project_id):
    """
    Enable code review for a project
    """
    try:
        project = ProjectService.enable_review(project_id)

        if project:
            return Response({
                'status': 'success',
                'message': f'Code review enabled for project {project.project_name}',
                'project': ProjectSerializer(project).data
            })
        else:
            return Response(
                {'status': 'error', 'message': f'Project {project_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    except Exception as e:
        logger.error(f"Error enabling review: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def disable_project_review(request, project_id):
    """
    Disable code review for a project
    """
    try:
        project = ProjectService.disable_review(project_id)

        if project:
            return Response({
                'status': 'success',
                'message': f'Code review disabled for project {project.project_name}',
                'project': ProjectSerializer(project).data
            })
        else:
            return Response(
                {'status': 'error', 'message': f'Project {project_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    except Exception as e:
        logger.error(f"Error disabling review: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def project_stats(request):
    """
    Get project statistics
    """
    try:
        stats = ProjectService.get_project_stats()

        return Response({
            'status': 'success',
            'stats': stats
        })

    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
