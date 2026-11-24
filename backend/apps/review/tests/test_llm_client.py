"""模型客户端：用真实 unionllm/litellm 请求本地 OpenAI 兼容服务。"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from apps.llm.services import LLMService, _routed_model


@pytest.fixture
def gateway(monkeypatch):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append({"path": self.path, "auth": self.headers.get("Authorization"), "model": body["model"]})
            data = json.dumps({
                "id": "x", "object": "chat.completion", "created": 1, "model": body["model"],
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    yield SimpleNamespace(base=f"http://127.0.0.1:{server.server_port}/v1", calls=calls)
    server.shutdown()
    server.server_close()


def config(provider, model, base):
    return SimpleNamespace(provider=provider, model=model, api_key="test-key", api_base=base, timeout=10)


@pytest.mark.parametrize("provider,model,sent", [
    ("deepseek", "deepseek-v4.1-flash", "deepseek-v4.1-flash"),
    ("openai", "deepseek-v4.1-flash", "deepseek-v4.1-flash"),
    ("openai", "openai/deepseek-v4.1-flash", "deepseek-v4.1-flash"),
    ("openai", "deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-V3"),
    ("openai", "deepseek/deepseek-r1", "deepseek/deepseek-r1"),
])
def test_requests_reach_the_configured_base_url(gateway, provider, model, sent):
    completion = LLMService(config(provider, model, gateway.base)).complete("hello")
    assert completion.text == "ok"
    assert gateway.calls[0]["path"].endswith("/chat/completions")
    assert gateway.calls[0]["path"].startswith("/v1/")
    assert gateway.calls[0]["auth"] == "Bearer test-key"
    assert gateway.calls[0]["model"] == sent


def test_credentials_are_not_written_to_the_process_environment(gateway, monkeypatch):
    for name in ("DEEPSEEK_API_KEY", "DEEPSEEK_API_BASE", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    LLMService(config("deepseek", "deepseek-chat", gateway.base)).complete("hello")
    assert "DEEPSEEK_API_KEY" not in os.environ
    assert "DEEPSEEK_API_BASE" not in os.environ
    assert "LLM_MODEL" not in os.environ


@pytest.mark.parametrize("provider,model,base,routed", [
    ("deepseek", "deepseek-chat", None, "deepseek/deepseek-chat"),
    ("openai", "gpt-4o", None, "openai/gpt-4o"),
    ("openai", "gemini/gemini-2.0-flash", None, "gemini/gemini-2.0-flash"),
    ("gemini", "gemini-2.0-flash", None, "gemini/gemini-2.0-flash"),
    ("litellm", "groq/llama", None, "groq/llama"),
])
def test_model_routing(provider, model, base, routed):
    assert _routed_model(provider, model, base) == routed
