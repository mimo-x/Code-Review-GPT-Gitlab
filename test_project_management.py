#!/usr/bin/env python3
"""
项目管理功能测试脚本
测试GitLab webhook自动识别项目和项目管理功能
"""

import json
import requests
import time
from datetime import datetime

# 配置
BASE_URL = "http://localhost:8000"
WEBHOOK_URL = f"{BASE_URL}/api/webhook/gitlab/"
PROJECTS_URL = f"{BASE_URL}/api/webhook/projects/"
PROJECT_STATS_URL = f"{BASE_URL}/api/webhook/projects/stats/"

# 测试项目数据
TEST_PROJECTS = [
    {
        "id": 100,
        "name": "Test Project 1",
        "path_with_namespace": "test/project1",
        "web_url": "http://localhost:8080/test/project1",
        "description": "Test project for code review",
        "namespace": {"full_path": "test", "name": "Test"},
        "created_at": "2024-01-01T00:00:00Z"
    },
    {
        "id": 101,
        "name": "Test Project 2",
        "path_with_namespace": "frontend/vue-app",
        "web_url": "http://localhost:8080/frontend/vue-app",
        "description": "Vue.js frontend application",
        "namespace": {"full_path": "frontend", "name": "Frontend"},
        "created_at": "2024-01-02T00:00:00Z"
    }
]

def create_webhook_payload(event_type, project_data, **kwargs):
    """创建webhook payload"""
    payload = {
        "object_kind": event_type,
        "project": project_data,
        "user": {
            "id": 1,
            "name": "Test User",
            "email": "test@example.com",
            "username": "testuser"
        },
        "repository": {
            "name": project_data["name"],
            "url": project_data["web_url"],
            "description": project_data["description"]
        }
    }

    # 根据事件类型添加特定字段
    if event_type == "merge_request":
        payload.update({
            "object_attributes": {
                "iid": kwargs.get("mr_iid", 1),
                "title": kwargs.get("title", "Test merge request"),
                "description": kwargs.get("description", "Test MR description"),
                "state": "opened",
                "action": "open",
                "source_branch": kwargs.get("source_branch", "feature/test"),
                "target_branch": kwargs.get("target_branch", "main"),
                "url": f"{project_data['web_url']}/-/merge_requests/1"
            },
            "changes": kwargs.get("changes", {})
        })
    elif event_type == "push":
        payload.update({
            "ref": kwargs.get("ref", "refs/heads/main"),
            "checkout_sha": "abc123",
            "user_id": 1,
            "user_name": "Test User",
            "user_email": "test@example.com",
            "user_avatar": "https://www.gravatar.com/avatar/example",
            "project_id": project_data["id"],
            "message": kwargs.get("message", "Test commit message"),
            "timestamp": datetime.now().isoformat()
        })
    elif event_type == "issue":
        payload.update({
            "object_attributes": {
                "iid": kwargs.get("issue_iid", 1),
                "title": kwargs.get("title", "Test issue"),
                "description": kwargs.get("description", "Test issue description"),
                "state": "opened",
                "action": "open"
            }
        })

    return payload

def send_webhook(payload):
    """发送webhook请求"""
    headers = {
        "Content-Type": "application/json",
        "X-GitLab-Token": "test-token"  # 如果设置了token验证
    }

    try:
        response = requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=10)
        print(f"Webhook Response Status: {response.status_code}")
        print(f"Webhook Response Body: {response.json()}")
        return response
    except Exception as e:
        print(f"Error sending webhook: {e}")
        return None

def get_projects(params=None):
    """获取项目列表"""
    try:
        response = requests.get(PROJECTS_URL, params=params, timeout=10)
        print(f"Get Projects Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Found {data.get('count', 0)} projects")
            return data
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Error getting projects: {e}")
        return None

def get_project_detail(project_id):
    """获取项目详情"""
    try:
        url = f"{PROJECTS_URL}{project_id}/"
        response = requests.get(url, timeout=10)
        print(f"Get Project Detail Status: {response.status_code}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Error getting project detail: {e}")
        return None

def get_project_stats():
    """获取项目统计"""
    try:
        response = requests.get(PROJECT_STATS_URL, timeout=10)
        print(f"Get Project Stats Status: {response.status_code}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Error getting project stats: {e}")
        return None

def enable_project_review(project_id):
    """启用项目审查"""
    try:
        url = f"{PROJECTS_URL}{project_id}/enable/"
        response = requests.post(url, timeout=10)
        print(f"Enable Review Status: {response.status_code}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Error enabling review: {e}")
        return None

def disable_project_review(project_id):
    """禁用项目审查"""
    try:
        url = f"{PROJECTS_URL}{project_id}/disable/"
        response = requests.post(url, timeout=10)
        print(f"Disable Review Status: {response.status_code}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Error disabling review: {e}")
        return None

