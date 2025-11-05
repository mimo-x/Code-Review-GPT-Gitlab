from django.apps import AppConfig


class WebhookConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.webhook'
    verbose_name = 'Webhook Management'
