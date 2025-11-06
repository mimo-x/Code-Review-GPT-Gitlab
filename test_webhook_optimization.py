#!/usr/bin/env python3
"""
测试优化后的webhook接口
验证所有请求都会被记录到webhook_logs表中
"""

import requests
import json
import time
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

def test_webhook_logging():
    """测试各种webhook请求是否都被正确记录"""

    test_cases = [
        {
            "name": "正常的Merge Request事件",
            "payload": {
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
            }
        },
        {
            "name": "无效的payload（缺少必要字段）",
            "payload": {
                "object_kind": "push"
            }
        },
        {
            "name": "未知的事件类型",
            "payload": {
                "object_kind": "unknown_event",
                "project": {
                    "id": 456,
                    "name": "another-project"
                }
            }
        },
        {
            "name": "格式错误的payload",
            "payload": "invalid json"
        }
    ]

    results = []

    for i, test_case in enumerate(test_cases):
        logger.info(f"测试用例 {i+1}: {test_case['name']}")

        try:
            # 发送webhook请求
            response = requests.post(
                f"{BASE_URL}/api/webhook/gitlab/",
                json=test_case["payload"],
                headers={
                    "Content-Type": "application/json",
                    "X-Gitlab-Token": "test-token",
                    "User-Agent": "Test-Webhook-Client"
                }
            )

            status_code = response.status_code
            response_data = response.json() if response.content else {}

            logger.info(f"  响应状态: {status_code}")
            logger.info(f"  响应数据: {response_data}")

        except Exception as e:
            logger.error(f"  请求失败: {str(e)}")
            status_code = 0
            response_data = {"error": str(e)}

        results.append({
            "test_name": test_case["name"],
            "status_code": status_code,
            "response": response_data
        })

        # 等待一下避免请求过快
        time.sleep(0.5)

    # 等待处理完成
    time.sleep(2)

    # 检查日志记录
    logger.info("\n检查webhook日志记录...")
    try:
        logs_response = requests.get(f"{BASE_URL}/api/webhook/logs/")
        if logs_response.status_code == 200:
            logs_data = logs_response.json()
            total_logs = logs_data.get("total", 0)
            recent_logs = logs_data.get("results", [])

            logger.info(f"总日志数: {total_logs}")

            # 检查最近的日志
            recent_test_logs = [log for log in recent_logs[:10] if any(test["test_name"] in log.get("message", "") for test in results)]

            logger.info(f"最近的相关测试日志数量: {len(recent_test_logs)}")

            for log in recent_test_logs:
                logger.info(f"  - {log.get('event_type', 'unknown')} | {log.get('request_id', 'no-id')} | {log.get('message', 'no-message')}")
                logger.info(f"    状态: {'成功' if log.get('processed') and not log.get('error_message') else '失败'}")
                if log.get('error_message'):
                    logger.info(f"    错误: {log['error_message']}")

            # 验证每个测试用例都有对应的日志记录
            expected_count = len(test_cases)
            actual_count = len(recent_test_logs)

            logger.info(f"\n验证结果:")
            logger.info(f"期望的日志数量: {expected_count}")
            logger.info(f"实际的日志数量: {actual_count}")
            logger.info(f"测试{'通过' if actual_count >= expected_count else '失败'}")

        else:
            logger.error(f"获取日志失败: {logs_response.status_code}")

    except Exception as e:
        logger.error(f"检查日志时出错: {str(e)}")

    return results

if __name__ == "__main__":
    print("开始测试webhook接口优化...")
    print("=" * 50)

    test_webhook_logging()

    print("=" * 50)
    print("测试完成！")
    print("请检查数据库中的webhook_logs表，确认所有请求都被正确记录。")