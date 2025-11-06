"""
URL configuration for Code Review GPT project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health_check(request):
    """Health check endpoint"""
    return JsonResponse({'status': 'ok', 'message': 'Code Review GPT is running'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),
    path('api/webhook/', include('apps.webhook.urls')),
    path('api/review/', include('apps.review.urls')),
    path('api/', include('apps.llm.urls')),
]
