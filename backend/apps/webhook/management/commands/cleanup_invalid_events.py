"""
清理所有项目中无效的 webhook 事件 ID

使用方法:
    python manage.py cleanup_invalid_events
"""
from django.core.management.base import BaseCommand
from apps.webhook.models import Project
from apps.llm.models import WebhookEventRule


class Command(BaseCommand):
    help = '清理所有项目中已被删除的 webhook 事件规则 ID'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅显示将要清理的数据，不实际修改数据库',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('运行在 DRY RUN 模式，不会实际修改数据'))

        # 获取所有有效的事件规则 ID
        valid_event_ids = set(WebhookEventRule.objects.values_list('id', flat=True))
        self.stdout.write(f'当前有效的事件规则 ID: {sorted(valid_event_ids)}')

        # 统计信息
        total_projects = 0
        cleaned_projects = 0
        total_invalid_ids = 0

        # 遍历所有项目
        for project in Project.objects.all():
            total_projects += 1
            enabled_ids = project.enabled_webhook_events_list

            if not enabled_ids:
                continue

            # 找出无效的 ID
            invalid_ids = [id for id in enabled_ids if id not in valid_event_ids]

            if invalid_ids:
                cleaned_projects += 1
                total_invalid_ids += len(invalid_ids)

                self.stdout.write(
                    self.style.WARNING(
                        f'\n项目 [{project.project_name}] (ID: {project.project_id})'
                    )
                )
                self.stdout.write(f'  当前配置的事件 ID: {enabled_ids}')
                self.stdout.write(
                    self.style.ERROR(f'  无效的事件 ID: {invalid_ids}')
                )

                if not dry_run:
                    # 过滤掉无效的 ID
                    valid_ids = [id for id in enabled_ids if id in valid_event_ids]
                    project.enabled_webhook_events_list = valid_ids
                    project.save(update_fields=['enabled_webhook_events'])

                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ 已清理，保留的事件 ID: {valid_ids}')
                    )
                else:
                    valid_ids = [id for id in enabled_ids if id in valid_event_ids]
                    self.stdout.write(f'  将保留的事件 ID: {valid_ids}')

        # 输出统计结果
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(f'总项目数: {total_projects}')
        self.stdout.write(f'需要清理的项目数: {cleaned_projects}')
        self.stdout.write(f'清理的无效事件 ID 总数: {total_invalid_ids}')

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n这是 DRY RUN 模式的结果，没有实际修改数据库'
                )
            )
            self.stdout.write('运行 python manage.py cleanup_invalid_events 来实际执行清理')
        else:
            if cleaned_projects > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✓ 成功清理 {cleaned_projects} 个项目中的无效事件 ID'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('\n✓ 所有项目的事件配置都是有效的，无需清理')
                )
