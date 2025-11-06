#!/usr/bin/env python
"""
测试时区转换是否正常工作
"""
import os
import sys
import django

# 设置 Django 环境
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.utils import timezone
from apps.webhook.models import Project, WebhookLog
from apps.webhook.serializers import ProjectSerializer, WebhookLogSerializer
import pytz

def test_timezone_conversion():
    """测试时区转换"""
    print("=" * 60)
    print("时区转换测试")
    print("=" * 60)
    
    # 1. 显示当前时区设置
    print("\n1. Django 时区配置:")
    from django.conf import settings
    print(f"   TIME_ZONE: {settings.TIME_ZONE}")
    print(f"   USE_TZ: {settings.USE_TZ}")
    
    # 2. 获取当前时间
    now_utc = timezone.now()
    print(f"\n2. 当前 UTC 时间: {now_utc}")
    print(f"   时区信息: {now_utc.tzinfo}")
    
    # 3. 转换到上海时区
    shanghai_tz = pytz.timezone('Asia/Shanghai')
    now_shanghai = now_utc.astimezone(shanghai_tz)
    print(f"\n3. 转换后的上海时间: {now_shanghai}")
    print(f"   格式化显示: {now_shanghai.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   时区信息: {now_shanghai.tzinfo}")
    
    # 4. 测试数据库查询和序列化
    print("\n4. 测试数据库数据序列化:")
    
    # 测试 Project
    project = Project.objects.first()
    if project:
        print(f"\n   Project (数据库原始数据):")
        print(f"   - ID: {project.project_id}")
        print(f"   - created_at (UTC): {project.created_at}")
        print(f"   - updated_at (UTC): {project.updated_at}")
        
        # 序列化
        serializer = ProjectSerializer(project)
        data = serializer.data
        print(f"\n   Project (序列化后 - 应该是上海时间):")
        print(f"   - created_at: {data.get('created_at')}")
        print(f"   - updated_at: {data.get('updated_at')}")
    else:
        print("   ⚠️  没有找到 Project 数据")
    
    # 测试 WebhookLog
    log = WebhookLog.objects.first()
    if log:
        print(f"\n   WebhookLog (数据库原始数据):")
        print(f"   - ID: {log.id}")
        print(f"   - created_at (UTC): {log.created_at}")
        
        # 序列化
        serializer = WebhookLogSerializer(log)
        data = serializer.data
        print(f"\n   WebhookLog (序列化后 - 应该是上海时间):")
        print(f"   - created_at: {data.get('created_at')}")
        print(f"   - processed_at: {data.get('processed_at')}")
    else:
        print("   ⚠️  没有找到 WebhookLog 数据")
    
    # 5. 时间差验证
    print(f"\n5. 时区差验证:")
    print(f"   UTC 和上海时间应该相差 8 小时")
    print(f"   UTC: {now_utc.strftime('%H:%M:%S')}")
    print(f"   上海: {now_shanghai.strftime('%H:%M:%S')}")
    hour_diff = now_shanghai.hour - now_utc.hour
    if hour_diff < 0:
        hour_diff += 24
    print(f"   实际时差: {hour_diff} 小时")
    
    if hour_diff == 8:
        print("   ✅ 时区转换正确！")
    else:
        print(f"   ❌ 时区转换错误！预期 8 小时，实际 {hour_diff} 小时")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print("\n重要提示:")
    print("1. 数据库存储的是 UTC 时间（这是正确的）")
    print("2. API 返回的应该是上海时间（通过序列化器转换）")
    print("3. 如果 API 返回的还是 UTC 时间，请重启 Django 服务器")
    print("4. 前端可能需要清除缓存并刷新页面")

if __name__ == '__main__':
    test_timezone_conversion()

