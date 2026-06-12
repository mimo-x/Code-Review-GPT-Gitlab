"""
Webhook 测试共享 fixtures
"""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    """提供 DRF APIClient 实例用于测试视图"""
    return APIClient()


@pytest.fixture
def webhook_payload():
    """标准 GitLab merge_request webhook payload"""
    return {
        "object_kind": "merge_request",
        "project": {
            "id": 1,
            "name": "test-project",
            "path_with_namespace": "org/test-project",
            "http_url": "https://gitlab.com/org/test-project.git",
            "namespace": "org",
        },
        "object_attributes": {
            "iid": 42,
            "title": "feat: add new feature",
            "source_branch": "feature/new-thing",
            "target_branch": "main",
            "action": "open",
            "description": "A test MR",
            "url": "https://gitlab.com/org/test-project/-/merge_requests/42",
            "author": {"name": "test-dev", "email": "test@example.com"},
            "last_commit": {
                "author": {"name": "test-dev", "email": "test@example.com"}
            },
        },
        "user": {"name": "test-dev", "email": "test@example.com"},
    }
