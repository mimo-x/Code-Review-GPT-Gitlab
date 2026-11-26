"""审查引擎配置：可选的引擎、每个引擎的配置项，以及当前选用的引擎。"""
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.api_auth.authentication import CookieTokenAuthentication
from apps.llm.models import LLMConfig

from .engines import ENGINES, current_engine
from .models import ReviewEngineConfig


@api_view(['GET', 'PUT'])
@authentication_classes([CookieTokenAuthentication])
@permission_classes([IsAuthenticated])
def engine_config(request):
    """GET 返回当前引擎和所有引擎的配置项；PUT 保存 {engine, options}。"""
    if request.method == 'PUT':
        if not isinstance(request.data, dict):
            return Response({'message': '配置必须是对象'}, status=status.HTTP_400_BAD_REQUEST)
        kind = request.data.get('engine')
        if not isinstance(kind, str) or kind not in ENGINES:
            return Response({'message': f'不支持的审查引擎: {kind}'}, status=status.HTTP_400_BAD_REQUEST)
        options = request.data.get('options')
        if options is None:
            options = {}
        if not isinstance(options, dict):
            return Response({'message': 'options 必须是对象'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            cleaned = ENGINES[kind].clean_options(options)
        except ValueError as exc:
            return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            config = ReviewEngineConfig.current() or ReviewEngineConfig()
            config.engine, config.options = kind, cleaned
            config.save()
    return Response(_payload())


def _payload() -> dict:
    kind, options = current_engine(LLMConfig.objects.filter(is_active=True).first())
    try:
        cleaned = ENGINES[kind].clean_options(options)
    except ValueError:
        cleaned = ENGINES[kind].clean_options({})
    return {
        'engine': kind,
        'options': cleaned,
        'configured': ReviewEngineConfig.current() is not None,
        'engines': [engine.describe() for engine in ENGINES.values()],
    }
