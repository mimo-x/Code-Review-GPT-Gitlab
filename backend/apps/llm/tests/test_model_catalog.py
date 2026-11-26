import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
from rest_framework.test import APIClient

from apps.llm.models import LLMConfig
from apps.llm.services import LLMService


PROVIDERS = "/api/llm-providers/"
MODELS = "/api/llm-configs/"
FRONTEND = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setenv("DEFAULT_USERNAME", "test-admin")
    monkeypatch.setenv("DEFAULT_PASSWORD", "test-password")
    client = APIClient()
    response = client.post("/api/auth/login", {
        "username": "test-admin", "password": "test-password",
    }, format="json")
    assert response.status_code == 200
    yield client
    client.post("/api/auth/logout")


def provider(client, name, route, base):
    response = client.post(PROVIDERS, {
        "name": name, "provider": route, "api_base": base, "api_key": f"{name}-test-key",
    }, format="json", **FRONTEND)
    assert response.status_code == 201, response.data
    assert response.data["has_api_key"] and "api_key" not in response.data
    return response.data


def model(client, service, name):
    response = client.post(MODELS, {
        "model_provider": service["id"], "model": name, "is_active": False,
    }, format="json", **FRONTEND)
    assert response.status_code == 201, response.data
    return response.data["id"]


def test_save_providers_and_select_a_model_from_each(client):
    first = provider(client, "First", "openai", "http://127.0.0.1:3425/v1")
    second = provider(client, "Second", "deepseek", "https://deepseek.example/v1")
    first_id = model(client, first, "auto/review")
    model(client, first, "auto/fast")
    second_id = model(client, second, "deepseek-chat")

    for model_id, expected_provider, expected_key, expected_url in (
        (first_id, "openai", "First-test-key", "http://127.0.0.1:3425/v1"),
        (second_id, "deepseek", "Second-test-key", "https://deepseek.example/v1"),
    ):
        assert client.post(f"{MODELS}{model_id}/activate/", {}, format="json", **FRONTEND).status_code == 200
        active = LLMConfig.objects.get(is_active=True)
        assert active.pk == model_id
        connection = LLMService(active)
        assert (connection.provider, connection.api_key, connection.api_base) == (
            expected_provider, expected_key, expected_url,
        )
    listing = client.get(PROVIDERS)
    assert [(item["name"], len(item["models"])) for item in listing.data] == [("First", 2), ("Second", 1)]
    assert "Second-test-key" not in listing.content.decode()


def test_changing_a_keyed_endpoint_requires_a_key_decision(client):
    saved = provider(client, "Gateway", "openai", "https://initial.example/v1")
    url = f"{PROVIDERS}{saved['id']}/"
    response = client.patch(url, {"api_base": "https://changed.example/v1"}, format="json", **FRONTEND)
    assert response.status_code == 400
    response = client.patch(
        url, {"api_base": "https://changed.example/v1", "api_key": ""}, format="json", **FRONTEND,
    )
    assert response.status_code == 200
    assert response.data["api_base"] == "https://changed.example/v1"
    assert not response.data["has_api_key"]


def test_catalog_routes_use_the_dashboard_login(client):
    assert APIClient().get(PROVIDERS).status_code == 401
    assert APIClient().get(MODELS).status_code == 401
    assert client.post(PROVIDERS, {"name": "No header"}, format="json").status_code == 403


def test_catalog_does_not_accept_duplicate_model_ids(client):
    saved = provider(client, "Gateway", "openai", "https://gateway.example/v1")
    model(client, saved, "auto/review")
    response = client.post(MODELS, {
        "model_provider": saved["id"], "model": "auto/review", "is_active": False,
    }, format="json", **FRONTEND)
    assert response.status_code == 400
    assert LLMConfig.objects.filter(model_provider_id=saved["id"]).count() == 1


