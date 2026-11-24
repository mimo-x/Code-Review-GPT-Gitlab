"""审查引擎注册表。"""
from __future__ import annotations

from .base import EngineError, ReviewEngine
from .claude_code import ClaudeCodeEngine
from .diff_llm import DiffLLMEngine
from .mock import MockEngine

ENGINES: dict[str, type[ReviewEngine]] = {
    engine.kind: engine for engine in (MockEngine, DiffLLMEngine, ClaudeCodeEngine)
}

# 过渡映射：引擎配置落库之前，审查方式仍由 LLMConfig.provider 决定
_KIND_BY_PROVIDER = {"mock": MockEngine.kind, "claude": ClaudeCodeEngine.kind}


def engine_for(llm_config, request_id: str | None = None) -> ReviewEngine:
    kind = _KIND_BY_PROVIDER.get(llm_config.provider, DiffLLMEngine.kind)
    return ENGINES[kind](llm_config, request_id=request_id)


__all__ = ["ENGINES", "EngineError", "ReviewEngine", "engine_for"]
