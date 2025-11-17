from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
import logging
import os
import tempfile
import subprocess
from .models import LLMConfig, GitLabConfig, NotificationConfig, NotificationChannel, WebhookEventRule, ClaudeCliConfig
from .serializers import (
    LLMConfigSerializer,
    GitLabConfigSerializer,
    NotificationConfigSerializer,
    NotificationChannelSerializer,
    WebhookEventRuleSerializer,
    ConfigSummarySerializer,
    ClaudeCliConfigSerializer
)

logger = logging.getLogger(__name__)


class LLMConfigViewSet(viewsets.ModelViewSet):
    """LLM配置管理API"""
    serializer_class = LLMConfigSerializer
    permission_classes = [AllowAny]  # 临时允许所有访问，生产环境应该使用IsAuthenticated

    def get_queryset(self):
        return LLMConfig.objects.all()

    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取当前激活的LLM配置"""
        config = LLMConfig.objects.filter(is_active=True).first()
        if config:
            serializer = self.get_serializer(config)
            return Response(serializer.data)
        return Response({'error': 'No active LLM config found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活指定的LLM配置"""
        config = self.get_object()
        # 先禁用所有其他配置
        LLMConfig.objects.filter(is_active=True).update(is_active=False)
        # 激活当前配置
        config.is_active = True
        config.save()
        return Response({'message': 'LLM config activated successfully'})


class GitLabConfigViewSet(viewsets.ModelViewSet):
    """GitLab配置管理API"""
    serializer_class = GitLabConfigSerializer
    permission_classes = [AllowAny]  # 临时允许所有访问，生产环境应该使用IsAuthenticated

    def get_queryset(self):
        return GitLabConfig.objects.all()

    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取当前激活的GitLab配置"""
        config = GitLabConfig.objects.filter(is_active=True).first()
        if config:
            serializer = self.get_serializer(config)
            return Response(serializer.data)
        return Response({'error': 'No active GitLab config found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活指定的GitLab配置"""
        config = self.get_object()
        # 先禁用所有其他配置
        GitLabConfig.objects.filter(is_active=True).update(is_active=False)
        # 激活当前配置
        config.is_active = True
        config.save()
        return Response({'message': 'GitLab config activated successfully'})


