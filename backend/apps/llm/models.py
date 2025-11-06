from django.db import models
from django.utils import timezone
import json


class LLMConfig(models.Model):
    """
    LLM配置模型
    """
    id = models.AutoField(primary_key=True)
    provider = models.CharField(
        max_length=50,
        choices=[
            ('openai', 'OpenAI'),
            ('deepseek', 'DeepSeek'),
            ('claude', 'Anthropic Claude'),
            ('gemini', 'Google Gemini'),
        ],
        default='openai'
    )
    model = models.CharField(max_length=100, default='gpt-4')
    api_key = models.CharField(max_length=500, blank=True)
    api_base = models.URLField(max_length=500, blank=True, null=True)

    # 状态和时间戳
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'llm_configs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_provider_display()} - {self.model}"


class GitLabConfig(models.Model):
    """
    GitLab配置模型
    """
    id = models.AutoField(primary_key=True)
    server_url = models.URLField(max_length=500, default='https://gitlab.com')
    private_token = models.CharField(max_length=500, blank=True)
    max_files = models.IntegerField(default=50)
    context_lines = models.IntegerField(default=5)

    # 状态和时间戳
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gitlab_configs'
        ordering = ['-created_at']

    def __str__(self):
        return f"GitLab Config - {self.server_url}"


class NotificationConfig(models.Model):
    """
    通知配置模型 - 支持不同类型的通知配置
    """
    NOTIFICATION_TYPES = [
        ('dingtalk', '钉钉通知'),
        ('gitlab', 'GitLab评论'),
        ('email', '邮件通知'),
        ('slack', 'Slack通知'),
        ('feishu', '飞书通知'),
        ('wechat', '企业微信通知'),
    ]

    id = models.AutoField(primary_key=True)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    enabled = models.BooleanField(default=True)

    # 通用配置字段（JSON格式存储不同通知类型的特定配置）
    config_data = models.TextField(default='{}', blank=True)

    # 状态和时间戳
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_configs'
        ordering = ['-created_at']
        unique_together = ['notification_type']

    def __str__(self):
        return f"{self.get_notification_type_display()} - {'Enabled' if self.enabled else 'Disabled'}"

    @property
    def config_dict(self):
        try:
            return json.loads(self.config_data)
        except (json.JSONDecodeError, TypeError):
            return {}

    @config_dict.setter
    def config_dict(self, value):
        self.config_data = json.dumps(value)

    def get_config_value(self, key, default=None):
        """获取配置项的值"""
        return self.config_dict.get(key, default)

    def set_config_value(self, key, value):
        """设置配置项的值"""
        config = self.config_dict
        config[key] = value
        self.config_dict = config
