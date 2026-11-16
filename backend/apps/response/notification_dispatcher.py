"""
通知分发器 - 负责管理和分发到各个通知渠道
"""
import logging
import time
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from datetime import datetime

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """
    通知分发器，支持多渠道通知分发
    """

    def __init__(self, request_id=None):
        self.request_id = request_id

    def dispatch(self, report_data: Dict[str, Any], mr_info: Dict[str, Any], project_id: Optional[int] = None) -> Dict[str, Any]:
        """
        分发通知到各个渠道
        """
        try:
            project_id = project_id or mr_info.get('project_id')
            notification_channels, gitlab_enabled = self._get_notification_targets(project_id)

            total_targets = len(notification_channels) + (1 if gitlab_enabled else 0)

            if total_targets == 0:
                logger.warning(f"[{self.request_id}] 未找到启用的通知渠道")
                return {'success': True, 'channels': [], 'message': '无启用的通知渠道'}

            logger.info(f"[{self.request_id}] 开始分发通知到 {total_targets} 个渠道")

            results = []
            failed_channels = []

            # 先处理第三方渠道
            for channel in notification_channels:
                channel_type = channel.notification_type
                logger.info(f"[{self.request_id}] 开始发送到渠道: {channel_type} ({channel.name})")

                try:
                    # 调用对应的服务发送通知
                    result = self._send_to_channel(channel_type, channel, report_data, mr_info)

                    results.append({
                        'channel': channel_type,
                        'success': result.get('success', False),
                        'message': result.get('message', ''),
                        'response_time': result.get('response_time', 0),
                        'details': result.get('details', {}),
                        'channel_id': channel.id,
                        'channel_name': channel.name,
                    })

                    if result.get('success', False):
                        logger.info(f"[{self.request_id}] 渠道 {channel_type} ({channel.name}) 发送成功 - 耗时:{result.get('response_time', 0):.2f}秒")
                    else:
                        error_details = result.get('details', {})
                        logger.error(f"[{self.request_id}] 渠道 {channel_type} ({channel.name}) 发送失败 - 错误信息:{result.get('message', '')}, 响应时间:{result.get('response_time', 0):.2f}秒, 详细信息:{error_details}")
                        failed_channels.append(f"{channel_type}:{channel.id}")

                except Exception as e:
                    error_msg = f"渠道 {channel_type} ({channel.name}) 发送异常: {str(e)}"
                    logger.error(f"[{self.request_id}] {error_msg}", exc_info=True)
                    failed_channels.append(f"{channel_type}:{channel.id}")
                    results.append({
                        'channel': channel_type,
                        'success': False,
                        'message': error_msg,
                        'response_time': 0,
                        'details': {'error': str(e)},
                        'channel_id': channel.id,
                        'channel_name': channel.name,
                    })

            # GitLab 评论通知单独处理
            if gitlab_enabled:
                gitlab_start = time.time()
                gitlab_result = self._send_to_gitlab(None, report_data, mr_info, gitlab_start)

                if gitlab_result:
                    results.append({
                        'channel': 'gitlab',
                        'success': gitlab_result.get('success', False),
                        'message': gitlab_result.get('message', ''),
                        'response_time': gitlab_result.get('response_time', 0),
                        'details': gitlab_result.get('details', {}),
                        'channel_name': 'GitLab 评论',
                    })

                    if gitlab_result.get('success', False):
                        logger.info(f"[{self.request_id}] GitLab 评论发送成功")
                    else:
                        logger.error(f"[{self.request_id}] GitLab 评论发送失败: {gitlab_result.get('message', '')}")
                        failed_channels.append('gitlab')

            # 汇总结果
            success_count = len([r for r in results if r['success']])
            total_count = len(results)

            summary = {
                'success': success_count > 0,  # 只要有一个成功就算整体成功
                'total_channels': total_count,
                'success_channels': success_count,
                'failed_channels': len(failed_channels),
                'failed_channel_list': failed_channels,
                'results': results,
                'dispatch_time': datetime.now().isoformat()
            }

            logger.info(f"[{self.request_id}] 通知分发完成 - 成功:{success_count}/{total_count}, 失败渠道:{failed_channels}")

            return summary

        except ImproperlyConfigured as config_error:
            elapsed_time = time.time() - start_time
            error_msg = f'GitLab配置缺失: {config_error}'
            logger.error(f"[{self.request_id}] {error_msg}")
            return {
                'success': False,
                'message': error_msg,
                'response_time': elapsed_time,
                'details': {'error': str(config_error)}
            }
        except Exception as e:
            logger.error(f"[{self.request_id}] 通知分发异常: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'通知分发失败: {str(e)}',
                'channels': [],
                'dispatch_time': datetime.now().isoformat()
            }

    def _get_notification_targets(self, project_id: int | None):
        """获取项目可用的通知渠道以及GitLab通知配置"""
        try:
            from apps.llm.models import NotificationChannel
            from apps.webhook.models import Project, ProjectNotificationSetting

            channels = []
            gitlab_enabled = True

            default_channels = NotificationChannel.objects.filter(is_default=True, is_active=True)
            gitlab_fallback = NotificationChannel.objects.filter(
                notification_type='gitlab'
            ).order_by('-is_default', '-updated_at').first()

            fallback_channels = [c for c in default_channels if c.notification_type != 'gitlab']
            gitlab_default_enabled = True
            if gitlab_fallback is not None:
                gitlab_default_enabled = gitlab_fallback.is_default and gitlab_fallback.is_active

            if project_id:
                try:
                    project = Project.objects.get(project_id=project_id)
                    gitlab_enabled = project.gitlab_comment_notifications_enabled

                    settings = ProjectNotificationSetting.objects.filter(
                        project=project,
                        enabled=True,
                        channel__is_active=True
                    ).select_related('channel')

                    channels = [s.channel for s in settings if s.channel.notification_type != 'gitlab']

                    if not channels:
                        channels = fallback_channels

                except Project.DoesNotExist:
                    channels = fallback_channels
                    gitlab_enabled = gitlab_default_enabled
            else:
                channels = fallback_channels
                gitlab_enabled = gitlab_default_enabled

            # 去重，保持顺序
            unique = {}
            for channel in channels:
                unique[channel.id] = channel

            return list(unique.values()), gitlab_enabled

        except Exception as e:
            logger.error(f"[{self.request_id}] 获取通知渠道失败: {e}", exc_info=True)
            return [], False

    def _send_to_channel(self, channel_type: str, channel, report_data: Dict[str, Any], mr_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送通知到指定渠道
        """
        start_time = time.time()

        try:
            if channel_type == 'dingtalk':
                return self._send_to_dingtalk(channel, report_data, mr_info, start_time)
            elif channel_type == 'gitlab':
                return self._send_to_gitlab(channel, report_data, mr_info, start_time)
            elif channel_type == 'slack':
                return self._send_to_slack(channel, report_data, mr_info, start_time)
            elif channel_type == 'feishu':
                return self._send_to_feishu(channel, report_data, mr_info, start_time)
            elif channel_type == 'wechat':
                return self._send_to_wechat(channel, report_data, mr_info, start_time)
            elif channel_type == 'email':
                return self._send_to_email(channel, report_data, mr_info, start_time)
            elif channel_type == 'custom_webhook':
                return self._send_to_custom_webhook(channel, report_data, mr_info, start_time)
            else:
                return {
                    'success': False,
                    'message': f'不支持的通知渠道: {channel_type}',
                    'response_time': time.time() - start_time
                }

        except Exception as e:
            elapsed_time = time.time() - start_time
            return {
                'success': False,
                'message': f'发送到 {channel_type} 失败: {str(e)}',
                'response_time': elapsed_time,
                'details': {'error': str(e)}
            }

    def _send_to_dingtalk(self, channel, report_data: Dict[str, Any], mr_info: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """
        发送到钉钉
        """
        try:
            from .services import DingTalkService

            config_dict = channel.config_dict
            webhook_url = config_dict.get('webhook_url') or config_dict.get('webhook')
            secret = config_dict.get('secret')

            logger.info(f"[{self.request_id}] 开始配置钉钉服务 - 通道:{channel.name}, webhook_url配置:{bool(webhook_url)}, secret配置:{bool(secret)}")

            if not webhook_url:
                error_msg = '钉钉webhook_url未配置'
                logger.error(f"[{self.request_id}] {error_msg} - 通道:{channel.name}, config_dict:{config_dict}")
                return {
                    'success': False,
                    'message': error_msg,
                    'response_time': time.time() - start_time,
                    'details': {'channel_config': config_dict, 'webhook_url_exists': bool(webhook_url), 'secret_exists': bool(secret)}
                }

            # 构建钉钉消息
            content = report_data['content']
            mr_title = mr_info.get('title', '代码审查')
            project_name = mr_info.get('project_name', '未知项目')

            # 限制消息长度
            if len(content) > 1500:
                content = content[:1500] + "\n\n...(内容过长已截断，请查看完整报告)"

            message = f"""### 🤖 AI代码审查报告

**项目**: {project_name}
**MR**: {mr_title}
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
{content}
---
"""

            service = DingTalkService(webhook_url=webhook_url, secret=secret)
            result = service.send_markdown(f"AI代码审查报告 - {mr_title}", message)

            elapsed_time = time.time() - start_time
            result['response_time'] = elapsed_time

            return result

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{self.request_id}] 钉钉发送失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'钉钉发送失败: {str(e)}',
                'response_time': elapsed_time
            }

    def _send_to_gitlab(self, config, report_data: Dict[str, Any], mr_info: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """
        发送到GitLab（MR评论）
        """
        try:
            from apps.review.services import GitlabService

            project_id = mr_info.get('project_id')
            mr_iid = mr_info.get('mr_iid')

            if not project_id or not mr_iid:
                error_msg = f'GitLab项目ID或MR IID缺失 - project_id:{project_id}, mr_iid:{mr_iid}'
                logger.error(f"[{self.request_id}] {error_msg}")
                return {
                    'success': False,
                    'message': error_msg,
                    'response_time': time.time() - start_time,
                    'details': {'project_id': project_id, 'mr_iid': mr_iid}
                }

            content = report_data['content']
            logger.info(f"[{self.request_id}] 开始发送GitLab MR评论 - project_id:{project_id}, mr_iid:{mr_iid}, content_length:{len(content)}")

            service = GitlabService(request_id=self.request_id)
            result = service.post_merge_request_comment(project_id, mr_iid, content)

            elapsed_time = time.time() - start_time

            if result is None:
                error_msg = f'GitLab API调用失败 - project_id:{project_id}, mr_iid:{mr_iid}'
                logger.error(f"[{self.request_id}] {error_msg}")
                return {
                    'success': False,
                    'message': error_msg,
                    'response_time': elapsed_time,
                    'details': {'project_id': project_id, 'mr_iid': mr_iid, 'api_result': None}
                }
            elif isinstance(result, dict) and 'id' in result:
                logger.info(f"[{self.request_id}] GitLab评论发送成功 - comment_id:{result.get('id')}, 耗时:{elapsed_time:.2f}秒")
                result['response_time'] = elapsed_time
                result['success'] = True
                result['message'] = 'GitLab评论发送成功'
                return result
            else:
                error_msg = f'GitLab API返回异常结果 - project_id:{project_id}, mr_iid:{mr_iid}, result:{result}'
                logger.error(f"[{self.request_id}] {error_msg}")
                return {
                    'success': False,
                    'message': error_msg,
                    'response_time': elapsed_time,
                    'details': {'project_id': project_id, 'mr_iid': mr_iid, 'api_result': result}
                }

        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = f'GitLab评论发送异常: {str(e)}'
            logger.error(f"[{self.request_id}] {error_msg}", exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'response_time': elapsed_time,
                'details': {'error': str(e), 'project_id': mr_info.get('project_id'), 'mr_iid': mr_info.get('mr_iid')}
            }

    def _send_to_slack(self, channel, report_data: Dict[str, Any], mr_info: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """
        发送到Slack
        """
        try:
            import requests

            config_dict = channel.config_dict
            webhook_url = config_dict.get('webhook_url') or config_dict.get('webhook')

            if not webhook_url:
                return {
                    'success': False,
                    'message': 'Slack webhook_url未配置',
                    'response_time': time.time() - start_time
                }

            # 构建Slack消息
            content = report_data['content']
            mr_title = mr_info.get('title', '代码审查')
            project_name = mr_info.get('project_name', '未知项目')

            # 限制消息长度
            if len(content) > 1000:
                content = content[:1000] + "\n\n...(内容过长已截断)"

            payload = {
                "text": f"🤖 AI代码审查报告 - {mr_title}",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🤖 AI代码审查报告"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*项目:*\n{project_name}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*MR:*\n{mr_title}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*时间:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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
                            "text": f"```\n{content}\n```"
                        }
                    }
                ]
            }

            response = requests.post(webhook_url, json=payload, timeout=30)
            elapsed_time = time.time() - start_time

            if response.status_code == 200:
                logger.info(f"[{self.request_id}] Slack发送成功 - 耗时:{elapsed_time:.2f}秒")
                return {
                    'success': True,
                    'message': 'Slack发送成功',
                    'response_time': elapsed_time,
                    'details': {'status_code': response.status_code}
                }
            else:
                logger.error(f"[{self.request_id}] Slack发送失败 - 状态码:{response.status_code}, 响应:{response.text}")
                return {
                    'success': False,
                    'message': f'Slack发送失败 - HTTP {response.status_code}',
                    'response_time': elapsed_time,
                    'details': {'status_code': response.status_code, 'response': response.text[:200]}
                }

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{self.request_id}] Slack发送异常: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Slack发送异常: {str(e)}',
                'response_time': elapsed_time
            }

    def _send_to_feishu(self, channel, report_data: Dict[str, Any], mr_info: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """
        发送到飞书（使用富文本卡片格式，支持签名校验）
        """
        try:
            from .services import FeishuService

            config_dict = channel.config_dict
            webhook_url = config_dict.get('webhook_url') or config_dict.get('webhook')
            secret = config_dict.get('secret')

            if not webhook_url:
                return {
                    'success': False,
                    'message': '飞书webhook_url未配置',
                    'response_time': time.time() - start_time
                }

            content = report_data.get('content', '')
            score = report_data.get('score', 0)

            service = FeishuService(webhook_url=webhook_url, secret=secret, request_id=self.request_id)
            result = service.send_interactive(
                title=mr_info.get('title', 'AI代码审查报告'),
                content=content,
                extra_info={
                    'project_name': mr_info.get('project_name', '未知项目'),
                    'mr_title': mr_info.get('title', ''),
                    'score': score,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }
            )

            elapsed_time = time.time() - start_time
            result['response_time'] = elapsed_time
            return result

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{self.request_id}] 飞书发送异常: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'飞书发送异常: {str(e)}',
                'response_time': elapsed_time
            }

    def _send_to_wechat(self, channel, report_data: Dict[str, Any], mr_info: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """
        发送到企业微信
        """
        try:
            import requests

            config_dict = channel.config_dict
            webhook_url = config_dict.get('webhook_url') or config_dict.get('webhook')

            if not webhook_url:
                return {
                    'success': False,
                    'message': '企业微信webhook_url未配置',
                    'response_time': time.time() - start_time
                }

            # 构建企业微信消息（简单文本格式）
            content = report_data['content']
            mr_title = mr_info.get('title', '代码审查')
            project_name = mr_info.get('project_name', '未知项目')

            # 限制消息长度
            if len(content) > 1500:
                content = content[:1500] + "\n\n...(内容过长已截断)"

            message_content = f"""🤖 AI代码审查报告

项目: {project_name}
MR: {mr_title}
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{content}
"""

            payload = {
                "msgtype": "text",
                "text": {
                    "content": message_content
                }
            }

            response = requests.post(webhook_url, json=payload, timeout=30)
            elapsed_time = time.time() - start_time

            result = response.json()
            if result.get('errcode') == 0:
                logger.info(f"[{self.request_id}] 企业微信发送成功 - 耗时:{elapsed_time:.2f}秒")
                return {
                    'success': True,
                    'message': '企业微信发送成功',
                    'response_time': elapsed_time,
                    'details': {'errcode': result.get('errcode')}
                }
            else:
                logger.error(f"[{self.request_id}] 企业微信发送失败 - 错误码:{result.get('errcode')}, 消息:{result.get('errmsg')}")
                return {
                    'success': False,
                    'message': f'企业微信发送失败 - {result.get("errmsg", "未知错误")}',
                    'response_time': elapsed_time,
                    'details': result
                }

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{self.request_id}] 企业微信发送异常: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'企业微信发送异常: {str(e)}',
                'response_time': elapsed_time
            }

    def _send_to_email(self, config, report_data: Dict[str, Any], mr_info: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """
        发送邮件
        """
        try:
            from django.core.mail import send_mail
            from django.conf import settings

            config_dict = config.config_dict
            to_emails = config_dict.get('to', [])
            cc_emails = config_dict.get('cc', [])

            if not to_emails:
                return {
                    'success': False,
                    'message': '邮件收件人未配置',
                    'response_time': time.time() - start_time
                }

            mr_title = mr_info.get('title', '代码审查')
            project_name = mr_info.get('project_name', '未知项目')

            subject = f"AI代码审查报告 - {project_name} - {mr_title}"

            # 构建邮件内容
            html_content = f"""
            <html>
            <body>
                <h2>🤖 AI代码审查报告</h2>
                <p><strong>项目:</strong> {project_name}</p>
                <p><strong>MR:</strong> {mr_title}</p>
                <p><strong>时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <hr>
                <pre style="white-space: pre-wrap; font-family: monospace;">{report_data['content']}</pre>
                <hr>
                <p><small>此邮件由AI代码审查系统自动发送</small></p>
            </body>
            </html>
            """

            recipient_list = to_emails + cc_emails

            result = send_mail(
                subject=subject,
                message=report_data['content'],  # 纯文本版本
                from_email=getattr(settings, 'EMAIL_FROM', 'noreply@example.com'),
                recipient_list=recipient_list,
                html_message=html_content,
                fail_silently=False
            )

            elapsed_time = time.time() - start_time

            if result > 0:
                logger.info(f"[{self.request_id}] 邮件发送成功 - 收件人:{len(recipient_list)}, 耗时:{elapsed_time:.2f}秒")
                return {
                    'success': True,
                    'message': f'邮件发送成功，发送给{result}人',
                    'response_time': elapsed_time,
                    'details': {'recipient_count': result}
                }
            else:
                logger.error(f"[{self.request_id}] 邮件发送失败 - 无收件人")
                return {
                    'success': False,
                    'message': '邮件发送失败',
                    'response_time': elapsed_time
                }

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{self.request_id}] 邮件发送异常: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'邮件发送异常: {str(e)}',
                'response_time': elapsed_time
            }

    def _send_to_custom_webhook(self, channel, report_data: Dict[str, Any], mr_info: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """
        发送到自定义 Webhook URL，支持模板变量替换和自定义 HTTP 方法

        config_data 格式:
        {
            "url": "https://example.com/webhook",
            "method": "POST",
            "headers": {"Authorization": "Bearer xxx", "Content-Type": "application/json"},
            "payload_template": {
                "msgtype": "text",
                "text": {"content": "{review_content}"}
            },
            "timeout": 30
        }
        """
        try:
            import requests

            config_dict = channel.config_dict
            url = config_dict.get('url') or config_dict.get('webhook_url') or config_dict.get('webhook')

            if not url:
                return {
                    'success': False,
                    'message': '自定义Webhook URL未配置',
                    'response_time': time.time() - start_time
                }

            method = config_dict.get('method', 'POST').upper()
            headers = config_dict.get('headers', {})
            payload_template = config_dict.get('payload_template', {})
            req_timeout = config_dict.get('timeout', 30)

            # 构建模板变量
            content_text = report_data.get('content', '')
            if len(content_text) > 3000:
                content_text = content_text[:3000] + "\n\n...(内容过长已截断)"

            template_vars = {
                '{project_name}': mr_info.get('project_name', '未知项目'),
                '{mr_title}': mr_info.get('title', ''),
                '{mr_author}': mr_info.get('author', ''),
                '{mr_url}': mr_info.get('web_url', ''),
                '{review_content}': content_text,
                '{review_score}': str(report_data.get('score', 0)),
                '{timestamp}': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '{source_branch}': mr_info.get('source_branch', ''),
                '{target_branch}': mr_info.get('target_branch', ''),
            }

            # 模板变量替换
            def apply_template(obj):
                if isinstance(obj, str):
                    result = obj
                    for var, value in template_vars.items():
                        result = result.replace(var, value)
                    return result
                elif isinstance(obj, dict):
                    return {apply_template(k): apply_template(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [apply_template(item) for item in obj]
                return obj

            payload = apply_template(payload_template) if payload_template else {
                "msgtype": "text",
                "text": {"content": template_vars['{review_content}']}
            }

            logger.info(f"[{self.request_id}] 自定义Webhook 发送 - URL:{url}, method:{method}")

            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=req_timeout)
            elif method == 'PUT':
                response = requests.put(url, json=payload, headers=headers, timeout=req_timeout)
            elif method == 'PATCH':
                response = requests.patch(url, json=payload, headers=headers, timeout=req_timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=req_timeout)
            else:
                response = requests.post(url, json=payload, headers=headers, timeout=req_timeout)

            elapsed_time = time.time() - start_time

            if 200 <= response.status_code < 300:
                logger.info(f"[{self.request_id}] 自定义Webhook 发送成功 - 耗时:{elapsed_time:.2f}秒, 状态码:{response.status_code}")
                return {
                    'success': True,
                    'message': f'自定义Webhook发送成功 - HTTP {response.status_code}',
                    'response_time': elapsed_time,
                    'details': {'status_code': response.status_code, 'url': url}
                }
            else:
                logger.error(f"[{self.request_id}] 自定义Webhook 发送失败 - 状态码:{response.status_code}, 响应:{response.text[:200]}")
                return {
                    'success': False,
                    'message': f'自定义Webhook发送失败 - HTTP {response.status_code}',
                    'response_time': elapsed_time,
                    'details': {'status_code': response.status_code, 'response': response.text[:200]}
                }

        except requests.exceptions.Timeout:
            elapsed_time = time.time() - start_time
            return {
                'success': False,
                'message': '自定义Webhook请求超时',
                'response_time': elapsed_time
            }
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{self.request_id}] 自定义Webhook 发送异常: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'自定义Webhook发送异常: {str(e)}',
                'response_time': elapsed_time
            }
