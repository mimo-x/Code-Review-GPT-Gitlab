"""
Webhook 视图异常容错测试

验证 GitLab webhook 端点在各种异常场景下的容错能力，
确保不会因为内部错误导致 GitLab 收到非 200 响应（防止 GitLab 重试）。
"""
import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.db.utils import OperationalError


@pytest.mark.django_db
class TestWebhookErrorResilience:
    """Webhook 异常容错测试套件"""

    def test_payload_parsing_failure_does_not_crash(self, api_client):
        """
        发送无法解析的非 JSON 请求体，验证视图不崩溃。

        关键：gitlab_webhook 在解析 request.data 时使用 try/except，
        失败时回退到空 dict，不应抛出未捕获异常。
        """
        response = api_client.post(
            '/api/webhook/gitlab/',
            data=b'\xff\xfe\x00\x01invalid-bytes',
            content_type='application/octet-stream',
        )
        # GitLab webhook 总是返回 200，防止 GitLab 重试
        assert response.status_code == 200

    def test_database_exception_during_log_creation(
        self, api_client, webhook_payload
    ):
        """
        Mock 数据库写入异常，验证 create_initial_webhook_log 的
        fallback 机制不会导致视图崩溃。

        当数据库完全不可用时，日志无法写入是预期行为，
        关键是不能让异常传播到 GitLab webhook 响应。
        """
        with patch(
            'apps.webhook.views.WebhookLog.objects.create',
            side_effect=OperationalError("模拟数据库故障"),
        ):
            response = api_client.post(
                '/api/webhook/gitlab/',
                data=webhook_payload,
                format='json',
            )

        # 核心断言：即使数据库不可用，webhook 也不应崩溃
        # 返回 200 防止 GitLab 重试是更重要的事
        assert response.status_code == 200

    @patch('apps.webhook.views.GitlabService')
    def test_gitlab_config_missing_graceful_failure(
        self, mock_gitlab_svc, webhook_payload
    ):
        """
        当 GitLab 配置缺失时，审查线程应优雅失败而不是崩溃。

        模拟 GitlabService 初始化抛出 ImproperlyConfigured，
        验证 process_merge_request_review 将其标记为 failed 而非崩溃。
        """
        from django.core.exceptions import ImproperlyConfigured
        from apps.webhook.views import process_merge_request_review
        from apps.webhook.models import MergeRequestReview, Project

        mock_gitlab_svc.side_effect = ImproperlyConfigured(
            "未找到已激活的 GitLab 配置"
        )

        # 创建必要的数据库记录
        project = Project.objects.create(
            project_id=1,
            project_name='test-project',
            project_path='test/test-project',
            project_url='https://gitlab.com/test/test-project',
            namespace='test',
        )
        review = MergeRequestReview.objects.create(
            project_id=1,
            project_name='test-project',
            merge_request_iid=42,
            merge_request_title='Test MR',
            source_branch='feature/test',
            target_branch='main',
            author_name='tester',
            author_email='t@test.com',
            status='pending',
        )

        # 直接调用审查处理函数（同步执行，不通过线程）
        process_merge_request_review(1, 42, review.pk, webhook_payload)

        # 验证审查被标记为失败而非崩溃
        review.refresh_from_db()
        assert review.status == 'failed'
        assert 'GitLab' in (review.error_message or '')

    def test_webhook_returns_200_for_various_scenarios(
        self, api_client, webhook_payload
    ):
        """
        验证多种输入场景下 webhook 始终返回 200。

        GitLab 对非 200 响应会重试 webhook，返回 200 可防止
        重复处理和级联故障。
        """
        # 场景 1: 正常有效请求
        response = api_client.post(
            '/api/webhook/gitlab/',
            data=webhook_payload,
            format='json',
        )
        assert response.status_code == 200

        # 场景 2: 缺少 object_kind 的最小 payload
        minimal = {"project": {"id": 1}}
        response = api_client.post(
            '/api/webhook/gitlab/',
            data=minimal,
            format='json',
        )
        assert response.status_code == 200

        # 场景 3: 完全空 payload
        response = api_client.post(
            '/api/webhook/gitlab/',
            data={},
            format='json',
        )
        assert response.status_code == 200

    def test_webhook_log_created_on_all_paths(
        self, api_client, webhook_payload
    ):
        """
        验证无论处理成功或失败，WebhookLog 记录始终被创建。

        create_initial_webhook_log 在 try/except 外部调用，
        确保日志记录是 webhook 处理的第一步和最后保障。
        """
        from apps.webhook.models import WebhookLog

        initial_count = WebhookLog.objects.count()

        response = api_client.post(
            '/api/webhook/gitlab/',
            data=webhook_payload,
            format='json',
        )
        assert response.status_code == 200

        # 每次 webhook 调用都应该增加一条日志记录
        assert WebhookLog.objects.count() == initial_count + 1

        log_entry = WebhookLog.objects.latest('created_at')
        assert log_entry.event_type == 'merge_request'
        assert log_entry.project_id == 1
