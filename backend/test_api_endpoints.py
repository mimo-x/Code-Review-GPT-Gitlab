#!/usr/bin/env python
"""
测试所有 Webhook API 端点是否正常工作
"""

import os
import sys
import django
import requests

# 设置 Django 环境
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

BASE_URL = "http://localhost:8001"

# 定义所有需要测试的端点
ENDPOINTS = [
    # GET 端点
    ("GET", "/api/webhook/reviews/", "获取审查列表"),
    ("GET", "/api/webhook/logs/", "获取日志列表"),
    ("GET", "/api/webhook/projects/", "获取项目列表"),
    ("GET", "/api/webhook/projects/stats/", "获取项目统计"),
    ("GET", "/api/webhook/mock/reviews/", "Mock 审查数据"),
    ("GET", "/api/webhook/mock/logs/", "Mock 日志数据"),
]

def test_endpoints():
    """测试所有端点"""
    print("=" * 80)
    print("测试 Webhook API 端点")
    print("=" * 80)

    results = []

    for method, path, description in ENDPOINTS:
        url = f"{BASE_URL}{path}"
        print(f"\n[测试] {description}")
        print(f"  {method} {url}")

        try:
            if method == "GET":
                response = requests.get(url, timeout=5)
            elif method == "POST":
                response = requests.post(url, json={}, timeout=5)
            else:
                print(f"  ⚠ 不支持的方法: {method}")
                continue

            # 检查状态码
            if response.status_code == 200:
                print(f"  ✓ 状态码: {response.status_code}")

                # 检查响应格式
                try:
                    data = response.json()
                    if 'status' in data:
                        print(f"  ✓ 响应格式正确: status={data['status']}")
                        if 'results' in data:
                            print(f"  ✓ 返回 {len(data['results'])} 条记录")
                    else:
                        print(f"  ✓ 响应: {str(data)[:100]}...")

                    results.append((path, "✓ 通过"))
                except Exception as e:
                    print(f"  ⚠ JSON 解析失败: {e}")
                    results.append((path, "⚠ JSON 解析失败"))
            else:
                print(f"  ✗ 状态码: {response.status_code}")
                print(f"  响应: {response.text[:200]}")
                results.append((path, f"✗ 状态码 {response.status_code}"))

        except requests.exceptions.ConnectionError:
            print(f"  ✗ 连接失败 - 服务器未运行？")
            results.append((path, "✗ 连接失败"))
        except requests.exceptions.Timeout:
            print(f"  ✗ 请求超时")
            results.append((path, "✗ 超时"))
        except Exception as e:
            print(f"  ✗ 错误: {e}")
            results.append((path, f"✗ {str(e)[:50]}"))

    # 打印总结
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)

    passed = sum(1 for _, result in results if result.startswith("✓"))
    total = len(results)

    for path, result in results:
        print(f"{result:20} {path}")

    print("\n" + "-" * 80)
    print(f"总计: {passed}/{total} 通过")

    if passed == total:
        print("✓ 所有端点测试通过！")
    else:
        print(f"✗ {total - passed} 个端点测试失败")
    print("=" * 80)

    return passed == total


if __name__ == '__main__':
    print("\n确保后端服务正在运行在 http://localhost:8001")
    print("如果未运行，请先执行: python manage.py runserver 8001\n")

    input("按 Enter 继续测试...")

    success = test_endpoints()
    sys.exit(0 if success else 1)
