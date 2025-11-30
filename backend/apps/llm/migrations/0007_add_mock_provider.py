# Generated manually to add mock provider choice
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("llm", "0006_claudecliconfig"),
    ]

    operations = [
        migrations.AlterField(
            model_name="llmconfig",
            name="provider",
            field=models.CharField(
                choices=[
                    ("openai", "OpenAI"),
                    ("deepseek", "DeepSeek"),
                    ("claude", "Anthropic Claude"),
                    ("gemini", "Google Gemini"),
                    ("mock", "Mock (No LLM)"),
                ],
                default="openai",
                max_length=50,
            ),
        ),
    ]
