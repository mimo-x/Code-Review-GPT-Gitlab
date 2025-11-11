#!/usr/bin/env python
"""
测试项目级 Webhook 事件自定义 Prompt 功能

测试场景：
1. 创建测试项目
2. 为项目启用 webhook 事件
3. 创建自定义 prompt 配置
4. 测试 prompt 变量替换
5. 清理测试数据
"""

import os
import sys
import django

# 设置 Django 环境
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.webhook.models import Project, ProjectWebhookEventPrompt
from apps.llm.models import WebhookEventRule


def test_prompt_feature():
    print("=" * 80)
    print("测试项目级 Webhook 事件自定义 Prompt 功能")
    print("=" * 80)

    # 1. 获取或创建测试项目
    print("\n[步骤 1] 获取或创建测试项目...")
    project, created = Project.objects.get_or_create(
        project_id=999999,
        defaults={
            'project_name': 'Test Project for Custom Prompts',
            'project_path': 'test/custom-prompts',
            'project_url': 'https://gitlab.com/test/custom-prompts',
            'namespace': 'test',
            'review_enabled': True
        }
    )
    if created:
        print(f"✓ 创建新项目: {project.project_name}")
    else:
        print(f"✓ 使用现有项目: {project.project_name}")

    # 2. 获取可用的 webhook 事件规则
    print("\n[步骤 2] 获取可用的 webhook 事件规则...")
    event_rules = WebhookEventRule.objects.filter(is_active=True)
    if not event_rules.exists():
        print("✗ 没有找到可用的 webhook 事件规则")
        print("  请先运行: python manage.py shell -c \"from apps.llm.views import WebhookEventRuleViewSet; WebhookEventRuleViewSet().initialize_defaults(None)\"")
        return

    print(f"✓ 找到 {event_rules.count()} 个可用的事件规则:")
    for rule in event_rules:
        print(f"  - {rule.name} ({rule.event_type})")

    # 3. 为项目启用第一个事件规则
    print("\n[步骤 3] 为项目启用事件规则...")
    first_rule = event_rules.first()
    project.enabled_webhook_events_list = [first_rule.id]
    project.save()
    print(f"✓ 已为项目启用事件规则: {first_rule.name}")

    # 4. 创建自定义 Prompt 配置
    print("\n[步骤 4] 创建自定义 Prompt 配置...")
    custom_prompt_text = """# {project_name} 代码审查

请对以下 Merge Request 进行详细审查：

**MR 信息**
- 标题: {title}
- 作者: {author}
- 分支: {source_branch} → {target_branch}
- MR ID: #{mr_iid}

**变更统计**
- 文件数: {file_count}
- 代码行数: {changes_count}

**审查重点**
1. 代码安全性（SQL注入、XSS等）
2. 性能优化建议
3. 代码规范检查
4. 最佳实践建议

请提供具体的改进建议和代码示例。
"""

    prompt_config, created = ProjectWebhookEventPrompt.objects.update_or_create(
        project=project,
        event_rule=first_rule,
        defaults={
            'custom_prompt': custom_prompt_text,
            'use_custom': True
        }
    )

    if created:
        print(f"✓ 创建新的 Prompt 配置")
    else:
        print(f"✓ 更新现有的 Prompt 配置")

    # 5. 测试 Prompt 变量替换
    print("\n[步骤 5] 测试 Prompt 变量替换...")
    test_context = {
        'project_name': 'My Awesome Project',
        'project_id': 12345,
        'author': 'John Doe',
        'title': 'Fix critical bug in authentication',
        'description': 'This MR fixes a critical security issue',
        'source_branch': 'feature/fix-auth-bug',
        'target_branch': 'main',
        'mr_iid': 42,
        'file_count': 5,
        'changes_count': 123
    }

    rendered_prompt = prompt_config.render_prompt(test_context)

    print("\n渲染前的 Prompt (前100字符):")
    print(f"  {custom_prompt_text[:100]}...")

    print("\n渲染后的 Prompt:")
    print("-" * 80)
    print(rendered_prompt)
    print("-" * 80)

    # 6. 验证替换结果
    print("\n[步骤 6] 验证变量替换结果...")
    checks = [
        ('{project_name}' not in rendered_prompt, "project_name 已替换"),
        ('{author}' not in rendered_prompt, "author 已替换"),
        ('{title}' not in rendered_prompt, "title 已替换"),
        ('{mr_iid}' not in rendered_prompt, "mr_iid 已替换"),
        ('My Awesome Project' in rendered_prompt, "包含实际项目名"),
        ('John Doe' in rendered_prompt, "包含实际作者名"),
        ('#42' in rendered_prompt, "包含实际 MR ID"),
    ]

    all_passed = True
    for check, description in checks:
        if check:
            print(f"✓ {description}")
        else:
            print(f"✗ {description}")
            all_passed = False

    # 7. 测试总结
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ 所有测试通过！")
    else:
        print("✗ 部分测试失败")

    print("\n[清理] 是否删除测试数据？ (测试项目和 Prompt 配置)")
    response = input("输入 'yes' 删除，其他键保留: ")
    if response.lower() == 'yes':
        prompt_config.delete()
        project.delete()
        print("✓ 已删除测试数据")
    else:
        print("✓ 保留测试数据")
        print(f"  项目ID: {project.project_id}")
        print(f"  Prompt配置ID: {prompt_config.id}")

    print("=" * 80)


if __name__ == '__main__':
    test_prompt_feature()
