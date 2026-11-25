"""The model boundary. Everything the loop sends and receives crosses here as plain
OpenAI-format chat data, so the same trajectories serve inference, replay and training.

Transport failures (rate limits, timeouts) are retried here; anything the model itself
produced, valid or not, is returned unchanged for the environment to judge.
"""

from __future__ import annotations

import json
import random
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from review_core.common import stable_id


class ModelRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    messages: tuple[dict, ...]
    tools: tuple[dict, ...] = ()
    max_output_tokens: int | None = None
    temperature: float | None = None

    @property
    def hash(self) -> str:
        return request_hash(self.messages, self.tools)


class Usage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
        )


class ModelResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    # An assistant message: {"role": "assistant", "content": str|None, "tool_calls": [...]}
    message: dict
    usage: Usage = Field(default_factory=Usage)
    finish_reason: str | None = None
    model: str | None = None
    latency_s: float = 0.0


class PolicyError(Exception):
    """The model could not be reached after retries; the episode ends with an error."""


class Policy(Protocol):
    name: str

    def complete(self, request: ModelRequest) -> ModelResponse: ...

    def describe(self) -> dict: ...


def request_hash(messages: Sequence[dict], tools: Sequence[dict]) -> str:
    return stable_id({"messages": list(messages), "tools": list(tools)})


def normalize_message(message: Any) -> dict:
    """Provider message object -> plain assistant dict with string tool arguments."""
    data = message if isinstance(message, dict) else message.model_dump()
    out: dict = {"role": "assistant", "content": data.get("content") or None}
    # Kept in the trajectory for training; the loop does not send it back to the model.
    reasoning = data.get("reasoning_content") or data.get("reasoning")
    if reasoning is not None and not isinstance(reasoning, str):
        reasoning = None  # structured provider objects are not chat text
    if reasoning:
        out["reasoning_content"] = reasoning
    calls = []
    for call in data.get("tool_calls") or []:
        function = call.get("function") or {}
        arguments = function.get("arguments")
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments or {}, ensure_ascii=False)
        calls.append(
            {
                "id": call.get("id") or f"call_{len(calls)}",
                "type": "function",
                "function": {"name": function.get("name") or "", "arguments": arguments},
            }
        )
    if calls:
        out["tool_calls"] = calls
    return out


class GatedPolicy:
    """At most `limit` requests of the wrapped policy in flight, across every thread that
    shares this object: every episode and post-filter call of every case in the process.
    The model server's capacity bounds the parallelism, not the shape of the work. A request
    holds its slot through the wrapped policy's retries, so backing off also sheds load."""

    def __init__(self, policy: Policy, limit: int):
        if limit < 1:
            raise ValueError(f"limit must be at least 1, not {limit}")
        self.policy = policy
        self.name = policy.name
        self.limit = limit
        self._slots = threading.BoundedSemaphore(limit)

    def describe(self) -> dict:
        return self.policy.describe()  # scheduling is not part of what the model is

    def complete(self, request: ModelRequest) -> ModelResponse:
        with self._slots:
            return self.policy.complete(request)


