from djongo import models
from django.utils import timezone


class Project(models.Model):
    """
    Model to store GitLab project information
    """
    _id = models.ObjectIdField()
    project_id = models.IntegerField(unique=True, db_index=True)
    project_name = models.CharField(max_length=255)
    project_path = models.CharField(max_length=500)
    project_url = models.URLField(max_length=500)
    namespace = models.CharField(max_length=255)

    # Review settings
    review_enabled = models.BooleanField(default=False, db_index=True)
    auto_review_on_mr = models.BooleanField(default=True)

    # Additional settings
    exclude_file_types = models.JSONField(default=list, blank=True)
    ignore_file_patterns = models.JSONField(default=list, blank=True)

    # Metadata
    gitlab_data = models.JSONField(default=dict, blank=True)

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


class WebhookLog(models.Model):
    """
    Model to store webhook event logs
    """
    _id = models.ObjectIdField()
    event_type = models.CharField(max_length=100, db_index=True)
    project_id = models.IntegerField(db_index=True)
    project_name = models.CharField(max_length=255)
    merge_request_iid = models.IntegerField(null=True, blank=True)
    user_name = models.CharField(max_length=255)
    user_email = models.EmailField()
    source_branch = models.CharField(max_length=255)
    target_branch = models.CharField(max_length=255)
    payload = models.JSONField()
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
        ]

    def __str__(self):
        return f"{self.event_type} - {self.project_name} - MR#{self.merge_request_iid}"


class MergeRequestReview(models.Model):
    """
    Model to store merge request review results
    """
    _id = models.ObjectIdField()
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
    files_reviewed = models.JSONField(default=list)
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

    class Meta:
        db_table = 'merge_request_reviews'
        ordering = ['-created_at']
        unique_together = ['project_id', 'merge_request_iid']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['project_id', 'merge_request_iid']),
        ]

    def __str__(self):
        return f"{self.project_name} - MR#{self.merge_request_iid} - {self.status}"
