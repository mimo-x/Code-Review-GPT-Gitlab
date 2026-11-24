"""后台接口访问控制。"""
import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIClient

from apps.llm.models import GitLabConfig, LLMConfig

USERNAME = 'test-admin'
PASSWORD = 'test-password'
SUMMARY_URL = '/api/configs/summary/'
BATCH_UPDATE_URL = '/api/configs/batch_update/'
PUBLIC_VIEWS = {'gitlab_webhook', 'login', 'logout', 'check_auth'}


def api_views(patterns=None, prefix=''):
    patterns = get_resolver().url_patterns if patterns is None else patterns
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from api_views(pattern.url_patterns, route)
        elif isinstance(pattern, URLPattern) and route.startswith('api/'):
            yield route, pattern.callback


@pytest.fixture
def secrets_configured(db):
    GitLabConfig.objects.create(server_url='https://gitlab.invalid', private_token='gitlab-secret')
    LLMConfig.objects.create(provider='openai', model='test', api_key='llm-secret')


@pytest.fixture
def logged_in(db, monkeypatch):
    monkeypatch.setenv('DEFAULT_USERNAME', USERNAME)
    monkeypatch.setenv('DEFAULT_PASSWORD', PASSWORD)
    client = APIClient()
    response = client.post('/api/auth/login', {'username': USERNAME, 'password': PASSWORD}, format='json')
    assert response.status_code == 200
    yield client
    client.post('/api/auth/logout')


def test_every_api_route_requires_login_unless_explicitly_public():
    exposed = []
    for route, callback in api_views():
        view_class = getattr(callback, 'cls', None)
        if getattr(view_class, '__name__', callback.__name__) in PUBLIC_VIEWS:
            continue
        if view_class is None or IsAuthenticated not in view_class.permission_classes:
            exposed.append(route)
    assert exposed == []


@pytest.mark.parametrize('method,url', [
    ('get', SUMMARY_URL),
    ('post', BATCH_UPDATE_URL),
    ('get', '/api/llm-configs/'),
    ('get', '/api/gitlab-configs/'),
    ('get', '/api/notification-channels/'),
    ('post', '/api/webhook-event-rules/initialize_defaults/'),
    ('get', '/api/webhook/projects/'),
    ('get', '/api/webhook/reviews/'),
    ('get', '/api/webhook/logs/'),
    ('get', '/api/system/info'),
])
def test_anonymous_requests_get_401_without_secrets(secrets_configured, method, url):
    response = getattr(APIClient(), method)(url, {}, format='json')
    assert response.status_code == 401
    assert b'secret' not in response.content


def test_anonymous_cannot_modify_configuration(secrets_configured):
    response = APIClient().post(BATCH_UPDATE_URL, {'gitlab': {'server_url': 'https://evil.invalid'}}, format='json')
    assert response.status_code == 401
    assert GitLabConfig.objects.get().server_url == 'https://gitlab.invalid'


def test_invalid_token_is_rejected(secrets_configured):
    client = APIClient()
    client.cookies['auth_token'] = 'not-a-real-token'
    assert client.get(SUMMARY_URL).status_code == 401


def test_logged_in_user_can_read_configuration(secrets_configured, logged_in):
    assert logged_in.get(SUMMARY_URL).status_code == 200


def test_logout_revokes_access(secrets_configured, logged_in):
    logged_in.post('/api/auth/logout')
    assert logged_in.get(SUMMARY_URL).status_code == 401


def test_gitlab_webhook_stays_public(db):
    response = APIClient().post('/api/webhook/gitlab/', {'object_kind': 'push', 'project': {'id': 1}}, format='json')
    assert response.status_code == 200


@pytest.mark.parametrize('fetch_site', ['cross-site', 'same-site'])
def test_cross_site_write_is_rejected(secrets_configured, logged_in, fetch_site):
    response = logged_in.post(
        BATCH_UPDATE_URL,
        {'gitlab': {'server_url': 'https://evil.invalid'}},
        format='json',
        HTTP_SEC_FETCH_SITE=fetch_site,
        HTTP_ORIGIN='http://evil.invalid',
    )
    assert response.status_code == 403
    assert GitLabConfig.objects.get().server_url == 'https://gitlab.invalid'


@pytest.mark.parametrize('headers', [
    {'HTTP_SEC_FETCH_SITE': 'same-origin'},
    {'HTTP_SEC_FETCH_SITE': 'same-site', 'HTTP_ORIGIN': 'http://localhost:3000'},
])
def test_trusted_write_is_allowed(secrets_configured, logged_in, settings, headers):
    settings.CORS_ALLOWED_ORIGINS = ['http://localhost:3000']
    response = logged_in.post(BATCH_UPDATE_URL, {}, format='json', **headers)
    assert response.status_code == 200
