from rest_framework import serializers
from .models import LLMConfig, GitLabConfig, NotificationConfig


class LLMConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLMConfig
        fields = ['id', 'provider', 'model', 'api_key', 'api_base', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        # 如果创建新的激活配置，先禁用其他配置
        if validated_data.get('is_active', True):
            LLMConfig.objects.filter(is_active=True).update(is_active=False)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # 如果设置为激活状态，先禁用其他配置
        if validated_data.get('is_active', False) and not instance.is_active:
            LLMConfig.objects.filter(is_active=True).update(is_active=False)
        return super().update(instance, validated_data)


class GitLabConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = GitLabConfig
        fields = ['id', 'server_url', 'private_token', 'max_files', 'context_lines', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'private_token': {'write_only': True}
        }

    def create(self, validated_data):
        # 如果创建新的激活配置，先禁用其他配置
        if validated_data.get('is_active', True):
            GitLabConfig.objects.filter(is_active=True).update(is_active=False)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # 如果设置为激活状态，先禁用其他配置
        if validated_data.get('is_active', False) and not instance.is_active:
            GitLabConfig.objects.filter(is_active=True).update(is_active=False)
        return super().update(instance, validated_data)


class NotificationConfigSerializer(serializers.ModelSerializer):
    config_data = serializers.JSONField(write_only=True, required=False)

    class Meta:
        model = NotificationConfig
        fields = ['id', 'notification_type', 'enabled', 'config_data', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        """自定义输出格式，将config_data扁平化"""
        data = super().to_representation(instance)

        # 直接从实例获取config_data
        config_data = instance.config_data
        if config_data is None:
            config_data = {}

        # 如果config_data是字符串，尝试解析为字典
        if isinstance(config_data, str):
            try:
                import ast
                config_data = ast.literal_eval(config_data)
            except (ValueError, SyntaxError):
                try:
                    import json
                    config_data = json.loads(config_data)
                except (json.JSONDecodeError, TypeError):
                    config_data = {}

        # 根据通知类型，将特定配置项提取到顶层
        if instance.notification_type == 'dingtalk':
            data['webhook'] = config_data.get('webhook', '')
            data['secret'] = config_data.get('secret', '')
        elif instance.notification_type == 'email':
            data['smtp_host'] = config_data.get('smtp_host', '')
            data['smtp_port'] = config_data.get('smtp_port', '')
            data['username'] = config_data.get('username', '')
            data['password'] = config_data.get('password', '')
            data['from_email'] = config_data.get('from_email', '')
        elif instance.notification_type == 'slack':
            data['webhook_url'] = config_data.get('webhook_url', '')
            data['channel'] = config_data.get('channel', '')
        elif instance.notification_type == 'feishu':
            data['webhook'] = config_data.get('webhook', '')
            data['app_id'] = config_data.get('app_id', '')
            data['app_secret'] = config_data.get('app_secret', '')
        elif instance.notification_type == 'wechat':
            data['corp_id'] = config_data.get('corp_id', '')
            data['corp_secret'] = config_data.get('corp_secret', '')
            data['agent_id'] = config_data.get('agent_id', '')
            data['webhook'] = config_data.get('webhook', '')

        return data

    def to_internal_value(self, data):
        """将扁平化的数据转换为内部格式"""
        # 提取特定类型的配置项
        config_data = {}
        notification_type = data.get('notification_type')

        if notification_type == 'dingtalk':
            config_data = {
                'webhook': data.get('webhook', ''),
                'secret': data.get('secret', '')
            }
        elif notification_type == 'email':
            config_data = {
                'smtp_host': data.get('smtp_host', ''),
                'smtp_port': data.get('smtp_port', ''),
                'username': data.get('username', ''),
                'password': data.get('password', ''),
                'from_email': data.get('from_email', '')
            }
        elif notification_type == 'slack':
            config_data = {
                'webhook_url': data.get('webhook_url', ''),
                'channel': data.get('channel', '')
            }
        elif notification_type == 'feishu':
            config_data = {
                'webhook': data.get('webhook', ''),
                'app_id': data.get('app_id', ''),
                'app_secret': data.get('app_secret', '')
            }
        elif notification_type == 'wechat':
            config_data = {
                'corp_id': data.get('corp_id', ''),
                'corp_secret': data.get('corp_secret', ''),
                'agent_id': data.get('agent_id', ''),
                'webhook': data.get('webhook', '')
            }

        # 清理特定类型的字段，保留通用字段
        clean_data = {}
        for field in self.fields:
            if field in data:
                clean_data[field] = data[field]

        clean_data['config_data'] = config_data
        return super().to_internal_value(clean_data)


class ConfigSummarySerializer(serializers.Serializer):
    """配置摘要序列化器，用于返回所有配置的概览"""
    llm = LLMConfigSerializer(source='active_llm_config', read_only=True)
    gitlab = GitLabConfigSerializer(source='active_gitlab_config', read_only=True)
    notifications = NotificationConfigSerializer(many=True, read_only=True)