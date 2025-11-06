import json
import logging
import threading
import uuid
from django.utils import timezone
from django.db import models, transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import WebhookLog, MergeRequestReview, Project
from .serializers import (
    WebhookLogSerializer,
    ProjectSerializer,
    ProjectListSerializer,
    ProjectUpdateSerializer,
    MergeRequestReviewSerializer
)
from .services import ProjectService
from apps.review.services import GitlabService, ReviewService

logger = logging.getLogger(__name__)


@api_view(['POST'])
def gitlab_webhook(request):
    """
    GitLab Webhook endpoint
    Handles incoming webhook events from GitLab

    优化版本：确保所有请求都被记录到webhook_logs表中
    """
    # 生成请求ID用于日志追踪
    request_id = str(uuid.uuid4())

    # 立即创建初始日志记录，确保请求被记录
    webhook_log = create_initial_webhook_log(request)

    if webhook_log:
        logger.info(f"Received webhook event: {webhook_log.event_type} (Request ID: {webhook_log.request_id})")
    else:
        logger.error(f"Critical: Failed to create webhook log for request {request_id}")

    try:
        with transaction.atomic():
            # 提取payload和事件类型
            try:
                payload = request.data
            except Exception:
                payload = {}
                logger.warning(f"Failed to parse request data for request {request_id}")

            event_type = payload.get('object_kind', 'unknown')
            project_data = payload.get('project', {})

            # 更新日志记录中的事件类型（如果之前是unknown）
            if webhook_log and webhook_log.event_type == 'unknown' and event_type != 'unknown':
                webhook_log.event_type = event_type
                webhook_log.save(update_fields=['event_type'])

            # Check or create project
            try:
                project, created = ProjectService.get_or_create_project(project_data)
                if created:
                    logger.info(f"🆕 New project added: {project.project_name} (ID: {project.project_id}) - Review disabled by default")
            except Exception as project_error:
                logger.error(f"Error creating/retrieving project for request {request_id}: {str(project_error)}")
                # 继续处理，不因为项目创建失败而停止

            # Handle different event types
            try:
                if event_type == 'merge_request':
                    return handle_merge_request(payload, webhook_log)
                elif event_type == 'push':
                    return handle_push(payload, webhook_log)
                elif event_type == 'issue':
                    return handle_issue(payload, webhook_log)
                elif event_type == 'note':
                    return handle_note(payload, webhook_log)
                elif event_type == 'pipeline':
                    return handle_pipeline(payload, webhook_log)
                elif event_type == 'tag_push':
                    return handle_tag_push(payload, webhook_log)
                else:
                    return handle_other(payload, webhook_log, event_type)
            except Exception as handler_error:
                logger.error(f"Error in event handler for request {request_id}: {str(handler_error)}", exc_info=True)
                # 标记日志为处理失败
                if webhook_log:
                    webhook_log.processed = True
                    webhook_log.processed_at = timezone.now()
                    webhook_log.error_message = f"Handler error: {str(handler_error)}"
                    webhook_log.save(update_fields=['processed', 'processed_at', 'error_message'])

                return Response(
                    {'status': 'error', 'message': f'Event handler failed: {str(handler_error)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

    except Exception as e:
        logger.error(f"Critical error processing webhook {request_id}: {str(e)}", exc_info=True)

        # 标记日志为处理失败
        if webhook_log:
            try:
                webhook_log.processed = True
                webhook_log.processed_at = timezone.now()
                webhook_log.error_message = f"Critical processing error: {str(e)}"
                webhook_log.save(update_fields=['processed', 'processed_at', 'error_message'])
            except Exception as save_error:
                logger.error(f"Failed to update webhook log {request_id}: {str(save_error)}")

        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def create_initial_webhook_log(request, payload=None, event_type=None):
    """
    立即创建webhook日志记录，确保所有请求都被记录
    在任何业务逻辑处理之前调用
    """
    try:
        # 生成唯一的请求ID用于追踪
        request_id = str(uuid.uuid4())

        # 提取请求数据
        if payload is None:
            try:
                payload = request.data
            except Exception:
                payload = {}

        if event_type is None:
            event_type = payload.get('object_kind', 'unknown')

        # 提取HTTP请求元数据
        headers = {}
        for key, value in request.META.items():
            if key.startswith('HTTP_'):
                # 将HTTP_HEADER_NAME��换为Header-Name格式
                header_name = key[5:].replace('_', '-').title()
                headers[header_name] = value

        # 提取项目信息
        project = payload.get('project', {})
        user = payload.get('user', {})
        object_attributes = payload.get('object_attributes', {})

        # 创建日志记录
        webhook_log = WebhookLog.objects.create(
            request_id=request_id,
            event_type=event_type,
            project_id=project.get('id', 0),
            project_name=project.get('name', ''),
            merge_request_iid=object_attributes.get('iid') if event_type == 'merge_request' else None,
            user_name=user.get('name', ''),
            user_email=user.get('email', ''),
            source_branch=object_attributes.get('source_branch', ''),
            target_branch=object_attributes.get('target_branch', ''),
            remote_addr=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            processed=False  # 初始状态为未处理
        )

        # 设置JSON字段
        webhook_log.payload_dict = payload
        webhook_log.request_headers_dict = headers

        # 保存原始请求体（如果可能的话）
        try:
            webhook_log.request_body_raw = request.body.decode('utf-8')
        except Exception:
            webhook_log.request_body_raw = str(payload)

        webhook_log.save()
        logger.info(f"Webhook log created: {request_id} - {event_type}")
        return webhook_log

    except Exception as e:
        logger.error(f"Failed to create initial webhook log: {str(e)}", exc_info=True)
        # 即使创建失败也要尝试创建一个最小化的记录
        try:
            fallback_log = WebhookLog.objects.create(
                request_id=str(uuid.uuid4()),
                event_type=event_type or 'error',
                project_id=0,
                project_name='unknown',
                user_name='system',
                user_email='',
                processed=False,
                error_message=f"Log creation failed: {str(e)}"
            )
            fallback_log.payload_dict = payload or {}
            fallback_log.save()
            return fallback_log
        except Exception as fallback_error:
            logger.error(f"Critical: Failed to create fallback webhook log: {str(fallback_error)}")
            return None


def create_webhook_log(payload, event_type):
    """保持向后兼容的创建webhook日志函数"""
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
            target_branch=object_attributes.get('target_branch', '')
        )
        # Set payload using the property
        webhook_log.payload_dict = payload
        webhook_log.save()
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
    List all projects with enhanced statistics

    Query parameters:
        - review_enabled: Filter by review status (true/false)
        - limit: Limit number of results (default: 50)
        - search: Search in project name and description
    """
    try:
        review_enabled = request.query_params.get('review_enabled')
        limit = request.query_params.get('limit', 50)
        search = request.query_params.get('search')

        # Start with all projects
        projects = Project.objects.all()

        # Apply filters
        if review_enabled is not None:
            review_enabled = review_enabled.lower() == 'true'
            projects = projects.filter(review_enabled=review_enabled)

        if search:
            projects = projects.filter(
                models.Q(project_name__icontains=search) |
                models.Q(project_path__icontains=search)
            )

        # Order by last webhook activity, then by creation time
        projects = projects.order_by('-last_webhook_at', '-created_at')

        # Apply limit
        try:
            limit = int(limit)
            projects = projects[:limit]
        except (ValueError, TypeError):
            pass

        # Use enhanced serializer for list view
        serializer = ProjectListSerializer(projects, many=True)

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
    Get project details with comprehensive statistics by GitLab project ID
    """
    try:
        project = Project.objects.get(project_id=project_id)

        # Get detailed statistics
        stats = ProjectService.get_project_detail_stats(project_id)

        # Get project with enhanced serializer
        serializer = ProjectSerializer(project)

        return Response({
            'status': 'success',
            'project': serializer.data,
            'stats': stats
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
    Get comprehensive project statistics
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


@api_view(['GET'])
def project_webhook_logs(request, project_id):
    """
    Get webhook logs for a specific project

    Query parameters:
        - limit: Limit number of results (default: 20)
    """
    try:
        limit = request.query_params.get('limit', 20)
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 20

        logs = ProjectService.get_recent_webhook_logs(project_id, limit)
        serializer = WebhookLogSerializer(logs, many=True)

        return Response({
            'status': 'success',
            'count': len(serializer.data),
            'logs': serializer.data
        })

    except Exception as e:
        logger.error(f"Error getting webhook logs: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def project_review_history(request, project_id):
    """
    Get review history for a specific project

    Query parameters:
        - days: Number of days to look back (default: 30)
        - limit: Limit number of results (default: 20)
    """
    try:
        days = request.query_params.get('days', 30)
        limit = request.query_params.get('limit', 20)

        try:
            days = int(days)
        except (ValueError, TypeError):
            days = 30

        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 20

        reviews = ProjectService.get_project_review_history(project_id, days)
        reviews = reviews[:limit]
        serializer = MergeRequestReviewSerializer(reviews, many=True)

        return Response({
            'status': 'success',
            'count': len(serializer.data),
            'reviews': serializer.data
        })

    except Exception as e:
        logger.error(f"Error getting review history: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== Enhanced Event Handlers ====================

def handle_issue(payload, webhook_log):
    """
    Handle issue events
    """
    try:
        object_attributes = payload.get('object_attributes', {})
        action = object_attributes.get('action')

        logger.info(f"Issue event: {action} - Issue #{object_attributes.get('iid')}")

        # Mark webhook as processed
        if webhook_log:
            webhook_log.processed = True
            webhook_log.processed_at = timezone.now()
            webhook_log.save()

        return Response({
            'status': 'success',
            'message': f'Issue {action} event processed'
        })

    except Exception as e:
        logger.error(f"Error handling issue: {str(e)}", exc_info=True)
        if webhook_log:
            webhook_log.error_message = str(e)
            webhook_log.save()
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def handle_note(payload, webhook_log):
    """
    Handle note/comment events (comments on MRs, issues, commits)
    """
    try:
        object_attributes = payload.get('object_attributes', {})
        noteable_type = object_attributes.get('noteable_type')
        action = object_attributes.get('action')

        logger.info(f"Note event: {action} on {noteable_type}")

        # Only process MR comments for potential review triggers
        if noteable_type == 'MergeRequest' and action == 'create':
            # Check if this comment might trigger a review
            comment = object_attributes.get('note', '')
            if 'review' in comment.lower() or 'check' in comment.lower():
                logger.info(f"Potential review trigger comment: {comment[:100]}...")
                # Could trigger a review process here if needed

        # Mark webhook as processed
        if webhook_log:
            webhook_log.processed = True
            webhook_log.processed_at = timezone.now()
            webhook_log.save()

        return Response({
            'status': 'success',
            'message': f'Note {action} event processed'
        })

    except Exception as e:
        logger.error(f"Error handling note: {str(e)}", exc_info=True)
        if webhook_log:
            webhook_log.error_message = str(e)
            webhook_log.save()
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def handle_pipeline(payload, webhook_log):
    """
    Handle CI/CD pipeline events
    """
    try:
        object_attributes = payload.get('object_attributes', {})
        status = object_attributes.get('status')
        source = object_attributes.get('source')

        logger.info(f"Pipeline event: {status} from {source}")

        # Update project activity timestamp
        project_data = payload.get('project', {})
        project_id = project_data.get('id')
        if project_id:
            try:
                project = Project.objects.get(project_id=project_id)
                project.last_webhook_at = timezone.now()
                project.save(update_fields=['last_webhook_at', 'updated_at'])
            except Project.DoesNotExist:
                pass

        # Mark webhook as processed
        if webhook_log:
            webhook_log.processed = True
            webhook_log.processed_at = timezone.now()
            webhook_log.save()

        return Response({
            'status': 'success',
            'message': f'Pipeline {status} event processed'
        })

    except Exception as e:
        logger.error(f"Error handling pipeline: {str(e)}", exc_info=True)
        if webhook_log:
            webhook_log.error_message = str(e)
            webhook_log.save()
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def handle_tag_push(payload, webhook_log):
    """
    Handle tag push events
    """
    try:
        ref = payload.get('ref', '')
        project_data = payload.get('project', {})

        logger.info(f"Tag push event: {ref}")

        # Update project activity timestamp
        project_id = project_data.get('id')
        if project_id:
            try:
                project = Project.objects.get(project_id=project_id)
                project.last_webhook_at = timezone.now()
                project.save(update_fields=['last_webhook_at', 'updated_at'])
            except Project.DoesNotExist:
                pass

        # Mark webhook as processed
        if webhook_log:
            webhook_log.processed = True
            webhook_log.processed_at = timezone.now()
            webhook_log.save()

        return Response({
            'status': 'success',
            'message': 'Tag push event processed'
        })

    except Exception as e:
        logger.error(f"Error handling tag push: {str(e)}", exc_info=True)
        if webhook_log:
            webhook_log.error_message = str(e)
            webhook_log.save()
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== Reviews and Logs APIs ====================

@api_view(['GET'])
def list_reviews(request):
    """
    Get list of merge request reviews with filtering and pagination

    Query parameters:
        - project_id: Filter by project ID
        - status: Filter by status (pending, processing, completed, failed)
        - limit: Limit number of results (default: 20)
        - offset: Offset for pagination (default: 0)
        - search: Search in project name, MR title, or author name
    """
    try:
        # Get query parameters
        project_id = request.query_params.get('project_id')
        status_filter = request.query_params.get('status')
        search = request.query_params.get('search')
        limit = request.query_params.get('limit', 20)
        offset = request.query_params.get('offset', 0)

        # Convert limit and offset to integers
        try:
            limit = int(limit)
            offset = int(offset)
        except (ValueError, TypeError):
            limit = 20
            offset = 0

        # Start with all reviews
        reviews = MergeRequestReview.objects.all()

        # Apply filters
        if project_id:
            reviews = reviews.filter(project_id=project_id)

        if status_filter:
            reviews = reviews.filter(status=status_filter)

        if search:
            reviews = reviews.filter(
                models.Q(project_name__icontains=search) |
                models.Q(merge_request_title__icontains=search) |
                models.Q(author_name__icontains=search) |
                models.Q(merge_request_iid__icontains=search)
            )

        # Get total count for pagination
        total_count = reviews.count()

        # Apply ordering and pagination
        reviews = reviews.order_by('-created_at')
        reviews = reviews[offset:offset + limit]

        # Serialize data
        serializer = MergeRequestReviewSerializer(reviews, many=True)

        # Format response data to match frontend expectations
        formatted_reviews = []
        status_choices = dict(MergeRequestReview._meta.get_field('status').choices)

        for review in serializer.data:
            formatted_review = {
                'id': review['id'],
                'mrId': review['merge_request_iid'],
                'project': review['project_name'],
                'title': review['merge_request_title'],
                'author': review['author_name'],
                'authorEmail': review['author_email'],
                'status': review['status'],
                'statusText': status_choices.get(review['status'], review['status']).title(),
                'llmModel': 'GPT-4',  # Default value for now
                'issuesCount': 0 if not review['review_content'] else len([line for line in review['review_content'].split('\n') if line.strip()]),
                'score': review['review_score'],
                'sourceBranch': review['source_branch'],
                'targetBranch': review['target_branch'],
                'createdAt': review['created_at'],
                'completedAt': review['completed_at'],
                'mrUrl': f"https://gitlab.com/gitlab-instance/-/merge_requests/{review['merge_request_iid']}"  # Generic URL
            }
            formatted_reviews.append(formatted_review)

        return Response({
            'status': 'success',
            'count': len(formatted_reviews),
            'total': total_count,
            'results': formatted_reviews
        })

    except Exception as e:
        logger.error(f"Error getting reviews: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def list_logs(request):
    """
    Get list of webhook logs with filtering and pagination

    Query parameters:
        - project_id: Filter by project ID
        - event_type: Filter by event type
        - level: Filter by log level (INFO, WARNING, ERROR)
        - limit: Limit number of results (default: 20)
        - offset: Offset for pagination (default: 0)
        - search: Search in project name, event type, or message
    """
    try:
        # Get query parameters
        project_id = request.query_params.get('project_id')
        event_type = request.query_params.get('event_type')
        level = request.query_params.get('level')
        search = request.query_params.get('search')
        limit = request.query_params.get('limit', 20)
        offset = request.query_params.get('offset', 0)

        # Convert limit and offset to integers
        try:
            limit = int(limit)
            offset = int(offset)
        except (ValueError, TypeError):
            limit = 20
            offset = 0

        # Start with all logs
        logs = WebhookLog.objects.all()

        # Apply filters
        if project_id:
            logs = logs.filter(project_id=project_id)

        if event_type:
            logs = logs.filter(event_type=event_type)

        if level:
            # Level filtering based on calculated log level
            level = level.upper()
            if level == 'ERROR':
                logs = logs.filter(error_message__isnull=False)
            elif level == 'WARNING':
                # Filter logs that contain warning indicators
                logs = logs.filter(
                    models.Q(payload__icontains='warning') |
                    models.Q(payload__icontains='retry') |
                    models.Q(error_message__icontains='warning')
                )
            elif level == 'INFO':
                # Filter logs without error messages
                logs = logs.filter(error_message__isnull=True)
            # For other levels, we would need to store the level in the database
            # For now, return empty for unsupported levels

        if search:
            logs = logs.filter(
                models.Q(project_name__icontains=search) |
                models.Q(event_type__icontains=search) |
                models.Q(user_name__icontains=search) |
                models.Q(payload__icontains=search)
            )

        # Get total count for pagination
        total_count = logs.count()

        # Apply ordering and pagination
        logs = logs.order_by('-created_at')
        logs = logs[offset:offset + limit]

        # Serialize data
        serializer = WebhookLogSerializer(logs, many=True)

        # Format response data to match frontend expectations
        formatted_logs = []
        for log in serializer.data:
            # Determine log level based on content
            log_level = 'INFO'
            if log.get('error_message'):
                log_level = 'ERROR'
            elif 'warning' in str(log.get('payload', '')).lower() or 'retry' in str(log.get('payload', '')).lower():
                log_level = 'WARNING'

            # 解析请求头（使用新字段）
            request_headers = None
            try:
                if log.get('request_headers'):
                    import json
                    request_headers = json.loads(log['request_headers'])
            except (json.JSONDecodeError, TypeError):
                pass

            # 解析payload
            payload_data = {}
            try:
                if log.get('payload'):
                    payload_data = json.loads(log['payload'])
            except (json.JSONDecodeError, TypeError):
                payload_data = log.get('payload', {})

            formatted_log = {
                'id': log['id'],
                'timestamp': log['created_at'],
                'level': log_level,
                'event_type': log['event_type'],
                'project_name': log['project_name'],
                'merge_request_iid': log['merge_request_iid'],
                'user_name': log['user_name'],
                'user_email': log['user_email'],
                'source_branch': log['source_branch'],
                'target_branch': log['target_branch'],
                'message': f"收到 {log['event_type']} 事件 - 项目: {log['project_name']}",
                # 使用新的HTTP元数据字段
                'request_headers': request_headers,
                'request_body': payload_data,
                'request_body_raw': log.get('request_body_raw', ''),
                'remote_addr': log.get('remote_addr'),
                'user_agent': log.get('user_agent'),
                'request_id': log.get('request_id'),
                'response_status': 200 if log.get('processed') and not log.get('error_message') else 500 if log.get('error_message') else None,
                'response_body': {'status': 'success' if log.get('processed') and not log.get('error_message') else 'error'} if log.get('processed') or log.get('error_message') else None,
                'processing_details': payload_data,
                'error_message': log.get('error_message'),
                'details': str(payload_data),
                'processed': log.get('processed'),
                'processed_at': log.get('processed_at')
            }
            formatted_logs.append(formatted_log)

        return Response({
            'status': 'success',
            'count': len(formatted_logs),
            'total': total_count,
            'results': formatted_logs
        })

    except Exception as e:
        logger.error(f"Error getting logs: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== Mock APIs for Testing ====================

@api_view(['GET'])
def mock_reviews(request):
    """
    Mock API for reviews - returns sample review data for frontend testing
    """
    try:
        mock_data = [
            {
                'id': 1,
                'project_id': 456,
                'project_name': 'code-review-admin',
                'merge_request_iid': 123,
                'merge_request_title': 'feat: 添加配置管理页面',
                'source_branch': 'feature/config-management',
                'target_branch': 'main',
                'author_name': 'developer1',
                'author_email': 'dev1@example.com',
                'status': 'completed',
                'review_content': '代码审查完成，发现3个问题需要修复...',
                'review_score': 85,
                'files_reviewed': ['src/views/Config.vue', 'backend/apps/llm/serializers.py'],
                'total_files': 15,
                'created_at': '2025-11-05T10:30:00Z',
                'completed_at': '2025-11-05T10:45:00Z',
                'mr_url': 'https://gitlab.com/username/code-review-admin/-/merge_requests/123'
            },
            {
                'id': 2,
                'project_id': 456,
                'project_name': 'code-review-admin',
                'merge_request_iid': 122,
                'merge_request_title': 'fix: 修复序列化器配置数据解析问题',
                'source_branch': 'fix/serializer-parsing',
                'target_branch': 'main',
                'author_name': 'developer2',
                'author_email': 'dev2@example.com',
                'status': 'completed',
                'review_content': '修复成功，代码质量良好',
                'review_score': 95,
                'files_reviewed': ['backend/apps/llm/serializers.py'],
                'total_files': 5,
                'created_at': '2025-11-05T09:15:00Z',
                'completed_at': '2025-11-05T09:25:00Z',
                'mr_url': 'https://gitlab.com/username/code-review-admin/-/merge_requests/122'
            },
            {
                'id': 3,
                'project_id': 456,
                'project_name': 'code-review-admin',
                'merge_request_iid': 121,
                'merge_request_title': 'refactor: 重构LLM配置模块',
                'source_branch': 'refactor/llm-config',
                'target_branch': 'main',
                'author_name': 'developer1',
                'author_email': 'dev1@example.com',
                'status': 'failed',
                'review_content': '',
                'review_score': None,
                'files_reviewed': [],
                'total_files': 8,
                'error_message': 'LLM API调用超时',
                'created_at': '2025-11-04T16:45:00Z',
                'completed_at': '2025-11-04T16:50:00Z',
                'mr_url': 'https://gitlab.com/username/code-review-admin/-/merge_requests/121'
            }
        ]

        return Response({
            'status': 'success',
            'count': len(mock_data),
            'results': mock_data
        })

    except Exception as e:
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def mock_logs(request):
    """
    Mock API for logs - returns sample webhook log data for frontend testing
    """
    try:
        mock_data = [
            {
                'id': 1,
                'timestamp': '2025-11-05T10:35:23Z',
                'level': 'INFO',
                'event_type': 'Merge Request Hook',
                'project_id': 456,
                'project_name': 'code-review-admin',
                'merge_request_iid': 123,
                'user_name': 'developer1',
                'user_email': 'dev1@example.com',
                'source_branch': 'feature/config-management',
                'target_branch': 'main',
                'message': '收到新的 Merge Request webhook 事件',
                'payload': {
                    'object_kind': 'merge_request',
                    'user': {'name': 'developer1', 'email': 'dev1@example.com'},
                    'project': {'name': 'code-review-admin', 'id': 456},
                    'object_attributes': {
                        'iid': 123,
                        'title': 'feat: 添加配置管理页面',
                        'action': 'open',
                        'source_branch': 'feature/config-management',
                        'target_branch': 'main'
                    }
                },
                'processed': True,
                'processed_at': '2025-11-05T10:35:25Z',
                'error_message': None
            },
            {
                'id': 2,
                'timestamp': '2025-11-05T10:35:26Z',
                'level': 'INFO',
                'event_type': 'Review Processing',
                'project_id': 456,
                'project_name': 'code-review-admin',
                'merge_request_iid': 123,
                'user_name': 'system',
                'message': '启动代码审查引擎，使用 GPT-4 模型',
                'payload': {
                    'action': 'review_started',
                    'llm_model': 'GPT-4',
                    'total_files': 15
                },
                'processed': True,
                'processed_at': '2025-11-05T10:35:30Z',
                'error_message': None
            },
            {
                'id': 3,
                'timestamp': '2025-11-05T10:20:15Z',
                'level': 'WARNING',
                'event_type': 'LLM API Call',
                'project_id': 456,
                'project_name': 'code-review-admin',
                'merge_request_iid': 122,
                'user_name': 'system',
                'message': 'LLM API 调用失败，正在重试 (1/3)',
                'payload': {
                    'error': 'Rate limit exceeded',
                    'retry_after': 60,
                    'llm_provider': 'OpenAI'
                },
                'processed': True,
                'processed_at': '2025-11-05T10:20:20Z',
                'error_message': 'Rate limit exceeded. Retry after 60 seconds.'
            },
            {
                'id': 4,
                'timestamp': '2025-11-05T10:18:42Z',
                'level': 'ERROR',
                'event_type': 'GitLab API Error',
                'project_id': 456,
                'project_name': 'code-review-admin',
                'user_name': 'system',
                'message': 'GitLab API 认证失败',
                'payload': {
                    'error': '401 Unauthorized',
                    'message': 'Invalid token'
                },
                'processed': False,
                'processed_at': None,
                'error_message': '401 Unauthorized - Invalid or expired access token'
            }
        ]

        return Response({
            'status': 'success',
            'count': len(mock_data),
            'results': mock_data
        })

    except Exception as e:
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
