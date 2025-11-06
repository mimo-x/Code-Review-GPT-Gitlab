#!/usr/bin/env python
"""
数据库初始化脚本
用于创建和初始化SQLite数据库
"""

import os
import sys
import django

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.core.management import execute_from_command_line
from django.db import connection
from apps.webhook.models import Project, WebhookLog, MergeRequestReview


def check_database_status():
    """检查数据库状态"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"当前数据库表: {tables}")
        return True
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return False


def init_database():
    """初始化数据库"""
    print("开始初始化数据库...")

    # 创建迁移文件
    print("创建迁移文件...")
    execute_from_command_line(['manage.py', 'makemigrations'])

    # 执行迁移
    print("执行数据库迁移...")
    execute_from_command_line(['manage.py', 'migrate'])

    # 创建超级用户（可选）
    print("是否创建超级用户？(y/n): ", end="")
    create_superuser = input().lower() == 'y'

    if create_superuser:
        execute_from_command_line([
            'manage.py', 'createsuperuser',
            '--username', 'admin',
            '--email', 'admin@example.com'
        ])

    print("数据库初始化完成！")


def reset_database():
    """重置数据库"""
    print("警告：这将删除所有数据！")
    print("确定要继续吗？(yes/no): ", end="")
    confirm = input()

    if confirm.lower() == 'yes':
        # 删除数据库文件
        db_path = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
        if os.path.exists(db_path):
            os.remove(db_path)
            print("已删除旧数据库文件")

        # 重新初始化
        init_database()
    else:
        print("操作已取消")


def show_database_info():
    """显示数据库信息"""
    print("=== 数据库信息 ===")

    # 检查使用的数据库类型
    from django.conf import settings
    db_config = settings.DATABASES['default']
    print(f"数据库引擎: {db_config['ENGINE']}")

    if 'sqlite' in db_config['ENGINE']:
        print(f"数据库文件: {db_config['NAME']}")

        # 检查文件大小
        if os.path.exists(db_config['NAME']):
            size = os.path.getsize(db_config['NAME'])
            print(f"文件大小: {size / 1024:.2f} KB")

    # 显示数据统计
    try:
        project_count = Project.objects.count()
        webhook_count = WebhookLog.objects.count()
        review_count = MergeRequestReview.objects.count()

        print(f"\n=== 数据统计 ===")
        print(f"项目数量: {project_count}")
        print(f"Webhook日志数量: {webhook_count}")
        print(f"审查记录数量: {review_count}")

        if project_count > 0:
            enabled_count = Project.objects.filter(review_enabled=True).count()
            print(f"启用审查的项目: {enabled_count}")

    except Exception as e:
        print(f"获取数据统计失败: {e}")


def test_database():
    """测试数据库连接"""
    print("测试数据库连接...")

    try:
        # 测试基本查询
        Project.objects.count()
        WebhookLog.objects.count()
        MergeRequestReview.objects.count()

        print("✅ 数据库连接正常")
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python init_database.py init     - 初始化数据库")
        print("  python init_database.py reset    - 重置数据库")
        print("  python init_database.py info     - 显示数据库信息")
        print("  python init_database.py test     - 测试数据库连接")
        print("  python init_database.py status   - 检查数据库状态")
        return

    command = sys.argv[1]

    if command == 'init':
        init_database()
    elif command == 'reset':
        reset_database()
    elif command == 'info':
        show_database_info()
    elif command == 'test':
        test_database()
    elif command == 'status':
        check_database_status()
    else:
        print(f"未知命令: {command}")


if __name__ == '__main__':
    main()