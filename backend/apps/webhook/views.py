import json
import logging
import threading
import uuid
import time
from django.utils import timezone
from django.db import models, transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import WebhookLog, MergeRequestReview, Project, ProjectNotificationSetting
from .serializers import (
    WebhookLogSerializer,
    ProjectSerializer,
    ProjectListSerializer,
    ProjectUpdateSerializer,
    MergeRequestReviewSerializer,
    ProjectNotificationSettingSerializer,
    ProjectNotificationUpdateSerializer
)
from .services import ProjectService
from apps.review.services import GitlabService, ReviewService
from apps.common.logging_utils import get_logger, TimerContext

logger = logging.getLogger(__name__)



@api_view(['POST'])
def gitlab_webhook(request):
    """
    GitLab Webhook endpoint
    Handles incoming webhook events from GitLab

    优化版本：确保所有请求都被记录到webhook_logs表中，使用结构化日志
    """
    # 生成请求ID用于日志追踪
    request_id = str(uuid.uuid4())
    structured_logger = get_logger('webhook', request_id)

    # 立即创建初始日志记录，确保请求被记录
    webhook_log = create_initial_webhook_log(request)

    if webhook_log:
        structured_logger.info("Webhook事件接收成功", request_id=webhook_log.request_id)
    else:
        structured_logger.error("严重错误：无法创建Webhook日志记录", request_id=request_id)

    try:
        with transaction.atomic():
            # 提取payload和事件类型
            try:
                payload = request.data
            except Exception:
                payload = {}
                structured_logger.warning("请求数据解析失败")

            event_type = payload.get('object_kind', 'unknown')
            project_data = payload.get('project', {})
            project_id = project_data.get('id')
            project_name = project_data.get('name', '')

            # 记录Webhook入站日志
            structured_logger.log_webhook_inbound(
                event_type=event_type,
                project_id=project_id,
                project_name=project_name,
                mr_iid=payload.get('object_attributes', {}).get('iid')
            )

            # 更新日志记录中的事件类型（如果之前是unknown）
            if webhook_log and webhook_log.event_type == 'unknown' and event_type != 'unknown':
                webhook_log.event_type = event_type
                webhook_log.save(update_fields=['event_type'])
                structured_logger.log_database_operation(
                    operation="update",
                    table="webhook_logs",
                    success=True,
                    record_id=webhook_log.id,
                    field="event_type"
                )

            # Check or create project
            try:
                project, created = ProjectService.get_or_create_project(project_data)
                if created:
                    structured_logger.info(
                        "新增项目",
                        project_name=project.project_name,
                        project_id=project.project_id,
                        review_enabled=project.review_enabled
                    )
            except Exception as project_error:
                structured_logger.log_error_with_context(
                    project_error,
                    context={"operation": "project_creation", "project_id": project_id}
                )
                # 继续处理，不因为项目创建失败而停止

            # 使用统一的事件处理函数
            try:
                with TimerContext(structured_logger, f"handle_webhook_event"):
                    return handle_webhook_event(payload, webhook_log, project_id)
            except Exception as handler_error:
                structured_logger.log_error_with_context(
                    handler_error,
                    context={
                        "event_type": event_type,
                        "project_id": project_id,
                        "stage": "event_handler"
                    }
                )
                # 标记日志为处理失败
                if webhook_log:
                    webhook_log.processed = True
                    webhook_log.processed_at = timezone.now()
                    webhook_log.error_message = f"Handler error: {str(handler_error)}"
                    webhook_log.save(update_fields=['processed', 'processed_at', 'error_message'])
                    structured_logger.log_database_operation(
                        operation="update",
                        table="webhook_logs",
                        success=True,
                        record_id=webhook_log.id,
                        field="error_message"
                    )

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


