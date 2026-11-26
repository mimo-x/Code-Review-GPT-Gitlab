from django.db import models


class ReviewEngineConfig(models.Model):
    """当前使用的审查引擎和它的选项。没有记录时按模型提供商选择引擎，兼容旧部署。"""

    engine = models.CharField(max_length=50)
    options = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'review_engine_config'

    @classmethod
    def current(cls):
        return cls.objects.order_by('-updated_at', '-id').first()

    def __str__(self):
        return self.engine
