#!/usr/bin/env python3
"""
初始化配置数据脚本
"""
import os
import sys
import django

# 设置Django环境
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.llm.models import LLMConfig, GitLabConfig, NotificationConfig, NotificationChannel
import json


def init_llm_configs():
    """初始化LLM配置"""
    print("初始化LLM配置...")

    # 创建默认的OpenAI配置
    openai_config, created = LLMConfig.objects.get_or_create(
        provider='openai',
        defaults={
            'model': 'gpt-4',
            'api_key': '',
            'api_base': '',
            'is_active': True
        }
    )

    if created:
        print(f"✓ 创建OpenAI配置: {openai_config}")
    else:
        print(f"✓ OpenAI配置已存在: {openai_config}")

    # 创建DeepSeek配置
    deepseek_config, created = LLMConfig.objects.get_or_create(
        provider='deepseek',
        defaults={
            'model': 'deepseek-coder',
            'api_key': '',
            'api_base': '',
            'is_active': False
        }
    )

    if created:
        print(f"✓ 创建DeepSeek配置: {deepseek_config}")
    else:
        print(f"✓ DeepSeek配置已存在: {deepseek_config}")

    # 创建Claude配置
    claude_config, created = LLMConfig.objects.get_or_create(
        provider='claude',
        defaults={
            'model': 'claude-3-sonnet-20240229',
            'api_key': '',
            'api_base': '',
            'is_active': False
        }
    )

    if created:
        print(f"✓ 创建Claude配置: {claude_config}")
    else:
        print(f"✓ Claude配置已存在: {claude_config}")


def init_gitlab_configs():
    """初始化GitLab配置"""
    print("\n初始化GitLab配置...")

    # 创建默认GitLab配置
    gitlab_config, created = GitLabConfig.objects.get_or_create(
        server_url='https://gitlab.com',
        defaults={
            'private_token': '',
            'max_files': 50,
            'context_lines': 5,
            'is_active': True
        }
    )

    if created:
        print(f"✓ 创建GitLab配置: {gitlab_config}")
    else:
        print(f"✓ GitLab配置已存在: {gitlab_config}")


def init_notification_configs():
    """初始化通知配置"""
    print("\n初始化通知配置...")

    # 钉钉通知配置
    dingtalk_config, created = NotificationConfig.objects.get_or_create(
        notification_type='dingtalk',
        defaults={
            'enabled': False,
            'config_data': json.dumps({
                'webhook': '',
                'secret': ''
            }),
            'is_active': True
        }
    )

    if created:
        print(f"✓ 创建钉钉通知配置: {dingtalk_config}")
    else:
        print(f"✓ 钉钉通知配置已存在: {dingtalk_config}")

    # GitLab评论通知配置
    gitlab_notif_config, created = NotificationConfig.objects.get_or_create(
        notification_type='gitlab',
        defaults={
            'enabled': True,
            'config_data': json.dumps({}),
            'is_active': True
        }
    )

    if created:
        print(f"✓ 创建GitLab评论通知配置: {gitlab_notif_config}")
    else:
        print(f"✓ GitLab评论通知配置已存在: {gitlab_notif_config}")

    # 飞书通知配置
    feishu_config, created = NotificationConfig.objects.get_or_create(
        notification_type='feishu',
        defaults={
            'enabled': False,
            'config_data': json.dumps({
                'webhook': '',
                'app_id': '',
                'app_secret': ''
            }),
            'is_active': True
        }
    )

    if created:
        print(f"✓ 创建飞书通知配置: {feishu_config}")
    else:
        print(f"✓ 飞书通知配置已存在: {feishu_config}")

    # 企业微信通知配置
    wechat_config, created = NotificationConfig.objects.get_or_create(
        notification_type='wechat',
        defaults={
            'enabled': False,
            'config_data': json.dumps({
                'corp_id': '',
                'corp_secret': '',
                'agent_id': '',
                'webhook': ''
            }),
            'is_active': True
        }
    )

    if created:
        print(f"✓ 创建企业微信通知配置: {wechat_config}")
    else:
        print(f"✓ 企业微信通知配置已存在: {wechat_config}")

    # 创建新的通知通道条目
    channels_to_ensure = [
        (
            '默认GitLab评论通道',
            'gitlab',
            '系统默认的GitLab评论通知通道',
            {},
            True,
        ),
        (
            '默认钉钉通知通道',
            'dingtalk',
            '示例钉钉机器人通道',
            {'webhook_url': '', 'secret': ''},
            False,
        ),
        (
            '默认飞书通知通道',
            'feishu',
            '示例飞书机器人通道',
            {'webhook_url': '', 'secret': ''},
            False,
        ),
        (
            '默认企业微信通知通道',
            'wechat',
            '示例企业微信机器人通道',
            {'webhook_url': ''},
            False,
        ),
        (
            '默认Slack通知通道',
            'slack',
            '示例Slack通知通道',
            {'webhook_url': ''},
            False,
        ),
    ]

    for name, notif_type, desc, config, is_default in channels_to_ensure:
        channel, created = NotificationChannel.objects.get_or_create(
            name=name,
            notification_type=notif_type,
            defaults={
                'description': desc,
                'config_data': json.dumps(config),
                'is_default': is_default,
                'is_active': True,
            }
        )
        if created:
            print(f"✓ 创建通知通道: {channel}")
        else:
            print(f"✓ 通知通道已存在: {channel}")


def main():
    """主函数"""
    print("开始初始化配置数据...")

    try:
        init_llm_configs()
        init_gitlab_configs()
        init_notification_configs()

        print("\n✅ 所有配置数据初始化完成!")

    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
