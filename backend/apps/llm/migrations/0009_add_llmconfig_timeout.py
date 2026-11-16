# Generated migration: add timeout field to LLMConfig
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('llm', '0008_add_unionllm_litellm_providers'),
    ]

    operations = [
        migrations.AddField(
            model_name='llmconfig',
            name='timeout',
            field=models.IntegerField(default=600, help_text='LLM API 调用超时时间（秒），默认 600 秒'),
        ),
    ]
