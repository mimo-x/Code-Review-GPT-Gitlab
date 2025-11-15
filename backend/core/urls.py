"""
URL configuration for Code Review GPT project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from apps.webhook import urls as webhook_urls
from apps.review import urls as review_urls
from apps.llm import urls as llm_urls
import psutil
import time
from datetime import datetime


# 记录服务启动时间
START_TIME = time.time()


def health_check(request):
    """Health check endpoint"""
    return JsonResponse({'status': 'ok', 'message': 'Code Review GPT is running'})


def system_info(request):
    """System information endpoint"""
    try:
        import sys
        import platform
        import django

        # CPU 使用率
        cpu_percent = psutil.cpu_percent(interval=1)

        # 内存信息
        memory = psutil.virtual_memory()
        memory_used_gb = memory.used / (1024 ** 3)
        memory_total_gb = memory.total / (1024 ** 3)
        memory_percent = memory.percent

        # 运行时间
        uptime_seconds = time.time() - START_TIME
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)

        if days > 0:
            uptime_str = f"{days}天 {hours}小时 {minutes}分钟"
        elif hours > 0:
            uptime_str = f"{hours}小时 {minutes}分钟"
        else:
            uptime_str = f"{minutes}分钟"

        # Python 版本
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        # Django 版本
        django_version = django.get_version()

        # 操作系统信息
        os_info = f"{platform.system()} {platform.release()}"

        # 项目版本 (可以从配置文件或环境变量读取)
        project_version = "v1.0.0"  # 可以从settings或环境变量获取

        return JsonResponse({
            'status': 'ok',
            # 资源使用信息
            'cpu': round(cpu_percent, 1),
            'memory': round(memory_percent, 1),
            'memoryUsed': f"{memory_used_gb:.1f} GB",
            'memoryTotal': f"{memory_total_gb:.1f} GB",
            'uptime': uptime_str,
            # 系统信息
            'projectName': 'Code Review GPT',
            'projectVersion': project_version,
            'pythonVersion': python_version,
            'djangoVersion': django_version,
            'osInfo': os_info,
            'serverStatus': 'running'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),
    path('api/system/info', system_info, name='system_info'),
    path('api/webhook/', include(webhook_urls)),
    path('api/review/', include(review_urls)),
    path('api/', include(llm_urls)),
]
