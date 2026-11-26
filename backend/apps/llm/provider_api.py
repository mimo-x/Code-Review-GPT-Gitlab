"""Model discovery and checks for saved endpoints, adapted from Paperpane's provider clients."""
import json
import re
import time
from urllib.parse import quote, urlsplit

import requests


DEFAULT_BASES = {
    "openai": "https://api.openai.com/v1",
    "openai_responses": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}
_MODES = {
    "text": "Reply with exactly OK.",
    "image": "What is the main color of this image? Answer with one word.",
    "structured": "Return an object with ok equal to true.",
}
_RED_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAKElEQVR4nO3NsQ0AAAzCMP5/un0CNkuZ41wybXsHAAAAAAAAAAAAxR4yw/wuPL6QkAAAAABJRU5ErkJggg=="
_TEST_SCHEMA = {
    "type": "object", "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"], "additionalProperties": False,
}
_MAX_RESPONSE_BYTES = 2_000_000


class ProviderAPIError(Exception):
    """A safe diagnostic message for the settings page."""


def base_url(provider, configured):
    value = (configured or DEFAULT_BASES.get(provider) or "").rstrip("/")
    try:
        url = urlsplit(value)
        if url.scheme not in ("http", "https") or not url.hostname or url.username is not None or url.query or url.fragment:
            raise ValueError
        url.port
    except ValueError:
        raise ProviderAPIError("请填写不含凭据或查询参数的 HTTP(S) API 地址。") from None
    path = re.sub(r"/(?:chat/completions|messages|responses|models/[^/]+:(?:streamGenerateContent|generateContent))$", "", url.path)
    return url._replace(path=path).geturl()


def provider_model_id(provider, model):
    prefix = {"openai_responses": "openai", "openai": "openai",
              "anthropic": "anthropic", "deepseek": "deepseek", "gemini": "gemini"}.get(provider)
    if prefix:
        model = model.removeprefix(f"{prefix}/")
    return model.removeprefix("models/") if provider == "gemini" else model


def _headers(provider, key):
    if provider == "anthropic":
        return {"anthropic-version": "2023-06-01", **({"x-api-key": key} if key else {})}
    if provider == "gemini":
        return {"x-goog-api-key": key} if key else {}
    return {"Authorization": f"Bearer {key}"} if key else {}


