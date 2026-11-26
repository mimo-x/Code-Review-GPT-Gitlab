from urllib.parse import urlsplit

from django.db import migrations, models
import django.db.models.deletion


PRESETS = {
    'openai': ('OpenAI', 'openai'),
    'deepseek': ('DeepSeek', 'deepseek'),
    'gemini': ('Google Gemini', 'google'),
    'unionllm': ('UnionLLM', ''),
    'litellm': ('LiteLLM', ''),
}


def migrate_model_catalog(apps, schema_editor):
    configurations = apps.get_model('llm', 'LLMConfig').objects.using(schema_editor.connection.alias)
    providers = apps.get_model('llm', 'LLMProvider').objects.using(schema_editor.connection.alias)
    groups = {}
    for config in configurations.filter(provider__in=PRESETS).order_by('id').iterator():
        connection = (config.provider, config.api_base, config.api_key, config.timeout)
        if connection not in groups:
            name, preset = PRESETS[config.provider]
            if config.provider == 'openai' and config.api_base:
                hostname = urlsplit(config.api_base).hostname
                if hostname and hostname != 'api.openai.com':
                    name, preset = hostname, 'custom'
            groups[connection] = providers.create(
                name=name[:80], preset=preset, provider=config.provider, api_base=config.api_base,
                api_key=config.api_key, timeout=config.timeout if config.timeout > 0 else 600,
            )
        configurations.filter(pk=config.pk).update(model_provider=groups[connection], api_key='')


def restore_model_configs(apps, schema_editor):
    configurations = apps.get_model('llm', 'LLMConfig').objects.using(schema_editor.connection.alias)
    for config in configurations.filter(model_provider__isnull=False).select_related('model_provider').iterator():
        connection = config.model_provider
        provider = connection.provider
        model = config.model
        if provider == 'anthropic':
            provider = 'litellm'
            if not model.startswith('anthropic/'):
                model = f'anthropic/{model}'
        configurations.filter(pk=config.pk).update(
            provider=provider, model=model, api_base=connection.api_base, api_key=connection.api_key,
            timeout=connection.timeout,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('llm', '0010_add_custom_webhook'),
    ]

    operations = [
        migrations.CreateModel(
            name='LLMProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('preset', models.CharField(blank=True, max_length=50)),
                ('provider', models.CharField(choices=[('openai', 'OpenAI 兼容'), ('deepseek', 'DeepSeek'), ('anthropic', 'Anthropic Messages'), ('gemini', 'Gemini 原生'), ('unionllm', 'UnionLLM'), ('litellm', 'LiteLLM')], max_length=50)),
                ('api_key', models.CharField(blank=True, max_length=500)),
                ('api_base', models.URLField(blank=True, max_length=500, null=True)),
                ('timeout', models.PositiveIntegerField(default=600)),
            ],
            options={
                'ordering': ['name', 'id'],
            },
        ),
        migrations.AddField(
            model_name='llmconfig',
            name='model_provider',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='models', to='llm.llmprovider'),
        ),
        migrations.RunPython(migrate_model_catalog, restore_model_configs),
    ]
