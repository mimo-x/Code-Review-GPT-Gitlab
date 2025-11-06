#!/usr/bin/env python3
"""
简单的webhook测试脚本
直接调用Django视图函数来测试优化后的webhook接口
"""

import os
import sys
import json
from unittest.mock import Mock

# 添加Django项目路径
sys.path.append('backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from apps.webhook.views import gitlab_webhook
from apps.webhook.models import WebhookLog
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request

def test_webhook_request(test_name, payload_data, headers=None):
    """测试单个webhook请求"""
    print(f"\n🧪 测试: {test_name}")
    print("=" * 50)

    # 创建请求工厂
    factory = APIRequestFactory()

    # 创建POST请求
    request = factory.post(
        '/api/webhook/gitlab/',
        data=payload_data,
        format='json',
        **(headers or {})
    )

    # 获取初始日志数量
    initial_count = WebhookLog.objects.count()
    print(f"处理前日志数量: {initial_count}")

    try:
        # 调用webhook视图
        response = gitlab_webhook(Request(request))

        # 检查响应
        print(f"响应状态码: {response.status_code}")
        print(f"响应数据: {response.data}")

        # 检查日志数量
        final_count = WebhookLog.objects.count()
        print(f"处理后日志数量: {final_count}")

        # 获取最新日志
        latest_log = WebhookLog.objects.order_by('-created_at').first()
        if latest_log and final_count > initial_count:
            print(f"✅ 新日志已创建")
            print(f"   请求ID: {latest_log.request_id}")
            print(f"   事件类型: {latest_log.event_type}")
            print(f"   项目名称: {latest_log.project_name}")
            print(f"   客户端IP: {latest_log.remote_addr}")
            print(f"   User-Agent: {latest_log.user_agent}")
            print(f"   处理状态: {latest_log.processed}")
            print(f"   错误信息: {latest_log.error_message}")
            print(f"   Payload大小: {len(latest_log.payload)} 字符")
            print(f"   Headers字段存在: {bool(latest_log.request_headers)}")
            print(f"   请求体原始数据存在: {bool(latest_log.request_body_raw)}")
        else:
            print("❌ 未创建新日志记录")

    except Exception as e:
        print(f"❌ 处理异常: {str(e)}")

def main():
    """运行所有测试"""
    print("🚀 开始测试优化后的webhook接口")
    print("目标: 验证所有请求都会被记录到webhook_logs表中")

    # 测试用例1: 正常的merge request
    test_webhook_request(
        "正常的Merge Request事件",
        {
            "object_kind": "merge_request",
            "project": {
                "id": 123,
                "name": "test-project"
            },
            "user": {
                "name": "test-user",
                "email": "test@example.com"
            },
            "object_attributes": {
                "iid": 1,
                "title": "Test MR",
                "action": "open",
                "source_branch": "feature/test",
                "target_branch": "main"
            }
        },
        {
            'HTTP_X_GITLAB_TOKEN': 'test-token',
            'HTTP_USER_AGENT': 'Test-Webhook-Client/1.0',
            'REMOTE_ADDR': '127.0.0.1'
        }
    )

    # 测试用例2: 无效payload
    test_webhook_request(
        "无效的payload（缺少项目信息）",
        {
            "object_kind": "push",
            "invalid_field": "test"
        }
    )

    # 测试用例3: 未知事件类型
    test_webhook_request(
        "未知的事件类型",
        {
            "object_kind": "unknown_custom_event",
            "project": {
                "id": 456,
                "name": "another-project"
            }
        }
    )

    print("\n" + "=" * 60)
    print("🎉 测试完成！")
    print("\n📊 验证结果:")

    # 统计总日志数
    total_logs = WebhookLog.objects.count()
    print(f"  总日志记录数: {total_logs}")

    # 显示最近有请求ID的日志（使用新功能创建的）
    recent_logs_with_id = WebhookLog.objects.filter(
        request_id__isnull=False
    ).order_by('-created_at')[:5]

    print(f"  使用新功能创建的日志数: {len(recent_logs_with_id)}")

    for log in recent_logs_with_id:
        status = "✅" if not log.error_message else "❌"
        print(f"    {status} {log.request_id[:8]}... | {log.event_type} | {log.project_name}")

    print("\n🔍 检查要点:")
    print("  1. 所有测试用例都应该创建了新的日志记录")
    print("  2. 新日志应该有唯一的request_id")
    print("  3. HTTP元数据（IP、User-Agent等）应该被正确记录")
    print("  4. 即使处理失败，请求也应该被记录")

if __name__ == "__main__":
    main()