class LiteLLMPolicy:
    """Any LiteLLM-supported endpoint; OpenAI-compatible gateways use model "openai/<name>"."""

    RETRYABLE = (
        "RateLimitError",
        "APIConnectionError",
        "Timeout",
        "ServiceUnavailableError",
        "InternalServerError",
        "APIError",
    )

    def __init__(
        self,
        model: str,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        timeout: float = 300,
        retries: int = 6,
        extra: dict | None = None,
    ):
        self.model = model
        self.name = model
        self.api_base = api_base
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self.extra = dict(extra or {})

    def describe(self) -> dict:
        # Never include credentials in trajectories.
        return {"kind": "litellm", "model": self.model, "api_base": self.api_base, **self.extra}

    def complete(self, request: ModelRequest) -> ModelResponse:
        import litellm

        options: dict = {
            "model": self.model,
            "messages": list(request.messages),
            "timeout": self.timeout,
            "drop_params": True,
            **self.extra,
        }
        if request.tools:
            options["tools"] = list(request.tools)
            options["tool_choice"] = "auto"
        if request.max_output_tokens:
            options["max_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if self.api_base:
            options["api_base"] = self.api_base
        if self.api_key:
            options["api_key"] = self.api_key
        delay = 2.0
        for attempt in range(self.retries + 1):
            started = time.monotonic()
            try:
                response = litellm.completion(**options)
            except Exception as exc:  # classify by name: LiteLLM maps providers onto these
                retryable = type(exc).__name__ in self.RETRYABLE
                if not retryable or attempt == self.retries:
                    raise PolicyError(f"{type(exc).__name__}: {str(exc)[:300]}") from None
                time.sleep(delay + random.random())
                delay = min(delay * 2, 60)
                continue
            choice = response.choices[0]
            usage = getattr(response, "usage", None)
            details = getattr(usage, "prompt_tokens_details", None) if usage else None
            return ModelResponse(
                message=normalize_message(choice.message),
                usage=Usage(
                    input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    cached_input_tokens=getattr(details, "cached_tokens", 0) or 0,
                ),
                finish_reason=choice.finish_reason,
                model=getattr(response, "model", None),
                latency_s=round(time.monotonic() - started, 3),
            )
        raise PolicyError("unreachable")


class ScriptedPolicy:
    """Deterministic test double: a function of the request, or a fixed list of messages."""

    def __init__(
        self,
        script: Callable[[ModelRequest], dict] | Sequence[dict],
        name: str = "scripted",
        usage: Callable[[ModelRequest, dict], Usage] | None = None,
    ):
        self.script = script
        self.name = name
        self.calls = 0
        self.usage = usage

    def describe(self) -> dict:
        return {"kind": "scripted", "model": self.name}

    def complete(self, request: ModelRequest) -> ModelResponse:
        if callable(self.script):
            message = self.script(request)
        else:
            if self.calls >= len(self.script):
                raise PolicyError("script exhausted")
            message = self.script[self.calls]
        self.calls += 1
        message = normalize_message(message)
        usage = self.usage(request, message) if self.usage else Usage()
        return ModelResponse(message=message, usage=usage, model=self.name)


class ReplayPolicy:
    """Re-serve a recorded episode's responses; fails loudly if the requests diverge."""

    def __init__(self, episode):
        self.episode = episode
        self.name = f"replay:{episode.policy.get('model')}"
        self.calls = 0

    def describe(self) -> dict:
        return {**self.episode.policy, "replayed_from": self.episode.id}

    def complete(self, request: ModelRequest) -> ModelResponse:
        if self.calls >= len(self.episode.steps):
            raise PolicyError("replay exhausted: the episode asked for more steps")
        step = self.episode.steps[self.calls]
        if step.request_hash != request.hash:
            raise PolicyError(f"replay diverged at step {self.calls}")
        self.calls += 1
        return ModelResponse(
            message=step.response,
            usage=step.usage,
            finish_reason=step.finish_reason,
            model=step.model,
        )


def to_responses(messages: Sequence[dict], tools: Sequence[dict]) -> tuple[str | None, list, list]:
    """Chat-format conversation -> (instructions, input items, tools) for the Responses API.

    Trajectories stay in chat format; this is only the wire format of one provider.
    """
    instructions = []
    items: list[dict] = []
    for message in messages:
        role = message["role"]
        if role == "system":
            instructions.append(message["content"])
        elif role == "user":
            items.append({"role": "user", "content": message["content"]})
        elif role == "assistant":
            if message.get("content"):
                items.append({"role": "assistant", "content": message["content"]})
            for call in message.get("tool_calls") or []:
                items.append(
                    {
                        "type": "function_call",
                        "call_id": call["id"],
                        "name": call["function"]["name"],
                        "arguments": call["function"]["arguments"],
                    }
                )
        elif role == "tool":
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": message["tool_call_id"],
                    "output": message["content"],
                }
            )
    converted = [
        {
            "type": "function",
            "name": tool["function"]["name"],
            "description": tool["function"].get("description", ""),
            "parameters": tool["function"]["parameters"],
        }
        for tool in tools
    ]
    return "\n\n".join(instructions) or None, items, converted


