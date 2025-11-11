"""
URL configuration for Code Review GPT project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from apps.webhook import urls as webhook_urls       
from apps.review import urls as review_urls
from apps.llm import urls as llm_urls


def health_check(request):
    """Health check endpoint"""
    return JsonResponse({'status': 'ok', 'message': 'Code Review GPT is running'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),
    path('api/webhook/', include(webhook_urls)),
    path('api/review/', include(review_urls)),
    path('api/', include(llm_urls)),
]