def handle_webhook_event(payload, webhook_log, project_id):
    """
    统一的 webhook 事件处理函数

    处理流程：
    1. 检查项目是否存在且启用了审查
    2. 获取项目启用的事件规则
    3. 匹配 payload 与规则
    4. 如果匹配，启动审查
    5. 否则跳过并记录原因

    Args:
        payload: GitLab webhook payload
        webhook_log: WebhookLog 实例
        project_id: 项目ID

    Returns:
        Response: DRF Response 对象
    """
    from apps.llm.models import WebhookEventRule

    try:
        # 提取项目数据
        project_data = payload.get('project', {})
        project_name = project_data.get('name', '')
        event_type = payload.get('object_kind', 'unknown')

        logger.info(f"Processing webhook event: type={event_type}, project_id={project_id}")

        # 1. 检查项目是否启用审查
        if not ProjectService.is_review_enabled(project_id):
            logger.info(f"⏸️  Review is disabled for project {project_id}. Skipping.")

            if webhook_log:
                webhook_log.processed = True
                webhook_log.processed_at = timezone.now()
                webhook_log.error_message = "Review disabled for this project"
                webhook_log.save()

            return Response({
                'status': 'skipped',
                'message': 'Code review is disabled for this project. Enable it in project settings.'
            })

        # 2. 获取项目及其启用的事件规则
        try:
            project = Project.objects.get(project_id=project_id)
            enabled_event_ids = project.enabled_webhook_events_list

            if not enabled_event_ids:
                logger.info(f"⚠️  Project {project_id} has no enabled webhook event rules. Skipping.")

                if webhook_log:
                    webhook_log.processed = True
                    webhook_log.processed_at = timezone.now()
                    webhook_log.error_message = "No webhook event rules enabled for this project"
                    webhook_log.save()

                return Response({
                    'status': 'skipped',
                    'message': 'Project has no webhook event rules enabled. Configure event rules in project settings.'
                })

            # 3. 匹配事件规则
            enabled_rules = WebhookEventRule.objects.filter(
                id__in=enabled_event_ids,
                is_active=True
            )

            matched_rule = None
            for rule in enabled_rules:
                if rule.matches_payload(payload):
                    matched_rule = rule
                    logger.info(f"✅ Webhook payload matched rule: {rule.name} (ID: {rule.id}) for project {project_id}")
                    break

            if not matched_rule:
                logger.info(f"⏸️  Webhook payload did not match any enabled rules for project {project_id}. Skipping.")

                if webhook_log:
                    webhook_log.processed = True
                    webhook_log.processed_at = timezone.now()
                    webhook_log.error_message = "No matching webhook event rule found"
                    webhook_log.save()

                return Response({
                    'status': 'skipped',
                    'message': 'Webhook event does not match any of the project\'s enabled event rules.'
                })

            logger.info(f"🎯 Webhook event matched rule: {matched_rule.name} (type: {matched_rule.event_type})")

            # 4. 启动代码审查（目前只支持 merge_request 类型）
            if event_type == 'merge_request':
                return _start_merge_request_review(payload, webhook_log, project_id, project_name, matched_rule)
            else:
                # 其他事件类型暂时不支持
                logger.info(f"⚠️  Event type '{event_type}' matched rule but review is not yet implemented.")

                if webhook_log:
                    webhook_log.processed = True
                    webhook_log.processed_at = timezone.now()
                    webhook_log.error_message = f"Review not implemented for event type: {event_type}"
                    webhook_log.save()

                return Response({
                    'status': 'skipped',
                    'message': f'Review not yet implemented for event type: {event_type}'
                })

        except Project.DoesNotExist:
            logger.error(f"Project {project_id} not found")
            return Response(
                {'status': 'error', 'message': f'Project {project_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    except Exception as e:
        logger.error(f"Error handling webhook event: {str(e)}", exc_info=True)

        if webhook_log:
            webhook_log.processed = True
            webhook_log.processed_at = timezone.now()
            webhook_log.error_message = str(e)
            webhook_log.save()

        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _start_merge_request_review(payload, webhook_log, project_id, project_name, matched_rule):
    """
    启动 Merge Request 代码审查

    Args:
        payload: GitLab webhook payload
        webhook_log: WebhookLog 实例
        project_id: 项目ID
        project_name: 项目名称
        matched_rule: 匹配的事件规则

    Returns:
        Response: DRF Response 对象
    """
    try:
        object_attributes = payload.get('object_attributes', {})
        merge_request_iid = object_attributes.get('iid')

        logger.info(f"Starting MR review: Project {project_id}, MR #{merge_request_iid}, Rule: {matched_rule.name}")

        # 创建审查记录
        request_id = webhook_log.request_id if webhook_log else str(uuid.uuid4())
        review = MergeRequestReview.objects.create(
            project_id=project_id,
            project_name=project_name,
            merge_request_iid=merge_request_iid,
            merge_request_title=object_attributes.get('title', ''),
            source_branch=object_attributes.get('source_branch', ''),
            target_branch=object_attributes.get('target_branch', ''),
            author_name=object_attributes.get('last_commit', {}).get('author', {}).get('name', ''),
            author_email=object_attributes.get('last_commit', {}).get('author', {}).get('email', ''),
            status='pending',
            request_id=request_id,
            review_content=''
        )

        # 启动审查线程（传递 matched_rule）
        def launch_review_thread():
            thread = threading.Thread(
                target=process_merge_request_review,
                args=(project_id, merge_request_iid, review.pk, payload, matched_rule)
            )
            thread.daemon = True
            thread.start()

        transaction.on_commit(launch_review_thread)

        # 标记 webhook 日志为已处理
        if webhook_log:
            webhook_log.processed = True
            webhook_log.processed_at = timezone.now()
            webhook_log.save()

        return Response({'status': 'success', 'message': 'Review process started'})

    except Exception as e:
        logger.error(f"Error starting MR review: {str(e)}", exc_info=True)

        if webhook_log:
            webhook_log.error_message = str(e)
            webhook_log.save()

        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )





def process_merge_request_review(project_id, merge_request_iid, review_id, payload, matched_rule=None):
    """
    Process merge request review in a separate thread
    新版本：整合报告生成器和多渠道通知分发器，使用结构化日志

    Args:
        project_id: 项目ID
        merge_request_iid: MR IID
        review_id: 审查记录ID
        payload: Webhook payload
        matched_rule: 匹配的 WebhookEventRule 实例（用于获取自定义 prompt）
    """
    import time
    from django.conf import settings

    # 获取request_id用于日志追踪
    try:
        review = MergeRequestReview.objects.get(pk=review_id)
    except MergeRequestReview.DoesNotExist:
        logger.error("MergeRequestReview %s not found when starting review processing", review_id)
        return

    request_id = review.request_id or str(uuid.uuid4())
    structured_logger = get_logger('mr_review', request_id)

    structured_logger.log_thread_start(project_id, merge_request_iid)

    try:
        # 获取MR基本信息
        project_data = payload.get('project', {})
        mr_data = payload.get('object_attributes', {})
        mr_info = {
            'project_id': project_id,
            'mr_iid': merge_request_iid,
            'project_name': project_data.get('name', '未知项目'),
            'title': mr_data.get('title', '未知MR'),
            'author': mr_data.get('author', {}).get('name', '未知作者'),
            'description': mr_data.get('description', ''),
            'url': mr_data.get('url', ''),
        }

        # 更新审查记录状态
        review.status = 'processing'
        review.save()
        structured_logger.log_database_operation(
            operation="update",
            table="merge_request_reviews",
            success=True,
            record_id=review_id,
            field="status"
        )

        # 初始化服务
        gitlab_service = GitlabService(request_id=request_id)

        # 获取MR变更信息
        with TimerContext(structured_logger, "get_mr_changes"):
            changes = gitlab_service.get_merge_request_changes(project_id, merge_request_iid)

        if not changes:
            structured_logger.error("未找到MR变更信息")
            review.status = 'failed'
            review.error_message = '未找到MR变更信息'
            review.save()
            return

        # 统计文件和变更信息
        file_count = len(changes.get('changes', []))
        changes_count = sum(
            change.get('diff', '').count('\n')
            for change in changes.get('changes', [])
        )
        mr_info.update({
            'file_count': file_count,
            'changes_count': changes_count
        })

        structured_logger.info(f"获取到 {file_count} 个文件变更，{changes_count} 行代码变更")

        # 判断是否使用Mock模式
        is_mock_mode = getattr(settings, 'CODE_REVIEW_MOCK_MODE', False)
        structured_logger.info(f"使用模式: {'Mock' if is_mock_mode else 'Real LLM'}")

        # 生成报告
        if is_mock_mode:
            # Mock模式
            from apps.review.report_generator import ReportGenerator
            with TimerContext(structured_logger, "generate_mock_report"):
                report_generator = ReportGenerator(request_id=request_id)
                report_data = report_generator.generate_mock(mr_info)

            llm_provider = 'mock'
            llm_model = 'mock'

            structured_logger.log_report_generation(
                is_mock=True,
                score=report_data['metadata'].get('score'),
                file_count=file_count,
                success=True
            )
        else:
            # 真实 Claude CLI 模式
            from apps.llm.services import LLMService
            from apps.review.report_generator import ReportGenerator
            from apps.review.repository_manager import RepositoryManager

            # 初始化仓库管理器
            repo_manager = RepositoryManager(request_id=request_id)

            # 获取项目 URL 和访问令牌
            project_url = project_data.get('git_http_url') or project_data.get('http_url')

            # 从 GitLab 配置获取访问令牌（使用已导入的 GitlabService）
            # GitlabService 已经在文件顶部从 apps.review.services 导入
            # 它的 _load_config 方法会从 GitLabConfig 数据库表加载配置
            gitlab_svc = GitlabService(request_id=request_id)
            access_token = gitlab_svc.private_token  # 使用 private_token 属性

            structured_logger.info(f"准备克隆项目: {project_url}")

            # 克隆或更新仓库
            with TimerContext(structured_logger, "clone_or_update_repository"):
                success, repo_path, clone_error = repo_manager.get_or_clone_repository(
                    project_url=project_url,
                    project_id=project_id,
                    access_token=access_token
                )

            if not success:
                structured_logger.error(f"仓库克隆失败: {clone_error}")
                review.status = 'failed'
                review.error_message = f'仓库克隆失败: {clone_error}'
                review.save()
                return

            structured_logger.info(f"仓库路径: {repo_path}")

            # 切换到 MR 分支
            source_branch = mr_data.get('source_branch', '')
            target_branch = mr_data.get('target_branch', 'main')

            with TimerContext(structured_logger, "checkout_merge_request"):
                success, checkout_error = repo_manager.checkout_merge_request(
                    repo_path=repo_path,
                    mr_iid=merge_request_iid,
                    source_branch=source_branch,
                    target_branch=target_branch
                )

            if not success:
                structured_logger.error(f"分支切换失败: {checkout_error}")
                review.status = 'failed'
                review.error_message = f'分支切换失败: {checkout_error}'
                review.save()
                return

            # 获取提交范围
            success, commit_range, range_error = repo_manager.get_commit_range(
                repo_path=repo_path,
                target_branch=target_branch
            )

            if not success:
                structured_logger.warning(f"获取提交范围失败: {range_error}，使用默认范围")
                commit_range = "HEAD~1..HEAD"

            structured_logger.info(f"提交范围: {commit_range}")

            # 更新 MR 信息
            mr_info.update({
                'source_branch': source_branch,
                'target_branch': target_branch,
            })

            # 获取项目自定义 Prompt（如果配置了）
            custom_prompt = None
            if matched_rule:
                try:
                    from .models import ProjectWebhookEventPrompt
                    prompt_config = ProjectWebhookEventPrompt.objects.filter(
                        project__project_id=project_id,
                        event_rule=matched_rule,
                        use_custom=True
                    ).select_related('event_rule').first()

                    if prompt_config and prompt_config.custom_prompt:
                        # 渲染 prompt 模板，替换占位符
                        custom_prompt = prompt_config.render_prompt(mr_info)
                        structured_logger.info(f"使用项目自定义 Prompt (Event: {matched_rule.name}, 长度: {len(custom_prompt)})")
                    else:
                        structured_logger.info("使用系统默认 Prompt")
                except Exception as e:
                    structured_logger.warning(f"获取自定义 Prompt 失败: {e}，使用系统默认")

            # 调用 LLM 进行代码审查（使用 Claude CLI）
            llm_service = LLMService(request_id=request_id)
            llm_start_time = time.time()

            llm_result = llm_service.review_code(
                code_context=None,  # 不再需要
                mr_info=mr_info,
                repo_path=repo_path,
                commit_range=commit_range,
                custom_prompt=custom_prompt  # 传递自定义 prompt
            )

            llm_duration = time.time() - llm_start_time

            # 检查审查结果
            if isinstance(llm_result, str):
                # 错误消息
                structured_logger.error(f"代码审查失败: {llm_result}")
                review.status = 'failed'
                review.error_message = llm_result
                review.save()
                return

            # 成功获取审查结果（字典格式）
            llm_provider = 'claude-cli'
            llm_model = 'claude-sonnet-4-5'  # Claude CLI 使用的模型

            # 提取审查内容和元数据
            review_content = llm_result.get('content', '')
            review_score = llm_result.get('score', 0)
            # duration_ms 和 token_usage 保存在 metadata 中，这里不需要单独提取

            structured_logger.log_llm_call(
                provider=llm_provider,
                model=llm_model,
                success=True,
                duration=llm_duration,
                prompt_length=0,  # Claude CLI 不返回 prompt 长度
                response_length=len(review_content)
            )

            # 构建报告数据（兼容现有格式）
            report_data = {
                'content': review_content,
                'metadata': llm_result.get('metadata', {}),
            }

            structured_logger.log_report_generation(
                is_mock=False,
                score=review_score,
                file_count=file_count,
                success=True
            )

        # 更新审查记录
        review.review_content = report_data['content']
        review.review_score = report_data['metadata'].get('score', 0)
        review.files_reviewed = [change.get('new_path') for change in changes.get('changes', [])]
        review.total_files = file_count
        review.llm_provider = llm_provider
        review.llm_model = llm_model
        review.is_mock = is_mock_mode
        review.status = 'completed'
        review.completed_at = timezone.now()
        review.save()

        structured_logger.log_database_operation(
            operation="update",
            table="merge_request_reviews",
            success=True,
            record_id=review_id,
            fields=["content", "score", "status", "metadata"]
        )

        structured_logger.info(f"报告生成完成 - 评分:{review.review_score}, 模型:{llm_model}")

        # 分发通知到各个渠道
        from apps.response.notification_dispatcher import NotificationDispatcher
        notification_dispatcher = NotificationDispatcher(request_id=request_id)

        with TimerContext(structured_logger, "notification_dispatch"):
            notification_result = notification_dispatcher.dispatch(
                report_data,
                mr_info,
                project_id=project_id
            )

        # 更新通知结果
        review.notification_sent = notification_result.get('success', False)
        review.notification_result = json.dumps(notification_result, ensure_ascii=False)
        review.save()

        structured_logger.log_notification_dispatch(
            total_channels=notification_result.get('total_channels', 0),
            success_channels=notification_result.get('success_channels', 0),
            failed_channels=notification_result.get('failed_channels', 0),
            duration=notification_result.get('results', [{}])[0].get('response_time', 0)
        )

        structured_logger.log_business_metric(
            "mr_review_completed",
            value={
                "score": review.review_score,
                "files": file_count,
                "duration": notification_result.get('results', [{}])[0].get('response_time', 0),
                "notification_success": notification_result.get('success', False)
            }
        )

    except Exception as e:
        structured_logger.log_error_with_context(
            e,
            context={
                "operation": "mr_review_processing",
                "project_id": project_id,
                "mr_iid": merge_request_iid
            }
        )

        try:
            review.status = 'failed'
            review.error_message = str(e)
            review.save()
        except:
            pass


def build_code_context(changes):
    """
    构建代码上下文用于LLM审查
    """
    context_parts = []

    for change in changes.get('changes', []):
        file_path = change.get('new_path') or change.get('old_path', '')
        diff = change.get('diff', '')

        if diff:
            context_parts.append(f"## 文件: {file_path}\n```diff\n{diff}\n```")

    return "\n\n".join(context_parts)


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


@api_view(['GET'])
def get_project_notifications(request, project_id):
    """获取项目已启用的通知通道"""
    try:
        project = Project.objects.get(project_id=project_id)
        settings = ProjectNotificationSetting.objects.filter(
            project=project,
            enabled=True,
            channel__is_active=True
        ).select_related('channel')

        serializer = ProjectNotificationSettingSerializer(settings, many=True)

        return Response({
            'status': 'success',
            'gitlab_comment_enabled': project.gitlab_comment_notifications_enabled,
            'channels': serializer.data
        })

    except Project.DoesNotExist:
        return Response(
            {'status': 'error', 'message': f'Project {project_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error getting project notifications: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def update_project_notifications(request, project_id):
    """更新项目通知通道选择"""
    try:
        project = Project.objects.get(project_id=project_id)

        serializer = ProjectNotificationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        channel_ids = validated.get('channel_ids')
        gitlab_enabled = validated.get('gitlab_comment_enabled')

        if gitlab_enabled is not None:
            project.gitlab_comment_notifications_enabled = gitlab_enabled
            project.save(update_fields=['gitlab_comment_notifications_enabled', 'updated_at'])

        if channel_ids is not None:
            ProjectNotificationSetting.objects.filter(project=project).exclude(channel_id__in=channel_ids).update(enabled=False)

            for channel_id in channel_ids:
                ProjectNotificationSetting.objects.update_or_create(
                    project=project,
                    channel_id=channel_id,
                    defaults={'enabled': True}
                )

        refreshed = ProjectNotificationSetting.objects.filter(
            project=project,
            enabled=True,
            channel__is_active=True
        ).select_related('channel')

        response_serializer = ProjectNotificationSettingSerializer(refreshed, many=True)

        return Response({
            'status': 'success',
            'gitlab_comment_enabled': project.gitlab_comment_notifications_enabled,
            'channels': response_serializer.data
        })

    except Project.DoesNotExist:
        return Response(
            {'status': 'error', 'message': f'Project {project_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error updating project notifications: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_project_webhook_events(request, project_id):
    """获取项目启用的webhook事件规则ID列表"""
    try:
        from apps.llm.models import WebhookEventRule

        project = Project.objects.get(project_id=project_id)

        # 获取项目配置的事件ID列表
        enabled_event_ids = project.enabled_webhook_events_list

        # 过滤掉已被删除的事件规则
        if enabled_event_ids:
            valid_event_ids = list(WebhookEventRule.objects.filter(
                id__in=enabled_event_ids
            ).values_list('id', flat=True))

            # 如果有无效的ID，自动清理并保存
            if set(valid_event_ids) != set(enabled_event_ids):
                project.enabled_webhook_events_list = valid_event_ids
                project.save(update_fields=['enabled_webhook_events'])
                logger.info(f"Cleaned up invalid event IDs for project {project_id}: "
                           f"removed {set(enabled_event_ids) - set(valid_event_ids)}")

            enabled_event_ids = valid_event_ids

        return Response({
            'status': 'success',
            'enabled_event_ids': enabled_event_ids
        })

    except Project.DoesNotExist:
        return Response(
            {'status': 'error', 'message': f'Project {project_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error getting project webhook events: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def update_project_webhook_events(request, project_id):
    """更新项目启用的webhook事件规则"""
    try:
        from .serializers import ProjectWebhookEventsUpdateSerializer

        project = Project.objects.get(project_id=project_id)

        serializer = ProjectWebhookEventsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        event_ids = validated.get('event_ids', [])
        project.enabled_webhook_events_list = event_ids
        project.save(update_fields=['enabled_webhook_events', 'updated_at'])

        return Response({
            'status': 'success',
            'message': 'Webhook事件配置已更新',
            'enabled_event_ids': project.enabled_webhook_events_list
        })

    except Project.DoesNotExist:
        return Response(
            {'status': 'error', 'message': f'Project {project_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error updating project webhook events: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_project_webhook_event_prompts(request, project_id):
    """
    获取项目的所有 Webhook 事件 Prompt 配置

    GET /api/webhook/projects/{project_id}/webhook-event-prompts/

    返回格式:
    {
        "status": "success",
        "prompts": [
            {
                "id": 1,
                "event_rule": 1,
                "event_rule_name": "MR 创建",
                "event_rule_type": "mr_open",
                "custom_prompt": "请详细审查...",
                "use_custom": true
            }
        ]
    }
    """
    try:
        from .serializers import ProjectWebhookEventPromptSerializer
        from .models import ProjectWebhookEventPrompt

        project = Project.objects.get(project_id=project_id)

        # 获取项目启用的事件规则
        enabled_event_ids = project.enabled_webhook_events_list

        # 查询现有的 prompt 配置
        prompts = ProjectWebhookEventPrompt.objects.filter(
            project=project,
            event_rule_id__in=enabled_event_ids
        ).select_related('event_rule')

        # 为启用但没有 prompt 配置的事件创建空配置
        existing_event_ids = set(prompts.values_list('event_rule_id', flat=True))
        missing_event_ids = set(enabled_event_ids) - existing_event_ids

        if missing_event_ids:
            from apps.llm.models import WebhookEventRule
            for event_id in missing_event_ids:
                try:
                    event_rule = WebhookEventRule.objects.get(id=event_id)
                    ProjectWebhookEventPrompt.objects.create(
                        project=project,
                        event_rule=event_rule,
                        custom_prompt='',
                        use_custom=False
                    )
                except WebhookEventRule.DoesNotExist:
                    logger.warning(f"Event rule {event_id} not found when creating prompt config")
                    continue

            # 重新查询以包含新创建的配置
            prompts = ProjectWebhookEventPrompt.objects.filter(
                project=project,
                event_rule_id__in=enabled_event_ids
            ).select_related('event_rule')

        serializer = ProjectWebhookEventPromptSerializer(prompts, many=True)

        return Response({
            'status': 'success',
            'prompts': serializer.data
        })

    except Project.DoesNotExist:
        return Response(
            {'status': 'error', 'message': f'Project {project_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error getting project webhook event prompts: {str(e)}", exc_info=True)
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def update_project_webhook_event_prompt(request, project_id):
    """
    更新项目的单个 Webhook 事件 Prompt 配置

    POST /api/webhook/projects/{project_id}/webhook-event-prompts/update/

    请求体:
    {
        "event_rule_id": 1,
        "custom_prompt": "请详细审查该 MR...",
        "use_custom": true
    }
    """
    try:
        from .serializers import ProjectWebhookEventPromptUpdateSerializer, ProjectWebhookEventPromptSerializer
        from .models import ProjectWebhookEventPrompt

        project = Project.objects.get(project_id=project_id)

        serializer = ProjectWebhookEventPromptUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        event_rule_id = validated['event_rule_id']
        custom_prompt = validated.get('custom_prompt', '')
        use_custom = validated.get('use_custom', False)

        # 获取或创建配置
        prompt_config, created = ProjectWebhookEventPrompt.objects.update_or_create(
            project=project,
            event_rule_id=event_rule_id,
            defaults={
                'custom_prompt': custom_prompt,
                'use_custom': use_custom
            }
        )

        result_serializer = ProjectWebhookEventPromptSerializer(prompt_config)

        return Response({
            'status': 'success',
            'message': 'Prompt 配置已更新',
            'prompt': result_serializer.data
        })

    except Project.DoesNotExist:
        return Response(
            {'status': 'error', 'message': f'Project {project_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error updating project webhook event prompt: {str(e)}", exc_info=True)
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

        # 预先查询项目信息以获取 project_url
        project_ids = list(set(review.project_id for review in reviews))
        projects = {project.project_id: project for project in Project.objects.filter(project_id__in=project_ids)}

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
                'mrUrl': f"{projects.get(review['project_id']).project_url}/-/merge_requests/{review['merge_request_iid']}" if projects.get(review['project_id']) and projects.get(review['project_id']).project_url else None
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