def test_project_management():
    """测试完整的项目管理流程"""
    print("=" * 60)
    print("开始测试项目管理功能")
    print("=" * 60)

    # 1. 发送merge request webhook，自动创建项目
    print("\n1. 发送Merge Request Webhook...")
    mr_payload = create_webhook_payload(
        "merge_request",
        TEST_PROJECTS[0],
        mr_iid=1,
        title="Add new feature",
        description="Implement new feature for testing",
        source_branch="feature/new-feature",
        target_branch="main"
    )
    response = send_webhook(mr_payload)
    time.sleep(1)

    # 2. 发送push webhook到另一个项目
    print("\n2. 发送Push Webhook...")
    push_payload = create_webhook_payload(
        "push",
        TEST_PROJECTS[1],
        ref="refs/heads/develop",
        message="Update dependencies"
    )
    response = send_webhook(push_payload)
    time.sleep(1)

    # 3. 检查项目列表
    print("\n3. 检查项目列表...")
    projects = get_projects()
    if projects:
        print("项目列表:")
        for project in projects.get('projects', []):
            print(f"  - {project['project_name']} (ID: {project['project_id']})")
            print(f"    审查状态: {'启用' if project['review_enabled'] else '禁用'}")
            print(f"    最后活动: {project['last_activity']}")

    # 4. 获取项目统计
    print("\n4. 获取项目统计...")
    stats = get_project_stats()
    if stats:
        stat_data = stats.get('stats', {})
        print(f"总项目数: {stat_data.get('total_projects', 0)}")
        print(f"活跃项目数: {stat_data.get('active_projects', 0)}")
        print(f"审查启用项目数: {stat_data.get('review_enabled', 0)}")
        print(f"本周审查数: {stat_data.get('weekly_reviews', 0)}")
        print(f"最近事件数: {stat_data.get('recent_events', 0)}")

    # 5. 获取项目详情
    print("\n5. 获取项目详情...")
    project_id = TEST_PROJECTS[0]["id"]
    detail = get_project_detail(project_id)
    if detail:
        project = detail.get('project', {})
        stats = detail.get('stats', {})
        print(f"项目名称: {project.get('project_name')}")
        print(f"项目描述: {project.get('description')}")
        print(f"Webhook URL: {project.get('webhook_url')}")
        print(f"提交数: {project.get('commits_count', 0)}")
        print(f"MR数: {project.get('mr_count', 0)}")
        print(f"成员数: {project.get('members_count', 0)}")

        if stats:
            review_stats = stats.get('reviews', {})
            print(f"审查统计:")
            print(f"  总审查数: {review_stats.get('total', 0)}")
            print(f"  完成审查数: {review_stats.get('completed', 0)}")
            print(f"  本周审查数: {review_stats.get('weekly', 0)}")

    # 6. 启用项目审查
    print("\n6. 启用项目审查...")
    enable_result = enable_project_review(project_id)
    if enable_result:
        print(f"启用结果: {enable_result.get('message')}")

    # 7. 再次检查项目状态
    print("\n7. 检查项目状态变更...")
    detail_after = get_project_detail(project_id)
    if detail_after:
        project = detail_after.get('project', {})
        print(f"审查状态: {'启用' if project.get('review_enabled') else '禁用'}")

    # 8. 发送另一个MR，这次应该会触发审查
    print("\n8. 发送第二个Merge Request (应该触发审查)...")
    mr_payload_2 = create_webhook_payload(
        "merge_request",
        TEST_PROJECTS[0],
        mr_iid=2,
        title="Fix bug",
        description="Fix critical bug in production",
        source_branch="fix/bug-fix",
        target_branch="main"
    )
    response = send_webhook(mr_payload_2)
    time.sleep(2)  # 等待审查处理

    # 9. 禁用项目审查
    print("\n9. 禁用项目审查...")
    disable_result = disable_project_review(project_id)
    if disable_result:
        print(f"禁用结果: {disable_result.get('message')}")

    # 10. 发送第三个MR，这次应该跳过审查
    print("\n10. 发送第三个Merge Request (应该跳过审查)...")
    mr_payload_3 = create_webhook_payload(
        "merge_request",
        TEST_PROJECTS[0],
        mr_iid=3,
        title="Documentation update",
        description="Update README file",
        source_branch="docs/update-readme",
        target_branch="main"
    )
    response = send_webhook(mr_payload_3)

    # 11. 发送其他类型的事件
    print("\n11. 发送Issue事件...")
    issue_payload = create_webhook_payload(
        "issue",
        TEST_PROJECTS[0],
        issue_iid=1,
        title="Feature request",
        description="Add new feature request"
    )
    response = send_webhook(issue_payload)

    print("\n12. 发送Pipeline事件...")
    pipeline_payload = create_webhook_payload(
        "pipeline",
        TEST_PROJECTS[0]
    )
    pipeline_payload["object_attributes"] = {
        "id": 1,
        "ref": "main",
        "status": "success",
        "source": "push"
    }
    response = send_webhook(pipeline_payload)

    # 12. 最终统计
    print("\n12. 最终统计...")
    final_stats = get_project_stats()
    if final_stats:
        stat_data = final_stats.get('stats', {})
        print(f"最终统计:")
        print(f"  总项目数: {stat_data.get('total_projects', 0)}")
        print(f"  活跃项目数: {stat_data.get('active_projects', 0)}")
        print(f"  审查启用项目数: {stat_data.get('review_enabled', 0)}")
        print(f"  本周审查数: {stat_data.get('weekly_reviews', 0)}")
        print(f"  最近事件数: {stat_data.get('recent_events', 0)}")

    print("\n" + "=" * 60)
    print("项目管理功能测试完成")
    print("=" * 60)

if __name__ == "__main__":
    print("确保Django服务器正在运行在 http://localhost:8000")
    print("确保MongoDB服务正在运行")
    print("开始测试项目管理功能...")
    print()

    test_project_management()