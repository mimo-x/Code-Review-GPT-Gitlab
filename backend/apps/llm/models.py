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
    通知配置模型（兼容旧版本配置，建议使用 NotificationChannel）
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


class WebhookEventRule(models.Model):
    """
    GitLab Webhook 事件识别规则配置
    用于定义如何识别特定的 webhook 事件类型
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, help_text="事件规则的名称，用于展示和选择")
    event_type = models.CharField(max_length=100, help_text="GitLab事件类型，如：Merge Request Hook, Push Hook")
    description = models.TextField(blank=True, help_text="事件规则的详细描述")

    # 事件识别规则，JSON格式存储需要匹配的字段和值
    # 示例：{"object_kind": "merge_request", "object_attributes": {"action": "open"}}
    match_rules = models.TextField(help_text="JSON格式的事件匹配规则")

    # 是否启用此规则
    is_active = models.BooleanField(default=True)

    # 时间戳
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'webhook_event_rules'
        ordering = ['name']
        indexes = [
            models.Index(fields=['event_type']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.event_type})"

    @property
    def match_rules_dict(self):
        """获取匹配规则的字典格式"""
        if not self.match_rules:
            return {}
        try:
            # 首先尝试 JSON 解析
            return json.loads(self.match_rules)
        except (json.JSONDecodeError, TypeError):
            try:
                # 如果失败，尝试使用 ast.literal_eval 解析 Python repr 格式
                import ast
                result = ast.literal_eval(self.match_rules)
                if isinstance(result, dict):
                    return result
                return {}
            except (ValueError, SyntaxError):
                return {}

    @match_rules_dict.setter
    def match_rules_dict(self, value):
        """设置匹配规则的字典格式"""
        self.match_rules = json.dumps(value, ensure_ascii=False)

    def matches_payload(self, payload: dict) -> bool:
        """
        检查给定的 webhook payload 是否匹配此规则

        Args:
            payload: GitLab webhook payload 字典

        Returns:
            bool: 是否匹配规则
        """
        if not self.is_active or not payload:
            return False

        rules = self.match_rules_dict
        if not rules:
            return False

        return self._deep_match(rules, payload)

    def _deep_match(self, rules: dict, data: dict) -> bool:
        """
        深度匹配规则和数据

        Args:
            rules: 匹配规则
            data: 要匹配的数据

        Returns:
            bool: 是否匹配
        """
        for key, value in rules.items():
            if key not in data:
                return False

            if isinstance(value, dict) and isinstance(data[key], dict):
                if not self._deep_match(value, data[key]):
                    return False
            elif data[key] != value:
                return False

        return True


class NotificationChannel(models.Model):
    """面向项目的通知渠道配置，支持同一类型多条记录"""

    NOTIFICATION_TYPES = NotificationConfig.NOTIFICATION_TYPES

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False, help_text="用于新项目的默认通道")
    config_data = models.TextField(default='{}', blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_channels'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.notification_type})"

    @property
    def config_dict(self):
        try:
            # 首先尝试直接解析 JSON
            return json.loads(self.config_data)
        except (json.JSONDecodeError, TypeError):
            try:
                # 如果 JSON 解析失败，尝试解析 Python 字面量格式
                import ast
                return ast.literal_eval(self.config_data) if self.config_data else {}
            except (ValueError, SyntaxError):
                return {}

    @config_dict.setter
    def config_dict(self, value):
        self.config_data = json.dumps(value)


class ClaudeCliConfig(models.Model):
    """
    Claude CLI 配置模型
    用于存储 Claude CLI 执行所需的环境变量和配置
    """
    id = models.AutoField(primary_key=True)

    # Claude CLI 环境变量
    anthropic_base_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="ANTHROPIC_BASE_URL - Claude API 基础地址"
    )
    anthropic_auth_token = models.CharField(
        max_length=500,
        blank=True,
        help_text="ANTHROPIC_AUTH_TOKEN - Claude 认证令牌"
    )

    # Claude CLI 可执行文件路径
    cli_path = models.CharField(
        max_length=500,
        default='claude',
        help_text="Claude CLI 可执行文件路径"
    )

    # 超时设置（秒）
    timeout = models.IntegerField(
        default=300,
        help_text="Claude CLI 执行超时时间（秒）"
    )

    # 状态和时间戳
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'claude_cli_configs'
        ordering = ['-created_at']

    def __str__(self):
        return f"Claude CLI Config - {self.cli_path}"
