# Generated migration: add custom_webhook notification type
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('llm', '0009_add_llmconfig_timeout'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notificationchannel',
            name='notification_type',
            field=models.CharField(choices=[
                ('dingtalk', '钉钉通知'),
                ('gitlab', 'GitLab评论'),
                ('email', '邮件通知'),
                ('slack', 'Slack通知'),
                ('feishu', '飞书通知'),
                ('wechat', '企业微信通知'),
                ('custom_webhook', '自定义Webhook'),
            ], max_length=50),
        ),
        migrations.AlterField(
            model_name='notificationconfig',
            name='notification_type',
            field=models.CharField(choices=[
                ('dingtalk', '钉钉通知'),
                ('gitlab', 'GitLab评论'),
                ('email', '邮件通知'),
                ('slack', 'Slack通知'),
                ('feishu', '飞书通知'),
                ('wechat', '企业微信通知'),
                ('custom_webhook', '自定义Webhook'),
            ], max_length=50),
        ),
    ]
