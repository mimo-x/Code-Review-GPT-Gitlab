from django.urls import path

from . import views

app_name = 'review'

urlpatterns = [
    path('engine/', views.engine_config, name='engine_config'),
]
