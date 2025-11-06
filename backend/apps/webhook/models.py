from django.db import models
from django.utils import timezone
import json


class Project(models.Model):
    """
    Model to store GitLab project information
    """
    id = models.AutoField(primary_key=True)
    project_id = models.IntegerField(unique=True, db_index=True)
    project_name = models.CharField(max_length=255)
    project_path = models.CharField(max_length=500)
    project_url = models.URLField(max_length=500)
    namespace = models.CharField(max_length=255)

    # Review settings
    review_enabled = models.BooleanField(default=False, db_index=True)
    auto_review_on_mr = models.BooleanField(default=True)
    gitlab_comment_notifications_enabled = models.BooleanField(default=True)

    # Additional settings - SQLite兼容的JSON字段
    exclude_file_types = models.TextField(default='[]', blank=True)
    ignore_file_patterns = models.TextField(default='[]', blank=True)

    # Metadata - SQLite兼容的JSON字段
    gitlab_data = models.TextField(default='{}', blank=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_webhook_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'projects'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project_id']),
            models.Index(fields=['review_enabled', 'created_at']),
        ]

    def __str__(self):
        return f"{self.project_name} (ID: {self.project_id}) - Review: {'ON' if self.review_enabled else 'OFF'}"

    # JSON字段的getter和setter方法
    @property
    def exclude_file_types_list(self):
        try:
            return json.loads(self.exclude_file_types)
        except (json.JSONDecodeError, TypeError):
            return []

    @exclude_file_types_list.setter
    def exclude_file_types_list(self, value):
        self.exclude_file_types = json.dumps(value)

    @property
    def ignore_file_patterns_list(self):
        try:
            return json.loads(self.ignore_file_patterns)
        except (json.JSONDecodeError, TypeError):
            return []

    @ignore_file_patterns_list.setter
    def ignore_file_patterns_list(self, value):
        self.ignore_file_patterns = json.dumps(value)

    @property
    def gitlab_data_dict(self):
        try:
            return json.loads(self.gitlab_data)
        except (json.JSONDecodeError, TypeError):
            return {}

    @gitlab_data_dict.setter
    def gitlab_data_dict(self, value):
        self.gitlab_data = json.dumps(value)


class WebhookLog(models.Model):
    """
    Model to store webhook event logs
    """
    id = models.AutoField(primary_key=True)
    event_type = models.CharField(max_length=100, db_index=True)
    project_id = models.IntegerField(db_index=True)
    project_name = models.CharField(max_length=255)
    merge_request_iid = models.IntegerField(null=True, blank=True)
    user_name = models.CharField(max_length=255)
    user_email = models.EmailField()
    source_branch = models.CharField(max_length=255)
    target_branch = models.CharField(max_length=255)

    # SQLite兼容的JSON字段
    payload = models.TextField(default='{}')

    # HTTP请求元数据
    request_headers = models.TextField(default='{}')  # JSON格式存储请求头
    request_body_raw = models.TextField(default='')   # 原始请求体
    remote_addr = models.GenericIPAddressField(null=True, blank=True)  # 客户端IP
    user_agent = models.TextField(null=True, blank=True)  # User-Agent
    request_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)  # 请求追踪ID

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'webhook_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['project_id', 'merge_request_iid']),
            models.Index(fields=['request_id']),
            models.Index(fields=['remote_addr']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.project_name} - MR#{self.merge_request_iid}"

    # JSON字段的getter和setter方法
    @property
    def payload_dict(self):
        try:
            return json.loads(self.payload)
        except (json.JSONDecodeError, TypeError):
            return {}

    @payload_dict.setter
    def payload_dict(self, value):
        self.payload = json.dumps(value)

    @property
    def request_headers_dict(self):
        try:
            return json.loads(self.request_headers)
        except (json.JSONDecodeError, TypeError):
            return {}

    @request_headers_dict.setter
    def request_headers_dict(self, value):
        self.request_headers = json.dumps(value)


class MergeRequestReview(models.Model):
    """
    Model to store merge request review results
    """
    id = models.AutoField(primary_key=True)
    project_id = models.IntegerField(db_index=True)
    project_name = models.CharField(max_length=255)
    merge_request_iid = models.IntegerField(db_index=True)
    merge_request_title = models.CharField(max_length=500)
    source_branch = models.CharField(max_length=255)
    target_branch = models.CharField(max_length=255)
    author_name = models.CharField(max_length=255)
    author_email = models.EmailField()

    # Review results
    review_content = models.TextField()
    review_score = models.IntegerField(null=True, blank=True)
    files_reviewed = models.TextField(default='[]', blank=True)  # SQLite兼容的JSON字段
    total_files = models.IntegerField(default=0)

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending',
        db_index=True
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_message = models.TextField(null=True, blank=True)

    # Response tracking
    response_sent = models.BooleanField(default=False)
    response_type = models.CharField(max_length=50, null=True, blank=True)

    # LLM相关字段
    llm_provider = models.CharField(max_length=50, null=True, blank=True)  # LLM提供商
    llm_model = models.CharField(max_length=100, null=True, blank=True)    # LLM模型
    is_mock = models.BooleanField(default=False)                           # 是否为Mock模式

    # 通知相关字段
    notification_sent = models.BooleanField(default=False)                 # 是否发送了通知
    notification_result = models.TextField(default='{}', blank=True)       # 通知结果（JSON格式）

    # 请求追踪
    request_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)  # 请求追踪ID

    class Meta:
        db_table = 'merge_request_reviews'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['project_id', 'merge_request_iid']),
            models.Index(fields=['request_id']),
            models.Index(fields=['is_mock', 'created_at']),
        ]

    def __str__(self):
        return f"{self.project_name} - MR#{self.merge_request_iid} - {self.status}"

    # JSON字段的getter和setter方法
    @property
    def files_reviewed_list(self):
        try:
            return json.loads(self.files_reviewed)
        except (json.JSONDecodeError, TypeError):
            return []

    @files_reviewed_list.setter
    def files_reviewed_list(self, value):
        self.files_reviewed = json.dumps(value)

    @property
    def notification_result_dict(self):
        try:
            return json.loads(self.notification_result)
        except (json.JSONDecodeError, TypeError):
            return {}

    @notification_result_dict.setter
    def notification_result_dict(self, value):
        self.notification_result = json.dumps(value, ensure_ascii=False)


class ProjectNotificationSetting(models.Model):
    """项目选择的通知通道配置"""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='notification_settings')
    channel = models.ForeignKey('llm.NotificationChannel', on_delete=models.CASCADE, related_name='project_settings')
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'project_notification_settings'
        ordering = ['project']
        unique_together = ['project', 'channel']

    def __str__(self):
        return f"Project {self.project.project_id} -> Channel {self.channel_id}"