REASONING_DELTAS = frozenset(
    {"response.reasoning_text.delta", "response.reasoning_summary_text.delta"}
)


class ResponsesPolicy:
    """OpenAI Responses API, streamed (some gateways only serve streaming requests).

    Stateless (store=false): every call sends the full context, like chat completions,
    so requests and trajectories mean the same thing for both API families.
    """

    def __init__(
        self,
        model: str,
        *,
        api_base: str,
        api_key: str,
        timeout: float = 600,
        retries: int = 8,
        extra: dict | None = None,
    ):
        from openai import OpenAI

        self.model = model
        self.name = model
        self.api_base = api_base
        self.timeout = timeout
        self.retries = retries
        self.extra = dict(extra or {})
        self.client = OpenAI(base_url=api_base, api_key=api_key, timeout=timeout, max_retries=0)

    def describe(self) -> dict:
        return {"kind": "responses", "model": self.model, "api_base": self.api_base, **self.extra}

    def complete(self, request: ModelRequest) -> ModelResponse:
        import openai

        instructions, items, tools = to_responses(request.messages, request.tools)
        options: dict = {
            "model": self.model,
            "input": items,
            "stream": True,
            "store": False,
            **self.extra,
        }
        if instructions:
            options["instructions"] = instructions
        if tools:
            options["tools"] = tools
        if request.max_output_tokens:
            options["max_output_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            options["temperature"] = request.temperature
        delay = 3.0
        for attempt in range(self.retries + 1):
            started = time.monotonic()
            try:
                final, streamed = None, []
                for event in self.client.responses.create(**options):
                    if event.type in REASONING_DELTAS:
                        streamed.append(getattr(event, "delta", "") or "")
                    elif event.type in {"response.completed", "response.incomplete"}:
                        final = event.response
                    elif event.type in {"response.failed", "error"}:
                        detail = getattr(event, "response", None) or event
                        raise openai.APIError(
                            str(getattr(detail, "error", detail))[:300], None, body=None
                        )
                if final is None:
                    raise openai.APIConnectionError(request=None)
                return self._response(
                    final, round(time.monotonic() - started, 3), "".join(streamed)
                )
            except (
                openai.APIConnectionError,
                openai.APITimeoutError,
                openai.RateLimitError,
                openai.InternalServerError,
                openai.APIError,
            ) as exc:
                status = getattr(exc, "status_code", None)
                if (
                    status is not None and status < 500 and status != 429
                ) or attempt == self.retries:
                    raise PolicyError(f"{type(exc).__name__}: {str(exc)[:300]}") from None
                time.sleep(delay + random.random() * 2)
                delay = min(delay * 2, 60)
        raise PolicyError("unreachable")

    def _response(self, final, latency: float, streamed: str = "") -> ModelResponse:
        content, calls, reasoning = [], [], []
        for item in final.output or []:
            if item.type == "reasoning":
                # Full reasoning text when the provider returns it, else its summary.
                parts = getattr(item, "content", None) or getattr(item, "summary", None) or []
                reasoning += [getattr(part, "text", "") or "" for part in parts]
            elif item.type == "message":
                for part in item.content or []:
                    if getattr(part, "type", "") == "output_text":
                        content.append(part.text)
            elif item.type == "function_call":
                calls.append(
                    {
                        "id": item.call_id,
                        "type": "function",
                        "function": {"name": item.name, "arguments": item.arguments or "{}"},
                    }
                )
        message: dict = {"role": "assistant", "content": "".join(content) or None}
        thought = "\n".join(part for part in reasoning if part) or streamed
        if thought:
            message["reasoning_content"] = thought  # recorded, never sent back (PRIVATE_KEYS)
        if calls:
            message["tool_calls"] = calls
        usage = final.usage
        details = getattr(usage, "input_tokens_details", None) if usage else None
        return ModelResponse(
            message=message,
            usage=Usage(
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cached_input_tokens=getattr(details, "cached_tokens", 0) or 0,
            ),
            finish_reason="length" if final.status == "incomplete" else "stop",
            model=getattr(final, "model", None),
            latency_s=latency,
        )
