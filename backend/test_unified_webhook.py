#!/usr/bin/env python
"""
测试统一的 webhook 事件处理逻辑
"""
import os
import sys
import django

# 设置 Django 环境
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.webhook.models import Project, WebhookLog
from apps.llm.models import WebhookEventRule
from apps.webhook.views import handle_webhook_event
from django.test import RequestFactory

def test_unified_webhook_handling():
    print("=== 测试统一的 Webhook 事件处理逻辑 ===\n")

    # 准备测试数据
    project = Project.objects.get(project_id=1)
    mr_create_rule = WebhookEventRule.objects.get(event_type='mr_open')
    mr_update_rule = WebhookEventRule.objects.get(event_type='mr_update')

    print(f"项目: {project.project_name} (ID: {project.project_id})")
    print(f"review_enabled: {project.review_enabled}")
    print(f"启用的规则: {project.enabled_webhook_events_list}")
    print()

    # 测试用例 1: MR 创建事件
    print("--- 测试用例 1: MR 创建事件 (action=open) ---")
    mr_open_payload = {
        "object_kind": "merge_request",
        "object_attributes": {
            "action": "open",
            "iid": 101,
            "title": "Test MR Open - Unified Handler",
            "source_branch": "feature-unified",
            "target_branch": "main",
            "last_commit": {
                "author": {
                    "name": "Test User",
                    "email": "test@example.com"
                }
            }
        },
        "project": {
            "id": 1,
            "name": "code-review-test"
        }
    }

    webhook_log_1 = WebhookLog.objects.create(
        event_type='merge_request',
        project_id=1,
        project_name='code-review-test',
        merge_request_iid=101,
        user_name='Test User',
        user_email='test@example.com',
        source_branch='feature-unified',
        target_branch='main',
        payload_dict=mr_open_payload
    )

    response_1 = handle_webhook_event(mr_open_payload, webhook_log_1, 1)
    print(f"响应状态: {response_1.status_code}")
    print(f"响应数据: {response_1.data}")
    webhook_log_1.refresh_from_db()
    print(f"Webhook日志: processed={webhook_log_1.processed}, error={webhook_log_1.error_message}")
    print()

    # 测试用例 2: MR 更新事件
    print("--- 测试用例 2: MR 更新事件 (action=update) ---")
    mr_update_payload = {
        "object_kind": "merge_request",
        "object_attributes": {
            "action": "update",
            "iid": 102,
            "title": "Test MR Update - Unified Handler",
            "source_branch": "feature-update",
            "target_branch": "main",
            "last_commit": {
                "author": {
                    "name": "Test User",
                    "email": "test@example.com"
                }
            }
        },
        "project": {
            "id": 1,
            "name": "code-review-test"
        }
    }

    webhook_log_2 = WebhookLog.objects.create(
        event_type='merge_request',
        project_id=1,
        project_name='code-review-test',
        merge_request_iid=102,
        user_name='Test User',
        user_email='test@example.com',
        source_branch='feature-update',
        target_branch='main',
        payload_dict=mr_update_payload
    )

    response_2 = handle_webhook_event(mr_update_payload, webhook_log_2, 1)
    print(f"响应状态: {response_2.status_code}")
    print(f"响应数据: {response_2.data}")
    webhook_log_2.refresh_from_db()
    print(f"Webhook日志: processed={webhook_log_2.processed}, error={webhook_log_2.error_message}")
    print()

    # 测试用例 3: MR 合并事件（不应该匹配）
    print("--- 测试用例 3: MR 合并事件 (action=merge) - 不应该匹配 ---")
    mr_merge_payload = {
        "object_kind": "merge_request",
        "object_attributes": {
            "action": "merge",
            "iid": 103,
            "title": "Test MR Merge - Should Not Match",
            "source_branch": "feature-merge",
            "target_branch": "main",
            "last_commit": {
                "author": {
                    "name": "Test User",
                    "email": "test@example.com"
                }
            }
        },
        "project": {
            "id": 1,
            "name": "code-review-test"
        }
    }

    webhook_log_3 = WebhookLog.objects.create(
        event_type='merge_request',
        project_id=1,
        project_name='code-review-test',
        merge_request_iid=103,
        user_name='Test User',
        user_email='test@example.com',
        source_branch='feature-merge',
        target_branch='main',
        payload_dict=mr_merge_payload
    )

    response_3 = handle_webhook_event(mr_merge_payload, webhook_log_3, 1)
    print(f"响应状态: {response_3.status_code}")
    print(f"响应数据: {response_3.data}")
    webhook_log_3.refresh_from_db()
    print(f"Webhook日志: processed={webhook_log_3.processed}, error={webhook_log_3.error_message}")
    print()

    # 测试用例 4: Push 事件（暂不支持）
    print("--- 测试用例 4: Push 事件 - 暂不支持 ---")
    push_payload = {
        "object_kind": "push",
        "ref": "refs/heads/main",
        "project": {
            "id": 1,
            "name": "code-review-test"
        }
    }

    webhook_log_4 = WebhookLog.objects.create(
        event_type='push',
        project_id=1,
        project_name='code-review-test',
        user_name='Test User',
        user_email='test@example.com',
        source_branch='main',
        target_branch='',
        payload_dict=push_payload
    )

    response_4 = handle_webhook_event(push_payload, webhook_log_4, 1)
    print(f"响应状态: {response_4.status_code}")
    print(f"响应数据: {response_4.data}")
    webhook_log_4.refresh_from_db()
    print(f"Webhook日志: processed={webhook_log_4.processed}, error={webhook_log_4.error_message}")
    print()

    # 测试用例 5: 没有启用规则的项目
    print("--- 测试用例 5: 项目没有启用事件规则 ---")
    empty_project = Project.objects.get(project_id=2)
    print(f"项目: {empty_project.project_name}, 启用规则: {empty_project.enabled_webhook_events_list}")

    empty_payload = {
        "object_kind": "merge_request",
        "object_attributes": {
            "action": "open",
            "iid": 104,
            "title": "Test Empty Project",
            "source_branch": "feature",
            "target_branch": "main",
            "last_commit": {
                "author": {
                    "name": "Test User",
                    "email": "test@example.com"
                }
            }
        },
        "project": {
            "id": 2,
            "name": "webhook-test-new"
        }
    }

    webhook_log_5 = WebhookLog.objects.create(
        event_type='merge_request',
        project_id=2,
        project_name='webhook-test-new',
        merge_request_iid=104,
        user_name='Test User',
        user_email='test@example.com',
        source_branch='feature',
        target_branch='main',
        payload_dict=empty_payload
    )

    response_5 = handle_webhook_event(empty_payload, webhook_log_5, 2)
    print(f"响应状态: {response_5.status_code}")
    print(f"响应数据: {response_5.data}")
    webhook_log_5.refresh_from_db()
    print(f"Webhook日志: processed={webhook_log_5.processed}, error={webhook_log_5.error_message}")
    print()

    # 清理测试数据
    print("--- 清理测试数据 ---")
    WebhookLog.objects.filter(id__in=[
        webhook_log_1.id, webhook_log_2.id, webhook_log_3.id,
        webhook_log_4.id, webhook_log_5.id
    ]).delete()
    print("测试数据已清理")
    print()

    print("=== 测试完成 ===")

if __name__ == '__main__':
    test_unified_webhook_handling()
