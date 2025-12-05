from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('llm', '0007_add_mock_provider'),
    ]

    operations = [
        migrations.AlterField(
            model_name='claudecliconfig',
            name='anthropic_base_url',
            field=models.TextField(blank=True, db_column='anthropic_base_url', help_text='auth.json 文件内容'),
        ),
        migrations.AlterField(
            model_name='claudecliconfig',
            name='anthropic_auth_token',
            field=models.TextField(blank=True, db_column='anthropic_auth_token', help_text='opencode.json 配置文件内容'),
        ),
        migrations.AddField(
            model_name='claudecliconfig',
            name='env_content',
            field=models.TextField(blank=True, help_text='.env 文件内容（可选）'),
        ),
    ]
