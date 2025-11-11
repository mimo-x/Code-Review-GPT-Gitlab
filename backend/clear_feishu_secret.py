#!/usr/bin/env python
"""
清理飞书通知通道的空secret字段
"""
import os
import sys
import django

# 设置Django环境
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.llm.models import NotificationChannel
import json

# 查询所有飞书通道
feishu_channels = NotificationChannel.objects.filter(notification_type='feishu')

print(f"找到 {feishu_channels.count()} 个飞书通知通道")
print("=" * 80)

for channel in feishu_channels:
    print(f"\n通道: {channel.name} (ID: {channel.id})")
    print(f"原始 config_data: {channel.config_data}")

    config_dict = channel.config_dict
    print(f"解析后的 config_dict: {config_dict}")

    # 检查secret
    secret = config_dict.get('secret', '')
    print(f"Secret值: {repr(secret)} (长度: {len(secret) if secret else 0})")

    if secret == '' or (secret and not secret.strip()):
        print("⚠️  发现空secret，准备清理...")

        # 移除secret字段
        if 'secret' in config_dict:
            del config_dict['secret']

        # 更新config_data
        channel.config_data = json.dumps(config_dict, ensure_ascii=False)
        channel.save()

        print(f"✅ 已清理，新的 config_data: {channel.config_data}")
    else:
        print(f"ℹ️  Secret已配置，保持不变")

print("\n" + "=" * 80)
print("清理完成！")
