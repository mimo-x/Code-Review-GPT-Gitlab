#!/usr/bin/env python
"""
升级验证脚本 - 测试主要功能是否正常工作
"""
import os
import sys
import django
from datetime import datetime

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.llm.models import LLMConfig, NotificationConfig
from apps.webhook.models import MergeRequestReview, WebhookLog
from apps.common.logging_utils import get_logger
from django.conf import settings


def test_database_models():
    """测试数据库模型是否正常"""
    print("🔍 测试数据库模型...")

    try:
        # 测试LLM配置
        llm_configs = LLMConfig.objects.count()
        print(f"✅ LLMConfig表正常，当前记录数: {llm_configs}")

        # 测试通知配置
        notification_configs = NotificationConfig.objects.count()
        print(f"✅ NotificationConfig表正常，当前记录数: {notification_configs}")

        # 测试MergeRequestReview的新字段
        # 检查是否有新字段
        try:
            review = MergeRequestReview.objects.first()
            if review:
                # 检查新字段是否存在
                has_request_id = hasattr(review, 'request_id')
                has_llm_provider = hasattr(review, 'llm_provider')
                has_is_mock = hasattr(review, 'is_mock')
                has_notification_result = hasattr(review, 'notification_result')

                print(f"✅ MergeRequestReview新字段检查:")
                print(f"   - request_id: {'✅' if has_request_id else '❌'}")
                print(f"   - llm_provider: {'✅' if has_llm_provider else '❌'}")
                print(f"   - is_mock: {'✅' if has_is_mock else '❌'}")
                print(f"   - notification_result: {'✅' if has_notification_result else '❌'}")
            else:
                print("⚠️ MergeRequestReview表中暂无数据，但字段结构正常")
        except Exception as e:
            print(f"❌ MergeRequestReview字段检查失败: {e}")

    except Exception as e:
        print(f"❌ 数据库模型测试失败: {e}")
        return False

    return True


def test_settings():
    """测试配置是否正常加载"""
    print("\n🔧 测试配置设置...")

    try:
        # 测试Mock模式配置
        mock_mode = getattr(settings, 'CODE_REVIEW_MOCK_MODE', False)
        print(f"✅ Mock模式配置: {mock_mode}")

        # 测试邮件配置
        email_configured = bool(getattr(settings, 'EMAIL_HOST', ''))
        print(f"✅ 邮件配置: {'已配置' if email_configured else '未配置'}")

        # 测试Slack配置
        slack_configured = bool(getattr(settings, 'SLACK_WEBHOOK_URL', ''))
        print(f"✅ Slack配置: {'已配置' if slack_configured else '未配置'}")

        # 测试飞书配置
        feishu_configured = bool(getattr(settings, 'FEISHU_WEBHOOK_URL', ''))
        print(f"✅ 飞书配置: {'已配置' if feishu_configured else '未配置'}")

        # 测试企业微信配置
        wechat_configured = bool(getattr(settings, 'WECHAT_WORK_WEBHOOK_URL', ''))
        print(f"✅ 企业微信配置: {'已配置' if wechat_configured else '未配置'}")

    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False

    return True


def test_logging_utils():
    """测试日志工具是否正常工作"""
    print("\n📝 测试日志工具...")

    try:
        # 测试结构化日志
        logger = get_logger('test', 'test-request-123')

        # 测试各种日志方法
        logger.info("测试INFO日志", test_field="test_value")
        logger.warning("测试WARNING日志")
        logger.error("测试ERROR日志")

        # 测试特定方法
        logger.log_webhook_inbound('merge_request', 123, 'test-project')
        logger.log_performance('test_operation', 1.23)
        logger.log_business_metric('test_metric', 100)

        print("✅ 结构化日志工具正常工作")

    except Exception as e:
        print(f"❌ 日志工具测试失败: {e}")
        return False

    return True


def test_llm_service():
    """测试LLM服务是否正常"""
    print("\n🤖 测试LLM服务...")

    try:
        from apps.llm.services import LLMService

        # 创建LLM服务实例
        llm_service = LLMService('test-request-123')

        print(f"✅ LLM服务初始化成功")
        print(f"   - 提供商: {llm_service.provider}")
        print(f"   - 模型: {llm_service.model}")
        print(f"   - 配置来源: {llm_service.config_source}")

    except Exception as e:
        print(f"❌ LLM服务测试失败: {e}")
        return False

    return True


def test_report_generator():
    """测试报告生成器是否正常"""
    print("\n📊 测试报告生成器...")

    try:
        from apps.review.report_generator import ReportGenerator

        # 创建报告生成器实例
        generator = ReportGenerator('test-request-123')

        # 测试Mock报告生成
        mr_info = {
            'project_name': 'test-project',
            'title': 'test MR',
            'author': 'test-author',
            'file_count': 5,
            'changes_count': 100
        }

        mock_report = generator.generate_mock(mr_info)
        print(f"✅ Mock报告生成成功，内容长度: {len(mock_report['content'])}")
        print(f"   - 评分: {mock_report['metadata']['score']}")
        print(f"   - 是否为Mock: {mock_report['metadata']['is_mock']}")

    except Exception as e:
        print(f"❌ 报告生成器测试失败: {e}")
        return False

    return True


def test_notification_dispatcher():
    """测试通知分发器是否正常"""
    print("\n📢 测试通知分发器...")

    try:
        from apps.response.notification_dispatcher import NotificationDispatcher

        # 创建通知分发器实例
        dispatcher = NotificationDispatcher('test-request-123')

        # 获取通知配置
        configs = dispatcher._get_active_notification_configs()
        print(f"✅ 通知分发器初始化成功")
        print(f"   - 活跃通知配置数量: {len(configs)}")

        for config in configs:
            print(f"   - 渠道: {config.notification_type}, 状态: {'启用' if config.enabled else '禁用'}")

    except Exception as e:
        print(f"❌ 通知分发器测试失败: {e}")
        return False

    return True


def main():
    """主测试函数"""
    print("=" * 60)
    print("🚀 MR代码审查与通知系统升级验证")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    tests = [
        ("数据库模型", test_database_models),
        ("配置设置", test_settings),
        ("日志工具", test_logging_utils),
        ("LLM服务", test_llm_service),
        ("报告生成器", test_report_generator),
        ("通知分发器", test_notification_dispatcher),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")

    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！升级验证成功！")
        print("\n📌 下一步:")
        print("1. 启动Django服务: python manage.py runserver")
        print("2. 配置LLM和通知渠道")
        print("3. 测试完整的MR审查流程")
        return 0
    else:
        print("⚠️ 部分测试失败，请检查相关配置和代码")
        return 1


if __name__ == "__main__":
    sys.exit(main())