"""日志列表接口。"""
import json

import pytest
from rest_framework.test import APIClient

from apps.webhook.models import WebhookLog


@pytest.mark.django_db
def test_lists_logs_without_request_headers():
    WebhookLog.objects.create(
        event_type="merge_request", project_id=1, project_name="p", user_name="dev",
        source_branch="f", target_branch="main", request_headers="",
        payload=json.dumps({"object_kind": "merge_request"}),
    )
    response = APIClient().get("/api/webhook/logs/")
    assert response.status_code == 200
    assert "merge_request" in json.dumps(response.json(), ensure_ascii=False)
