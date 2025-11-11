#!/usr/bin/env python
"""
飞书Webhook测试脚本 - 用于调试签名和时间戳问题
"""
import hashlib
import base64
import hmac
import time
import json
import requests
import sys
from datetime import datetime

def gen_feishu_sign(timestamp, secret):
    """
    生成飞书签名（HMAC-SHA256）
    """
    string_to_sign = f'{timestamp}\n{secret}'
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign, string_to_sign

def test_feishu_webhook(webhook_url, secret=None):
    """
    测试飞书Webhook
    """
    print("=" * 80)
    print("飞书Webhook测试")
    print("=" * 80)
    print(f"Webhook URL: {webhook_url[:50]}...")
    print(f"Secret配置: {'是' if secret else '否'}")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)

    # 构建测试消息
    payload = {
        "msg_type": "interactive",
        "card": {
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n**消息**: 这是一条飞书Webhook测试消息",
                        "tag": "lark_md"
                    }
                }
            ],
            "header": {
                "title": {
                    "content": "🧪 Webhook测试",
                    "tag": "plain_text"
                },
                "template": "blue"
            }
        }
    }

    # 如果有secret，生成签名
    if secret:
        timestamp = str(int(time.time()))
        sign, string_to_sign = gen_feishu_sign(timestamp, secret)

        payload['timestamp'] = timestamp
        payload['sign'] = sign

        print(f"时间戳 (timestamp): {timestamp}")
        print(f"待签名字符串: {repr(string_to_sign)}")
        print(f"生成的签名 (sign): {sign}")
        print("-" * 80)

    print(f"请求payload (JSON):")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("-" * 80)

    # 发送请求
    try:
        print("发送请求中...")
        response = requests.post(webhook_url, json=payload, timeout=30)

        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        print("-" * 80)

        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                print("✅ 测试成功！飞书Webhook配置正确")
                return True
            else:
                print(f"❌ 测试失败 - 错误码: {result.get('code')}, 错误信息: {result.get('msg')}")
                print(f"完整响应: {result}")
                return False
        else:
            print(f"❌ HTTP请求失败 - 状态码: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ 发送异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("=" * 80)

if __name__ == '__main__':
    # 从命令行参数获取webhook_url和secret
    if len(sys.argv) < 2:
        print("用法: python test_feishu_webhook.py <webhook_url> [secret]")
        print("示例: python test_feishu_webhook.py 'https://open.feishu.cn/...' 'SEC_xxx'")
        sys.exit(1)

    webhook_url = sys.argv[1]
    secret = sys.argv[2] if len(sys.argv) > 2 else None

    test_feishu_webhook(webhook_url, secret)