def _read_json(url, *, headers, payload=None, params=None, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProviderAPIError("模型服务请求超时。")
    try:
        request = requests.get if payload is None else requests.post
        kwargs = {"params": params} if payload is None else {"json": payload}
        with request(url, headers=headers, stream=True, allow_redirects=False,
                     timeout=(min(5, remaining), remaining), **kwargs) as response:
            status = response.status_code
            if not 200 <= status < 300:
                errors = {
                    401: "鉴权失败，请检查 API Key。",
                    403: "没有访问权限，请检查 API Key。",
                    429: "请求过于频繁，请稍后重试。",
                }
                raise ProviderAPIError(errors.get(status, f"接口返回 HTTP {status}。"))
            data = bytearray()
            for chunk in response.iter_content(chunk_size=8192):
                if time.monotonic() >= deadline:
                    raise ProviderAPIError("模型服务请求超时。")
                data.extend(chunk)
                if len(data) > _MAX_RESPONSE_BYTES:
                    raise ProviderAPIError("接口返回的数据过大。")
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ValueError
            return result
    except requests.RequestException:
        raise ProviderAPIError("无法连接模型服务，请检查地址和网络。") from None
    except (ValueError, UnicodeError):
        raise ProviderAPIError("接口返回的不是有效 JSON 对象。") from None


def discover_models(connection):
    provider = connection.provider
    url = base_url(provider, connection.api_base) + "/models"
    deadline = time.monotonic() + min(connection.timeout or 25, 25)
    cursor_key = "pageToken" if provider == "gemini" else "after_id"
    cursor, seen, found = None, set(), {}
    for _ in range(30):
        data = _read_json(url, headers=_headers(provider, connection.api_key),
                          params={cursor_key: cursor} if cursor else None, deadline=deadline)
        rows = data.get("models" if provider == "gemini" else "data")
        if not isinstance(rows, list):
            raise ProviderAPIError("模型列表格式不正确。")
        for row in rows:
            if not isinstance(row, dict):
                continue
            if provider == "gemini":
                methods = row.get("supportedGenerationMethods")
                if isinstance(methods, list) and "generateContent" not in methods:
                    continue
            identifier = row.get("name" if provider == "gemini" else "id")
            if not isinstance(identifier, str):
                continue
            identifier = identifier.strip()
            if provider == "gemini":
                identifier = identifier.removeprefix("models/")
            if not identifier or len(identifier) > 100:
                continue
            label = row.get("display_name") or row.get("displayName") or identifier
            found[identifier] = {"modelId": identifier, "label": label[:100] if isinstance(label, str) else identifier}
            if len(found) > 5000:
                raise ProviderAPIError("端点返回了超过 5000 个模型。请手动填写模型 ID。")
        cursor = data.get("nextPageToken") if provider == "gemini" else (
            data.get("last_id") if data.get("has_more") else None
        )
        if not cursor:
            return list(found.values())
        if not isinstance(cursor, str) or cursor in seen:
            raise ProviderAPIError("模型列表的分页游标无效。")
        seen.add(cursor)
    raise ProviderAPIError("模型列表的分页数量过多。请手动填写模型 ID。")


def _text(parts):
    if not isinstance(parts, list):
        return ""
    return "".join(part["text"] for part in parts
                   if isinstance(part, dict) and isinstance(part.get("text"), str)
                   and not part.get("thought") and part.get("type", "text") in ("text", "output_text"))


def responses_reply(endpoint, key, model, content, timeout, *, structured=False, max_tokens=None):
    payload = {"model": model, "input": [{"role": "user", "content": content}], "store": False}
    if max_tokens is not None:
        payload["max_output_tokens"] = max_tokens
    if structured:
        payload["text"] = {"format": {"type": "json_schema", "name": "connection_test",
                                      "strict": True, "schema": _TEST_SCHEMA}}
    result = _read_json(endpoint + "/responses", headers=_headers("openai_responses", key),
                        payload=payload, deadline=time.monotonic() + timeout)
    output = result.get("output")
    if not isinstance(output, list):
        return ""
    return "".join(_text(row.get("content")) for row in output
                   if isinstance(row, dict) and row.get("type") == "message")


def _test_chat(connection, model, prompt, mode, endpoint, deadline):
    provider = connection.provider
    image = mode == "image"
    structured = mode == "structured"
    if provider == "anthropic":
        path = "/messages"
        parts = [{"type": "text", "text": prompt}]
        if image:
            parts.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _RED_IMAGE}})
        payload = {"model": model, "max_tokens": 2048, "messages": [{"role": "user", "content": parts}]}
        if structured:
            payload["output_config"] = {"format": {"type": "json_schema", "schema": _TEST_SCHEMA}}
    elif provider == "gemini":
        path = f"/models/{quote(model, safe='')}:generateContent"
        parts = [{"text": prompt}]
        if image:
            parts.append({"inlineData": {"mimeType": "image/png", "data": _RED_IMAGE}})
        payload = {"contents": [{"role": "user", "parts": parts}], "generationConfig": {"maxOutputTokens": 2048}}
        if structured:
            payload["generationConfig"].update(responseMimeType="application/json", responseJsonSchema=_TEST_SCHEMA)
    else:
        path = "/chat/completions"
        content = prompt
        if image:
            content = [{"type": "text", "text": prompt},
                       {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_RED_IMAGE}"}}]
        payload = {"model": model, "messages": [{"role": "user", "content": content}]}
        token_parameter = "max_completion_tokens" if endpoint == DEFAULT_BASES["openai"] else "max_tokens"
        payload[token_parameter] = 2048
        if structured:
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "connection_test", "strict": True, "schema": _TEST_SCHEMA}}
    data = _read_json(endpoint + path, headers=_headers(provider, connection.api_key),
                      payload=payload, deadline=deadline)
    try:
        if provider == "anthropic":
            return _text(data.get("content", []))
        if provider == "gemini":
            return _text(data["candidates"][0]["content"]["parts"])
        content = data["choices"][0]["message"]["content"]
        return content if isinstance(content, str) else _text(content or [])
    except (KeyError, IndexError, TypeError):
        return ""


def test_model(config, mode):
    connection = config.connection
    provider = connection.provider
    started = time.monotonic()
    timeout = min(connection.timeout or 50, 50)
    endpoint = base_url(provider, connection.api_base)
    model = provider_model_id(provider, config.model)
    if provider == "openai_responses":
        parts = [{"type": "input_text", "text": _MODES[mode]}]
        if mode == "image":
            parts.append({"type": "input_image", "image_url": f"data:image/png;base64,{_RED_IMAGE}"})
        text = responses_reply(endpoint, connection.api_key, model, parts, timeout,
                               structured=mode == "structured", max_tokens=2048)
    else:
        text = _test_chat(connection, model, _MODES[mode], mode, endpoint, started + timeout)
    if not text.strip():
        raise ProviderAPIError("接口没有返回文字。")
    if mode == "image" and not re.search(r"\bred\b|红", text, re.IGNORECASE):
        raise ProviderAPIError("模型未正确识别红色测试图。")
    if mode == "structured":
        try:
            value = json.loads(text)
        except ValueError:
            value = None
        if not isinstance(value, dict) or value.get("ok") is not True:
            raise ProviderAPIError("返回数据未通过结构化校验。")
    return {"text": text.strip()[:1000], "elapsed_ms": round((time.monotonic() - started) * 1000)}
