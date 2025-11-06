from django.urls import path
from . import views

app_name = 'webhook'

urlpatterns = [
    # Webhook endpoints
    path('gitlab/', views.gitlab_webhook, name='gitlab_webhook'),

    # Project management endpoints
    path('projects/', views.list_projects, name='list_projects'),
    path('projects/<int:project_id>/', views.get_project, name='get_project'),
    path('projects/<int:project_id>/update/', views.update_project, name='update_project'),
    path('projects/<int:project_id>/notifications/', views.get_project_notifications, name='get_project_notifications'),
    path('projects/<int:project_id>/notifications/update/', views.update_project_notifications, name='update_project_notifications'),
    path('projects/<int:project_id>/enable/', views.enable_project_review, name='enable_project_review'),
    path('projects/<int:project_id>/disable/', views.disable_project_review, name='disable_project_review'),
    path('projects/<int:project_id>/webhook-logs/', views.project_webhook_logs, name='project_webhook_logs'),
    path('projects/<int:project_id>/review-history/', views.project_review_history, name='project_review_history'),

    # Statistics endpoints
    path('projects/stats/', views.project_stats, name='project_stats'),

    # Reviews and Logs API endpoints
    path('reviews/', views.list_reviews, name='list_reviews'),
    path('logs/', views.list_logs, name='list_logs'),

    # Mock API endpoints for testing
    path('mock/reviews/', views.mock_reviews, name='mock_reviews'),
    path('mock/logs/', views.mock_logs, name='mock_logs'),
]
