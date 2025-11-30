"""
Response services for sending notifications (DingTalk, Slack, Feishu, WeChat Work, Email)
"""
import logging
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests

logger = logging.getLogger(__name__)


class DingTalkService:
    """
    Service for sending DingTalk notifications
    """

    def __init__(self, webhook_url=None, secret=None, request_id=None):
        self.request_id = request_id
        # 优先使用传入的参数，否则从数据库或环境变量加载
        if webhook_url and secret:
            self.webhook_url = webhook_url
            self.secret = secret
        else:
            self._load_config()
            # 如果传入了部分参数，覆盖配置
            if webhook_url:
                self.webhook_url = webhook_url
            if secret:
                self.secret = secret

    def _load_config(self):
        """
        从数据库加载钉钉配置，若不存在则保持为空并记录日志
        """
        try:
            from apps.llm.models import NotificationChannel
            channel = NotificationChannel.objects.filter(
                notification_type='dingtalk',
                is_active=True
            ).order_by('-is_default', '-updated_at').first()

            if channel and (channel.is_default or not getattr(self, 'webhook_url', None)):
                config_dict = channel.config_dict
                self.webhook_url = config_dict.get('webhook_url') or config_dict.get('webhook')
                self.secret = config_dict.get('secret')
                logger.info(f"[{self.request_id}] 钉钉配置从数据库加载成功: {channel.name}")
            else:
                self.webhook_url = getattr(self, 'webhook_url', None)
                self.secret = getattr(self, 'secret', None)
                logger.info(f"[{self.request_id}] 未找到数据库中的钉钉配置")
        except Exception as e:
            logger.warning(f"[{self.request_id}] 钉钉配置加载失败: {e}")
            self.webhook_url = None
            self.secret = None

    def send_markdown(self, title, content):
        """
        Send markdown message to DingTalk
        """
        if not self.webhook_url:
            logger.warning(f"[{self.request_id}] DingTalk webhook URL not configured")
            return {
                'success': False,
                'message': 'DingTalk webhook URL未配置'
            }

        try:
            start_time = time.time()

            # Generate signature if secret is provided
            url = self.webhook_url
            if self.secret:
                timestamp = str(round(time.time() * 1000))
                sign = self._generate_signature(timestamp)
                url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
                logger.debug(f"[{self.request_id}] 钉钉签名生成完成 - timestamp:{timestamp}, sign:{sign}")

            # Build message payload
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": content
                }
            }

            logger.info(f"[{self.request_id}] 开始发送钉钉消息 - URL:{url[:100]}...")
            logger.debug(f"[{self.request_id}] 钉钉消息内容: {payload}")

            # Send request
            response = requests.post(url, json=payload, timeout=30)
            elapsed_time = time.time() - start_time

            # 记录详细的响应信息
            logger.info(f"[{self.request_id}] 钉钉API响应 - 状态码:{response.status_code}, 耗时:{elapsed_time:.2f}秒, 响应内容:{response.text}")

            result = response.json()
            if result.get('errcode') == 0:
                logger.info(f"[{self.request_id}] DingTalk消息发送成功 - 耗时:{elapsed_time:.2f}秒")
                return {
                    'success': True,
                    'message': 'DingTalk消息发送成功',
                    'response_time': elapsed_time,
                    'details': {'errcode': result.get('errcode'), 'response': result}
                }
            else:
                logger.error(f"[{self.request_id}] DingTalk API错误 - 错误码:{result.get('errcode')}, 错误信息:{result.get('errmsg')}, 完整响应:{result}")
                return {
                    'success': False,
                    'message': f'DingTalk API错误: {result.get("errmsg", "未知错误")} (错误码: {result.get("errcode")})',
                    'response_time': elapsed_time,
                    'details': {'response': result, 'http_status': response.status_code}
                }

        except Exception as e:
            elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
            logger.error(f"[{self.request_id}] DingTalk消息发送异常 - {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'DingTalk消息发送异常: {str(e)}',
                'response_time': elapsed_time,
                'details': {'exception': str(e)}
            }

    def _generate_signature(self, timestamp):
        """
        Generate signature for DingTalk webhook
        """
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{self.secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')

        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

        return sign

    # 向后兼容的方法
    def send_markdown_message(self, title, content):
        """
        向后兼容的方法
        """
        result = self.send_markdown(title, content)
        return result.get('success', False)


class SlackService:
    """
    Service for sending Slack notifications
    """

    def __init__(self, webhook_url=None, request_id=None):
        self.request_id = request_id
        # 优先使用传入的参数，否则从数据库或环境变量加载
        if webhook_url:
            self.webhook_url = webhook_url
        else:
            self._load_config()

    def _load_config(self):
        """
        从数据库加载Slack配置，若不存在则保持为空
        """
        try:
            from apps.llm.models import NotificationChannel
            channel = NotificationChannel.objects.filter(
                notification_type='slack',
                is_active=True
            ).order_by('-is_default', '-updated_at').first()

            if channel and (channel.is_default or not getattr(self, 'webhook_url', None)):
                config_dict = channel.config_dict
                self.webhook_url = config_dict.get('webhook_url') or config_dict.get('webhook')
                logger.info(f"[{self.request_id}] Slack配置从数据库加载成功: {channel.name}")
            else:
                self.webhook_url = getattr(self, 'webhook_url', None)
                logger.info(f"[{self.request_id}] 未找到数据库中的 Slack 配置")
        except Exception as e:
            logger.warning(f"[{self.request_id}] Slack配置加载失败: {e}")
            self.webhook_url = None

    def send_message(self, text, blocks=None):
        """
        Send message to Slack
        """
        if not self.webhook_url:
            logger.warning(f"[{self.request_id}] Slack webhook URL not configured")
            return {
                'success': False,
                'message': 'Slack webhook URL未配置'
            }

        try:
            start_time = time.time()

            payload = {"text": text}
            if blocks:
                payload["blocks"] = blocks

            response = requests.post(self.webhook_url, json=payload, timeout=30)
            elapsed_time = time.time() - start_time

            if response.status_code == 200:
                logger.info(f"[{self.request_id}] Slack消息发送成功 - 耗时:{elapsed_time:.2f}秒")
                return {
                    'success': True,
                    'message': 'Slack消息发送成功',
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
            logger.error(f"[{self.request_id}] Slack消息发送异常: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Slack消息发送异常: {str(e)}',
                'response_time': time.time() - start_time if 'start_time' in locals() else 0
            }


class FeishuService:
    """
    Service for sending Feishu notifications
    """

    def __init__(self, webhook_url=None, secret=None, request_id=None):
        self.request_id = request_id
        # 优先使用传入的参数，否则从数据库或环境变量加载
        if webhook_url and secret:
            self.webhook_url = webhook_url
            self.secret = secret
        else:
            self._load_config()
            # 如果传入了部分参数，覆盖配置
            if webhook_url:
                self.webhook_url = webhook_url
            if secret:
                self.secret = secret

    def _load_config(self):
        """
        从数据库加载飞书配置，若不存在则保持为空
        """
        try:
            from apps.llm.models import NotificationChannel
            channel = NotificationChannel.objects.filter(
                notification_type='feishu',
                is_active=True
            ).order_by('-is_default', '-updated_at').first()

            if channel and (channel.is_default or not getattr(self, 'webhook_url', None)):
                config_dict = channel.config_dict
                self.webhook_url = config_dict.get('webhook_url') or config_dict.get('webhook')
                self.secret = config_dict.get('secret')
                logger.info(f"[{self.request_id}] 飞书配置从数据库加载成功: {channel.name}")
            else:
                self.webhook_url = getattr(self, 'webhook_url', None)
                self.secret = getattr(self, 'secret', None)
                logger.info(f"[{self.request_id}] 未找到数据库中的飞书配置")
        except Exception as e:
            logger.warning(f"[{self.request_id}] 飞书配置加载失败: {e}")
            self.webhook_url = None
            self.secret = None

    def send_text(self, text):
        """
        Send simple text message to Feishu (不使用签名)
        """
        if not self.webhook_url:
            logger.warning(f"[{self.request_id}] Feishu webhook URL not configured")
            return {
                'success': False,
                'message': 'Feishu webhook URL未配置'
            }

        try:
            start_time = time.time()

            # 简单的文本消息，不使用签名
            payload = {
                "msg_type": "text",
                "content": {
                    "text": text
                }
            }

            logger.debug(f"[{self.request_id}] 飞书请求payload: {payload}")
            response = requests.post(self.webhook_url, json=payload, timeout=30)
            elapsed_time = time.time() - start_time

            logger.info(f"[{self.request_id}] 飞书API响应 - 状态码:{response.status_code}, 响应内容:{response.text}")

            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    logger.info(f"[{self.request_id}] 飞书消息发送成功 - 耗时:{elapsed_time:.2f}秒")
                    return {
                        'success': True,
                        'message': '飞书消息发送成功',
                        'response_time': elapsed_time,
                        'details': {'code': result.get('code')}
                    }
                else:
                    logger.error(f"[{self.request_id}] 飞书发送失败 - 错误码:{result.get('code')}, 消息:{result.get('msg')}, 完整响应:{result}")
                    return {
                        'success': False,
                        'message': f'飞书API错误: {result.get("msg", "未知错误")}',
                        'response_time': elapsed_time,
                        'details': result
                    }
            else:
                logger.error(f"[{self.request_id}] 飞书发送失败 - 状态码:{response.status_code}")
                return {
                    'success': False,
                    'message': f'飞书发送失败 - HTTP {response.status_code}',
                    'response_time': elapsed_time,
                    'details': {'status_code': response.status_code}
                }

        except Exception as e:
            logger.error(f"[{self.request_id}] 飞书消息发送异常: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'飞书消息发送异常: {str(e)}',
                'response_time': time.time() - start_time if 'start_time' in locals() else 0
            }

    # 保持向后兼容
    def send_card(self, card_content):
        """
        向后兼容方法，转为发送文本消息
        """
        text = str(card_content)
        return self.send_text(text)


class WechatWorkService:
    """
    Service for sending WeChat Work notifications
    """

    def __init__(self, webhook_url=None, request_id=None):
        self.request_id = request_id
        # 优先使用传入的参数，否则从数据库或环境变量加载
        if webhook_url:
            self.webhook_url = webhook_url
        else:
            self._load_config()

    def _load_config(self):
        """
        从数据库加载企业微信配置，若不存在则保持为空
        """
        try:
            from apps.llm.models import NotificationChannel
            channel = NotificationChannel.objects.filter(
                notification_type='wechat',
                is_active=True
            ).order_by('-is_default', '-updated_at').first()

            if channel and (channel.is_default or not getattr(self, 'webhook_url', None)):
                config_dict = channel.config_dict
                self.webhook_url = config_dict.get('webhook_url') or config_dict.get('webhook')
                logger.info(f"[{self.request_id}] 企业微信配置从数据库加载成功: {channel.name}")
            else:
                self.webhook_url = getattr(self, 'webhook_url', None)
                logger.info(f"[{self.request_id}] 未找到数据库中的企业微信配置")
        except Exception as e:
            logger.warning(f"[{self.request_id}] 企业微信配置加载失败: {e}")
            self.webhook_url = None

    def send_text(self, content):
        """
        Send simple text message to WeChat Work
        """
        if not self.webhook_url:
            logger.warning(f"[{self.request_id}] WeChat Work webhook URL not configured")
            return {
                'success': False,
                'message': '企业微信webhook URL未配置'
            }

        try:
            start_time = time.time()

            payload = {
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }

            response = requests.post(self.webhook_url, json=payload, timeout=30)
            elapsed_time = time.time() - start_time

            result = response.json()
            if result.get('errcode') == 0:
                logger.info(f"[{self.request_id}] 企业微信消息发送成功 - 耗时:{elapsed_time:.2f}秒")
                return {
                    'success': True,
                    'message': '企业微信消息发送成功',
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
            logger.error(f"[{self.request_id}] 企业微信消息发送异常: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'企业微信消息发送异常: {str(e)}',
                'response_time': time.time() - start_time if 'start_time' in locals() else 0
            }

    # 向后兼容方法
    def send_markdown(self, content):
        """
        向后兼容方法，转为发送文本消息
        """
        return self.send_text(content)


class EmailService:
    """
    Service for sending email notifications
    """

    def __init__(self, request_id=None):
        self.request_id = request_id

    def send_email(self, subject, message, html_message=None, from_email=None, to=None, cc=None):
        """
        Send email notification
        """
        try:
            from django.core.mail import send_mail
            from django.conf import settings

            start_time = time.time()

            # 使用配置的默认值
            if from_email is None:
                from_email = getattr(settings, 'EMAIL_FROM', 'noreply@example.com')

            recipient_list = to or []
            if cc:
                recipient_list.extend(cc)

            if not recipient_list:
                return {
                    'success': False,
                    'message': '邮件收件人未配置',
                    'response_time': 0
                }

            result = send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
                html_message=html_message,
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
            elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
            logger.error(f"[{self.request_id}] 邮件发送异常: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'邮件发送异常: {str(e)}',
                'response_time': elapsed_time
            }


class NotificationService:
    """
    Unified notification service
    """

    def __init__(self, request_id=None):
        self.request_id = request_id
        self.dingtalk = DingTalkService(request_id=request_id)
        self.slack = SlackService(request_id=request_id)
        self.feishu = FeishuService(request_id=request_id)
        self.wechat_work = WechatWorkService(request_id=request_id)
        self.email = EmailService(request_id=request_id)

    def notify_review_completed(self, project_name, merge_request_iid, review_content):
        """
        Notify when code review is completed
        """
        title = f"代码审查完成 - {project_name}"
        content = f"""
## {title}

**MR #{merge_request_iid}**

{review_content}

---
*Generated by Code Review GPT*
        """

        return self.dingtalk.send_markdown_message(title, content)
