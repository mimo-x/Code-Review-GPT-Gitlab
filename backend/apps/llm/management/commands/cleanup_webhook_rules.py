from django.core.management.base import BaseCommand
from apps.llm.models import WebhookEventRule
from apps.webhook.models import Project


class Command(BaseCommand):
    help = '清理所有 webhook event rules 和项目中的相关引用'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('开始清理 webhook event rules...'))

        # 统计数据
        rules_count = WebhookEventRule.objects.count()

        # 清理所有项目中的 enabled_webhook_events
        projects = Project.objects.all()
        updated_projects = 0

        for project in projects:
            if project.enabled_webhook_events:
                # 清空项目的启用事件列表
                project.enabled_webhook_events = '[]'
                project.save()
                updated_projects += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  清理项目: {project.project_name} (ID: {project.id})')
                )

        # 删除所有 webhook event rules
        WebhookEventRule.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(f'\n清理完成!')
        )
        self.stdout.write(
            self.style.SUCCESS(f'  删除了 {rules_count} 条 webhook event rules')
        )
        self.stdout.write(
            self.style.SUCCESS(f'  清理了 {updated_projects} 个项目的事件配置')
        )
