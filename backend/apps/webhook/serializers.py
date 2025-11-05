from rest_framework import serializers
from .models import WebhookLog, MergeRequestReview, Project


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ['_id', 'created_at', 'updated_at', 'last_webhook_at']


class ProjectUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating project settings"""
    class Meta:
        model = Project
        fields = ['review_enabled', 'auto_review_on_mr', 'exclude_file_types', 'ignore_file_patterns']


class WebhookLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookLog
        fields = '__all__'
        read_only_fields = ['_id', 'created_at', 'processed_at']


class MergeRequestReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = MergeRequestReview
        fields = '__all__'
        read_only_fields = ['_id', 'created_at', 'updated_at', 'completed_at']
