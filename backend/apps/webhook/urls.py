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
    path('projects/<int:project_id>/enable/', views.enable_project_review, name='enable_project_review'),
    path('projects/<int:project_id>/disable/', views.disable_project_review, name='disable_project_review'),
    path('projects/stats/', views.project_stats, name='project_stats'),
]