@pytest.fixture
def endpoint(monkeypatch):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, status, data, headers=None):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            target = urlsplit(self.path)
            requests.append((self.command, self.path, dict(self.headers), None))
            if target.path.startswith("/redirect"):
                self.respond(302, {}, {"Location": "/unexpected/models"})
            elif target.path.startswith("/gemini"):
                if target.query:
                    self.respond(200, {"models": [{"name": "models/model-2"}]})
                else:
                    self.respond(200, {
                        "models": [
                            {"name": "models/model-1", "displayName": "First"},
                            {"name": "models/embedding", "supportedGenerationMethods": ["embedContent"]},
                        ],
                        "nextPageToken": "next",
                    })
            elif target.path.endswith("/models"):
                self.respond(200, {"data": [{"id": "auto/example", "display_name": "Example"}]})
            else:
                self.respond(404, {})

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.command, self.path, dict(self.headers), data))
            if self.path.endswith("/responses"):
                text = '{"ok":true}' if "text" in data else "OK"
                self.respond(200, {"output": [{"type":"message","content":[{"type":"output_text","text":text}]}]})
            elif self.path.endswith("/chat/completions"):
                self.respond(200, {"choices":[{"message":{"content":"OK"}}]})
            elif self.path.endswith("/messages"):
                self.respond(200, {"content":[{"type":"text","text":"red"}]})
            else:
                self.respond(404, {})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    yield f"http://127.0.0.1:{server.server_port}", requests
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_discovers_the_saved_openai_endpoint_without_forwarding_the_key(client, endpoint):
    base, sent = endpoint
    saved = provider(client, "Gateway", "openai", base + "/v1")
    response = client.post(f"{PROVIDERS}{saved['id']}/endpoint-models/", {}, format="json", **FRONTEND)
    assert response.status_code == 200
    assert response.data == {"models": [{"modelId":"auto/example","label":"Example"}]}
    assert sent[0][1] == "/v1/models"
    assert sent[0][2]["Authorization"] == "Bearer Gateway-test-key"

    redirect = provider(client, "Redirect", "openai", base + "/redirect")
    response = client.post(f"{PROVIDERS}{redirect['id']}/endpoint-models/", {}, format="json", **FRONTEND)
    assert response.status_code == 502
    assert [entry[1] for entry in sent] == ["/v1/models", "/redirect/models"]


def test_discovers_paginated_gemini_models(client, endpoint):
    base, sent = endpoint
    saved = provider(client, "Gemini", "gemini", base + "/gemini/v1beta")
    data = client.post(f"{PROVIDERS}{saved['id']}/endpoint-models/", {}, format="json", **FRONTEND).data
    assert [item["modelId"] for item in data["models"]] == ["model-1", "model-2"]
    assert all(entry[2]["x-goog-api-key"] == "Gemini-test-key" for entry in sent)
    assert sent[1][1] == "/gemini/v1beta/models?pageToken=next"


@pytest.mark.parametrize("route,mode,id,suffix,snippet", [
    ("openai", "text", "auto/example", "/chat/completions", "OK"),
    ("openai_responses", "structured", "openai/example", "/responses", '{"ok":true}'),
    ("anthropic", "image", "anthropic/example", "/messages", "red"),
])
def test_model_checks_use_the_selected_protocol(client, endpoint, route, mode, id, suffix, snippet):
    base, sent = endpoint
    saved = provider(client, "Test", route, base + "/v1")
    model_id = model(client, saved, id)
    response = client.post(f"{MODELS}{model_id}/test/", {"mode": mode}, format="json", **FRONTEND)
    assert response.status_code == 200, response.data
    assert response.data["text"] == snippet and response.data["elapsed_ms"] >= 0
    assert len(sent) == 1 and sent[0][1] == "/v1" + suffix
    assert sent[0][3]["model"] == id.removeprefix("openai/").removeprefix("anthropic/")
    if route == "openai_responses":
        assert sent[0][3]["store"] is False
        assert sent[0][3]["text"]["format"]["strict"] is True
        active = LLMConfig.objects.get(pk=model_id)
        assert LLMService(active).complete("Reply OK").text == "OK"


def test_bulk_add_and_duplicate_provider_are_safe_for_active_models(client):
    saved = provider(client, "Gateway", "openai", "https://gateway.example/v1")
    url = f"{PROVIDERS}{saved['id']}/"
    payload = [{"model":"auto/example","label":"Example"}, {"model":"auto/fast"}]
    for _ in range(2):
        response = client.post(url + "models/", payload, format="json", **FRONTEND)
        assert response.status_code == 200
        assert len(response.data) == 2
    model_id = response.data[0]["id"]
    assert client.post(f"{MODELS}{model_id}/activate/", {}, format="json", **FRONTEND).status_code == 200

    response = client.post(url + "duplicate/", {}, format="json", **FRONTEND)
    assert response.status_code == 201
    assert len(response.data["models"]) == 2
    assert not response.data["has_api_key"]
    assert not any(item["is_active"] for item in response.data["models"])
    assert client.delete(url, **FRONTEND).status_code == 409
    assert client.delete(f"{MODELS}{model_id}/", **FRONTEND).status_code == 409