class NotificationConfigViewSet(viewsets.ModelViewSet):
    """通知配置管理API"""
    serializer_class = NotificationConfigSerializer
    permission_classes = [AllowAny]  # 临时允许所有访问，生产环境应该使用IsAuthenticated

    def get_queryset(self):
        return NotificationConfig.objects.all()

    def create(self, request, *args, **kwargs):
        """创建通知配置，确保同一类型的配置唯一性"""
        notification_type = request.data.get('notification_type')
        if notification_type:
            # 检查是否已存在相同类型的配置
            existing_config = NotificationConfig.objects.filter(
                notification_type=notification_type
            ).first()

            if existing_config:
                # 更新现有配置
                serializer = self.get_serializer(existing_config, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()
                return Response(serializer.data)

        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """根据类型获取通知配置"""
        notification_type = request.query_params.get('type')
        if notification_type:
            config = NotificationConfig.objects.filter(
                notification_type=notification_type,
                is_active=True
            ).first()
            if config:
                serializer = self.get_serializer(config)
                return Response(serializer.data)
        return Response({'error': 'Config not found'}, status=status.HTTP_404_NOT_FOUND)


class NotificationChannelViewSet(viewsets.ModelViewSet):
    """通知渠道管理API"""
    serializer_class = NotificationChannelSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = NotificationChannel.objects.all()
        notif_type = self.request.query_params.get('type')
        if notif_type:
            queryset = queryset.filter(notification_type=notif_type)
        return queryset.order_by('name', '-updated_at')

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """测试通知渠道是否配置正确"""
        import uuid

        channel = self.get_object()

        # 生成唯一的测试消息标识
        test_id = str(uuid.uuid4())[:8]
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')

        if channel.notification_type == 'dingtalk':
            return self._test_dingtalk(channel, test_id, timestamp)
        elif channel.notification_type == 'slack':
            return self._test_slack(channel, test_id, timestamp)
        elif channel.notification_type == 'feishu':
            return self._test_feishu(channel, test_id, timestamp)
        elif channel.notification_type == 'wechat':
            return self._test_wechat(channel, test_id, timestamp)
        elif channel.notification_type == 'email':
            return self._test_email(channel, test_id, timestamp)
        else:
            return Response({
                'success': False,
                'message': f'暂不支持测试 {channel.notification_type} 类型的通知渠道'
            }, status=status.HTTP_400_BAD_REQUEST)

    def _test_dingtalk(self, channel, test_id, timestamp):
        """测试钉钉通知渠道"""
        try:
            from apps.response.services import DingTalkService

            config_dict = channel.config_dict
            webhook_url = config_dict.get('webhook_url') or config_dict.get('webhook')
            secret = config_dict.get('secret')

            if not webhook_url:
                return Response({
                    'success': False,
                    'message': '钉钉webhook_url未配置'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 构建测试消息
            test_message = f"""### 🧪 通知渠道测试

**渠道名称**: {channel.name}
**测试ID**: {test_id}
**测试时间**: {timestamp}
**配置状态**: ✅ Webhook已配置
**签名状态**: {'✅ Secret已配置' if secret else '⚠️ 未配置Secret'}

---

这是一条测试消息，用于验证钉钉通知渠道配置是否正确。如果您收到此消息，说明配置成功！

---
*Code Review GPT 自动发送*"""

            service = DingTalkService(webhook_url=webhook_url, secret=secret, request_id=f"test-{test_id}")
            result = service.send_markdown("通知渠道测试", test_message)

            if result.get('success'):
                return Response({
                    'success': True,
                    'message': '测试消息发送成功，请检查钉钉群是否收到消息',
                    'test_id': test_id
                })
            else:
                return Response({
                    'success': False,
                    'message': f'测试消息发送失败: {result.get("message", "未知错误")}',
                    'details': result.get('details', {}),
                    'test_id': test_id
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'测试异常: {str(e)}',
                'test_id': test_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _test_slack(self, channel, test_id, timestamp):
        """测试Slack通知渠道"""
        try:
            import requests

            config_dict = channel.config_dict
            webhook_url = config_dict.get('webhook_url') or config_dict.get('webhook')

            if not webhook_url:
                return Response({
                    'success': False,
                    'message': 'Slack webhook_url未配置'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 构建测试消息
            payload = {
                "text": f"🧪 通知渠道测试 - {channel.name}",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🧪 通知渠道测试"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*渠道名称:*\n{channel.name}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*测试ID:*\n{test_id}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*测试时间:*\n{timestamp}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*配置状态:*\n✅ 已配置"
                            }
                        ]
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "这是一条测试消息，用于验证Slack通知渠道配置是否正确。如果您收到此消息，说明配置成功！"
                        }
                    }
                ]
            }

            response = requests.post(webhook_url, json=payload, timeout=30)

            if response.status_code == 200:
                return Response({
                    'success': True,
                    'message': '测试消息发送成功，请检查Slack频道是否收到消息',
                    'test_id': test_id
                })
            else:
                return Response({
                    'success': False,
                    'message': f'Slack API返回错误: HTTP {response.status_code}',
                    'response': response.text[:200],
                    'test_id': test_id
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'测试异常: {str(e)}',
                'test_id': test_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _test_feishu(self, channel, test_id, timestamp):
        """测试飞书通知渠道"""
        try:
            import requests

            config_dict = channel.config_dict
            webhook_url = config_dict.get('webhook_url') or config_dict.get('webhook')

            if not webhook_url:
                return Response({
                    'success': False,
                    'message': '飞书webhook_url未配置'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 构建简单的文本测试消息（不使用签名）
            message_text = f"🧪 通知渠道测试\n\n渠道名称: {channel.name}\n测试ID: {test_id}\n测试时间: {timestamp}\n配置状态: ✅ Webhook已配置\n\n这是一条测试消息，用于验证飞书通知渠道配置是否正确。如果您收到此消息，说明配置成功！"

            payload = {
                "msg_type": "text",
                "content": {
                    "text": message_text
                }
            }

            logger.info(f"飞书测试请求 - URL: {webhook_url[:50]}...")
            logger.info(f"飞书测试请求 - Payload: {payload}")
            response = requests.post(webhook_url, json=payload, timeout=30)
            result = response.json()

            logger.info(f"飞书测试API响应 - 状态码:{response.status_code}, 响应内容:{response.text}")

            if response.status_code == 200 and result.get('code') == 0:
                return Response({
                    'success': True,
                    'message': '测试消息发送成功，请检查飞书群是否收到消息',
                    'test_id': test_id
                })
            else:
                error_msg = result.get('msg', '未知错误')
                logger.error(f"飞书测试失败 - 错误码:{result.get('code')}, 消息:{error_msg}, 完整响应:{result}")
                return Response({
                    'success': False,
                    'message': f'飞书API错误: {error_msg}',
                    'details': result,
                    'test_id': test_id
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'测试异常: {str(e)}',
                'test_id': test_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _test_wechat(self, channel, test_id, timestamp):
        """测试企业微信通知渠道"""
        try:
            import requests

            config_dict = channel.config_dict
            webhook_url = config_dict.get('webhook_url') or config_dict.get('webhook')

            if not webhook_url:
                return Response({
                    'success': False,
                    'message': '企业微信webhook_url未配置'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 构建简单的文本测试消息
            message_content = f"""🧪 通知渠道测试

渠道名称: {channel.name}
测试ID: {test_id}
测试时间: {timestamp}
配置状态: ✅ Webhook已配置

这是一条测试消息，用于验证企业微信通知渠道配置是否正确。如果您收到此消息，说明配置成功！"""

            payload = {
                "msgtype": "text",
                "text": {
                    "content": message_content
                }
            }

            response = requests.post(webhook_url, json=payload, timeout=30)
            result = response.json()

            if result.get('errcode') == 0:
                return Response({
                    'success': True,
                    'message': '测试消息发送成功，请检查企业微信群是否收到消息',
                    'test_id': test_id
                })
            else:
                error_msg = result.get('errmsg', '未知错误')
                return Response({
                    'success': False,
                    'message': f'企业微信API错误: {error_msg}',
                    'details': result,
                    'test_id': test_id
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'测试异常: {str(e)}',
                'test_id': test_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _test_email(self, channel, test_id, timestamp):
        """测试邮件通知渠道"""
        try:
            from django.core.mail import send_mail
            from django.conf import settings

            config_dict = channel.config_dict

            # 检查邮件配置
            smtp_host = config_dict.get('smtp_host')
            smtp_port = config_dict.get('smtp_port')
            username = config_dict.get('username')
            password = config_dict.get('password')
            from_email = config_dict.get('from_email')

            if not all([smtp_host, smtp_port, username, password]):
                return Response({
                    'success': False,
                    'message': '邮件服务配置不完整，请检查SMTP设置'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 临时配置Django邮件设置
            original_email_settings = {}
            for key in ['EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD']:
                original_email_settings[key] = getattr(settings, key, None)

            settings.EMAIL_HOST = smtp_host
            settings.EMAIL_PORT = int(smtp_port)
            settings.EMAIL_HOST_USER = username
            settings.EMAIL_HOST_PASSWORD = password

            try:
                # 发送测试邮件
                subject = f"🧪 通知渠道测试 - {channel.name}"
                message = f"""
通知渠道测试

渠道名称: {channel.name}
测试ID: {test_id}
测试时间: {timestamp}
配置状态: ✅ 已配置

这是一条测试消息，用于验证邮件通知渠道配置是否正确。如果您收到此邮件，说明配置成功！

---
Code Review GPT 自动发送
"""

                recipient = username  # 发送给配置的邮箱
                result = send_mail(
                    subject=subject,
                    message=message,
                    from_email=from_email or username,
                    recipient_list=[recipient],
                    fail_silently=False
                )

                if result > 0:
                    return Response({
                        'success': True,
                        'message': f'测试邮件发送成功，请检查邮箱 {recipient} 是否收到邮件',
                        'test_id': test_id
                    })
                else:
                    return Response({
                        'success': False,
                        'message': '邮件发送失败',
                        'test_id': test_id
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            finally:
                # 恢复原始邮件设置
                for key, value in original_email_settings.items():
                    if value is not None:
                        setattr(settings, key, value)
                    else:
                        delattr(settings, key)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'测试异常: {str(e)}',
                'test_id': test_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WebhookEventRuleViewSet(viewsets.ModelViewSet):
    """Webhook事件规则管理API"""
    serializer_class = WebhookEventRuleSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return WebhookEventRule.objects.all().order_by('name')

    def create(self, request, *args, **kwargs):
        """创建webhook事件规则，会检查是否存在相同的match_rules"""
        import json

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 检查是否已存在相同match_rules的规则
        new_match_rules = serializer.validated_data.get('match_rules', {})
        new_match_rules_json = json.dumps(new_match_rules, sort_keys=True)

        for existing_rule in WebhookEventRule.objects.all():
            existing_match_rules_json = json.dumps(existing_rule.match_rules_dict, sort_keys=True)
            if existing_match_rules_json == new_match_rules_json:
                return Response({
                    'error': '已存在相同匹配规则的事件',
                    'existing_rule': {
                        'id': existing_rule.id,
                        'name': existing_rule.name,
                        'event_type': existing_rule.event_type
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

        instance = serializer.save()

        # 重新从数据库获取实例以确保数据完整
        instance.refresh_from_db()

        # 使用序列化器返回完整数据
        response_serializer = self.get_serializer(instance)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """更新webhook事件规则，会检查是否与其他规则的match_rules冲突"""
        import json

        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # 如果更新了match_rules，检查是否与其他规则冲突
        if 'match_rules' in serializer.validated_data:
            new_match_rules = serializer.validated_data['match_rules']
            new_match_rules_json = json.dumps(new_match_rules, sort_keys=True)

            for existing_rule in WebhookEventRule.objects.exclude(id=instance.id):
                existing_match_rules_json = json.dumps(existing_rule.match_rules_dict, sort_keys=True)
                if existing_match_rules_json == new_match_rules_json:
                    return Response({
                        'error': '已存在相同匹配规则的事件',
                        'existing_rule': {
                            'id': existing_rule.id,
                            'name': existing_rule.name,
                            'event_type': existing_rule.event_type
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)

        instance = serializer.save()

        # 重新从数据库获取实例以确保数据完整
        instance.refresh_from_db()

        # 使用序列化器返回完整数据
        response_serializer = self.get_serializer(instance)
        return Response(response_serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        删除webhook事件规则
        删除前需要清理所有项目中对该事件规则的引用
        """
        from apps.webhook.models import Project

        instance = self.get_object()
        rule_id = instance.id

        # 查找所有使用了该事件规则的项目
        projects = Project.objects.all()
        updated_projects = []

        for project in projects:
            enabled_events = project.enabled_webhook_events_list
            if rule_id in enabled_events:
                # 从项目的启用事件列表中移除该规则
                project.disable_webhook_event(rule_id)
                project.save()
                updated_projects.append(project.project_name)

        # 执行删除
        instance.delete()

        # 返回删除信息，包含受影响的项目列表
        response_data = {
            'message': f'事件规则已删除',
            'affected_projects_count': len(updated_projects),
            'affected_projects': updated_projects[:10]  # 最多返回10个项目名
        }

        if len(updated_projects) > 10:
            response_data['note'] = f'共影响 {len(updated_projects)} 个项目，仅显示前10个'

        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def usage(self, request, pk=None):
        """
        查询使用该事件规则的项目列表
        """
        from apps.webhook.models import Project

        rule = self.get_object()
        projects = Project.objects.all()
        using_projects = []

        for project in projects:
            if rule.id in project.enabled_webhook_events_list:
                using_projects.append({
                    'id': project.id,
                    'project_id': project.project_id,
                    'project_name': project.project_name,
                    'project_url': project.project_url,
                    'review_enabled': project.review_enabled
                })

        return Response({
            'rule_id': rule.id,
            'rule_name': rule.name,
            'usage_count': len(using_projects),
            'projects': using_projects
        })

    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """测试事件规则是否匹配给定的payload"""
        rule = self.get_object()
        test_payload = request.data.get('payload', {})

        is_match = rule.matches_payload(test_payload)

        return Response({
            'rule_id': rule.id,
            'rule_name': rule.name,
            'is_match': is_match,
            'payload': test_payload,
            'match_rules': rule.match_rules_dict
        })

    @action(detail=False, methods=['post'])
    def initialize_defaults(self, request):
        """
        初始化默认的webhook事件规则
        只创建 MR 创建和 MR 更新两种规则
        会自动去重，不会创建重复的规则（基于match_rules判断）
        """
        import json

        # 预定义的事件规则配置（只包含 MR 创建和更新）
        default_rules = [
            {
                'name': 'MR 创建',
                'event_type': 'mr_open',
                'description': '当新的 Merge Request 被创建时触发代码审查',
                'match_rules': {
                    'object_kind': 'merge_request',
                    'object_attributes': {'action': 'open'}
                },
                'is_active': True
            },
            {
                'name': 'MR 更新',
                'event_type': 'mr_update',
                'description': '当 Merge Request 被更新时触发代码审查（如推送新提交）',
                'match_rules': {
                    'object_kind': 'merge_request',
                    'object_attributes': {'action': 'update'}
                },
                'is_active': True
            }
        ]

        created = []
        skipped = []

        for rule_config in default_rules:
            # 检查是否已存在相同match_rules的规则
            match_rules_json = json.dumps(rule_config['match_rules'], sort_keys=True)

            # 查找所有规则并比较match_rules
            exists = False
            for existing_rule in WebhookEventRule.objects.all():
                existing_match_rules_json = json.dumps(existing_rule.match_rules_dict, sort_keys=True)
                if existing_match_rules_json == match_rules_json:
                    exists = True
                    skipped.append({
                        'name': rule_config['name'],
                        'reason': f'已存在相同规则: {existing_rule.name} (ID: {existing_rule.id})'
                    })
                    break

            if not exists:
                # 创建新规则
                rule = WebhookEventRule.objects.create(
                    name=rule_config['name'],
                    event_type=rule_config['event_type'],
                    description=rule_config['description'],
                    match_rules=json.dumps(rule_config['match_rules'], ensure_ascii=False),
                    is_active=rule_config['is_active']
                )
                created.append({
                    'id': rule.id,
                    'name': rule.name,
                    'event_type': rule.event_type,
                    'is_active': rule.is_active
                })

        return Response({
            'message': '初始化完成',
            'created_count': len(created),
            'skipped_count': len(skipped),
            'created': created,
            'skipped': skipped
        })

    @action(detail=False, methods=['post'])
    def validate_payload(self, request):
        """使用所有活跃规则验证payload，返回匹配的规则"""
        payload = request.data.get('payload', {})
        if not payload:
            return Response({'error': 'Payload is required'}, status=status.HTTP_400_BAD_REQUEST)

        active_rules = WebhookEventRule.objects.filter(is_active=True)
        matched_rules = []

        for rule in active_rules:
            if rule.matches_payload(payload):
                matched_rules.append({
                    'id': rule.id,
                    'name': rule.name,
                    'event_type': rule.event_type,
                    'description': rule.description
                })

        return Response({
            'payload': payload,
            'matched_rules': matched_rules,
            'total_matched': len(matched_rules)
        })


class ConfigViewSet(viewsets.GenericViewSet):
    """配置统一管理API"""
    permission_classes = [AllowAny]  # 临时允许所有访问，生产环境应该使用IsAuthenticated

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """获取所有配置的摘要信息"""
        active_llm_config = LLMConfig.objects.filter(is_active=True).first()
        active_gitlab_config = GitLabConfig.objects.filter(is_active=True).first()
        active_claude_cli_config = ClaudeCliConfig.objects.filter(is_active=True).first()
        notification_configs = NotificationConfig.objects.filter(is_active=True)
        notification_channels = NotificationChannel.objects.all()
        webhook_events = WebhookEventRule.objects.all()

        data = {
            'llm': LLMConfigSerializer(active_llm_config).data if active_llm_config else None,
            'gitlab': GitLabConfigSerializer(active_gitlab_config).data if active_gitlab_config else None,
            'claude_cli': ClaudeCliConfigSerializer(active_claude_cli_config).data if active_claude_cli_config else None,
            'notifications': NotificationConfigSerializer(notification_configs, many=True).data,
            'channels': NotificationChannelSerializer(notification_channels, many=True).data,
            'webhook_events': WebhookEventRuleSerializer(webhook_events, many=True).data
        }

        return Response(data)

    @action(detail=False, methods=['post'])
    def batch_update(self, request):
        """批量更新配置"""
        data = request.data
        errors = {}

        try:
            # 更新LLM配置
            if 'llm' in data:
                llm_data = data['llm']
                active_llm = LLMConfig.objects.filter(is_active=True).first()

                if active_llm:
                    llm_serializer = LLMConfigSerializer(active_llm, data=llm_data, partial=True)
                    if llm_serializer.is_valid():
                        llm_serializer.save()
                    else:
                        errors['llm'] = llm_serializer.errors
                else:
                    llm_serializer = LLMConfigSerializer(data=llm_data)
                    if llm_serializer.is_valid():
                        llm_serializer.save()
                    else:
                        errors['llm'] = llm_serializer.errors

            # 更新GitLab配置
            if 'gitlab' in data:
                gitlab_data = data['gitlab']
                active_gitlab = GitLabConfig.objects.filter(is_active=True).first()

                if active_gitlab:
                    gitlab_serializer = GitLabConfigSerializer(active_gitlab, data=gitlab_data, partial=True)
                    if gitlab_serializer.is_valid():
                        gitlab_serializer.save()
                    else:
                        errors['gitlab'] = gitlab_serializer.errors
                else:
                    gitlab_serializer = GitLabConfigSerializer(data=gitlab_data)
                    if gitlab_serializer.is_valid():
                        gitlab_serializer.save()
                    else:
                        errors['gitlab'] = gitlab_serializer.errors

            # 更新Claude CLI配置
            if 'claude_cli' in data:
                claude_cli_data = data['claude_cli']
                active_claude_cli = ClaudeCliConfig.objects.filter(is_active=True).first()

                if active_claude_cli:
                    claude_cli_serializer = ClaudeCliConfigSerializer(active_claude_cli, data=claude_cli_data, partial=True)
                    if claude_cli_serializer.is_valid():
                        claude_cli_serializer.save()
                    else:
                        errors['claude_cli'] = claude_cli_serializer.errors
                else:
                    claude_cli_serializer = ClaudeCliConfigSerializer(data=claude_cli_data)
                    if claude_cli_serializer.is_valid():
                        claude_cli_serializer.save()
                    else:
                        errors['claude_cli'] = claude_cli_serializer.errors

            # 通知渠道维护改为单独接口，这里仅做兼容忽略
            data.pop('notifications', None)
            data.pop('channels', None)

            if errors:
                return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

            return Response({'message': 'All configs updated successfully'})

        except Exception as e:
            return Response(
                {'error': f'Failed to update configs: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='test-claude-cli')
    def test_claude_cli(self, request):
        """
        测试 Claude CLI 配置是否可用

        测试步骤：
        1. 验证 CLI 安装（claude --help）
        2. 获取 CLI 版本（claude --version）
        3. 实际调用 API 验证环境变量是否生效
        """
        try:
            from apps.review.claude_cli_service import ClaudeCliService

            # 获取前端传来的配置
            claude_cli_data = request.data.get('claude_cli', {})

            # 创建测试服务实例
            test_service = ClaudeCliService()

            # 手动设置配置（用于测试，不保存到数据库）
            test_service.anthropic_base_url = claude_cli_data.get('anthropic_base_url')
            test_service.anthropic_auth_token = claude_cli_data.get('anthropic_auth_token')
            test_service.cli_path = claude_cli_data.get('cli_path', 'claude')
            test_service.timeout = claude_cli_data.get('timeout', 300)

            # 测试 1: 验证 CLI 安装
            is_valid, error = test_service.validate_cli_installation()
            if not is_valid:
                return Response({
                    'status': 'error',
                    'message': f'CLI 安装验证失败: {error}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 测试 2: 获取版本号
            success, version, version_error = test_service.get_cli_version()
            if not success:
                logger.warning(f"无法获取 CLI 版本: {version_error}")
                version = 'unknown'

            # 测试 3: 快速验证 Base URL 连通性（如果配置了）
            if test_service.anthropic_base_url:
                try:
                    import requests
                    # 快速检查 base URL 是否可访问（5秒超时）
                    test_url = test_service.anthropic_base_url.rstrip('/')
                    logger.info(f"检查 Base URL 连通性: {test_url}")

                    response = requests.get(
                        test_url,
                        timeout=5,
                        allow_redirects=True
                    )
                    logger.info(f"Base URL 响应状态: {response.status_code}")
                except requests.exceptions.Timeout:
                    return Response({
                        'status': 'error',
                        'message': f'Base URL 连接超时，请检查 {test_service.anthropic_base_url} 是否可访问'
                    }, status=status.HTTP_400_BAD_REQUEST)
                except requests.exceptions.ConnectionError:
                    return Response({
                        'status': 'error',
                        'message': f'无法连接到 {test_service.anthropic_base_url}，请检查 URL 是否正确'
                    }, status=status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    logger.warning(f"Base URL 连通性检查警告: {e}")
                    # 不阻断测试，继续执行

            # 测试 4: 尝试简单的 API 调用
            with tempfile.TemporaryDirectory() as temp_dir:
                env = os.environ.copy()
                if test_service.anthropic_base_url:
                    env['ANTHROPIC_BASE_URL'] = test_service.anthropic_base_url
                if test_service.anthropic_auth_token:
                    env['ANTHROPIC_AUTH_TOKEN'] = test_service.anthropic_auth_token

                # 初始化 git 仓库
                subprocess.run(['git', 'init'], cwd=temp_dir, capture_output=True)
                subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=temp_dir, capture_output=True)
                subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=temp_dir, capture_output=True)

                # 创建测试文件
                test_file = os.path.join(temp_dir, 'test.txt')
                with open(test_file, 'w') as f:
                    f.write('Hello World')

                subprocess.run(['git', 'add', '.'], cwd=temp_dir, capture_output=True)
                subprocess.run(['git', 'commit', '-m', 'test'], cwd=temp_dir, capture_output=True)

                # 调用 Claude CLI
                test_command = [
                    test_service.cli_path,
                    '-p', 'Say "test successful" in one word',
                    '--output-format', 'json'
                ]

                logger.info(f"执行测试命令: {' '.join(test_command)}")
                logger.info(f"Base URL: {test_service.anthropic_base_url or '默认'}")
                logger.info(f"Auth Token: {'已配置' if test_service.anthropic_auth_token else '未配置'}")

                try:
                    result = subprocess.run(
                        test_command,
                        cwd=temp_dir,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=45,  # 45 秒超时，平衡速度和可靠性
                        check=False
                    )

                    logger.info(f"命令返回码: {result.returncode}")
                    if result.stdout:
                        logger.info(f"stdout: {result.stdout[:500]}")
                    if result.stderr:
                        logger.error(f"stderr: {result.stderr[:500]}")

                    if result.returncode == 0:
                        return Response({
                            'status': 'success',
                            'message': 'Claude CLI 配置正确，API 连接成功',
                            'version': version,
                            'details': {
                                'cli_path': test_service.cli_path,
                                'base_url': test_service.anthropic_base_url or '默认',
                                'auth_configured': bool(test_service.anthropic_auth_token)
                            }
                        })
                    else:
                        # 解析错误信息
                        error_output = result.stderr or result.stdout or '未知错误'

                        # 检查常见错误模式
                        if 'authentication' in error_output.lower() or 'unauthorized' in error_output.lower():
                            error_msg = '认证失败：请检查 ANTHROPIC_AUTH_TOKEN 是否正确'
                        elif 'connection' in error_output.lower() or 'network' in error_output.lower():
                            error_msg = '网络连接失败：请检查 ANTHROPIC_BASE_URL 和网络连接'
                        elif 'not found' in error_output.lower():
                            error_msg = f'Claude CLI 未找到：请检查 cli_path 配置 ({test_service.cli_path})'
                        else:
                            error_msg = f'Claude CLI 执行失败: {error_output[:200]}'

                        logger.error(f"Claude CLI 测试失败: {error_msg}")

                        return Response({
                            'status': 'error',
                            'message': error_msg,
                            'details': {
                                'returncode': result.returncode,
                                'stderr': result.stderr[:500] if result.stderr else None,
                                'stdout': result.stdout[:500] if result.stdout else None
                            }
                        }, status=status.HTTP_400_BAD_REQUEST)

                except subprocess.TimeoutExpired as e:
                    logger.error(f"Claude CLI 调用超时 (45秒)")
                    return Response({
                        'status': 'error',
                        'message': 'Claude CLI 调用超时（45秒），可能原因：\n1. 认证信息错误（ANTHROPIC_AUTH_TOKEN 不正确）\n2. API 端点无法访问或响应慢\n3. 网络连接不稳定',
                        'details': {
                            'timeout': 45,
                            'suggestion': '请仔细检查 ANTHROPIC_AUTH_TOKEN 是否正确（常见错误：复制时多了空格或少了字符）'
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"测试 Claude CLI 配置失败: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'message': f'测试失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
