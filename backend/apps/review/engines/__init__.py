"""审查引擎注册表。"""
from __future__ import annotations

from .base import EngineError, ReviewEngine
from .claude_code import ClaudeCodeEngine
from .diff_llm import DiffLLMEngine
from .mock import MockEngine
from .review_agent import ReviewAgentEngine

ENGINES: dict[str, type[ReviewEngine]] = {
    engine.kind: engine
    for engine in (DiffLLMEngine, ReviewAgentEngine, ClaudeCodeEngine, MockEngine)
}

# 没有保存过引擎配置时，审查方式仍由 LLMConfig.provider 决定，兼容旧部署
_KIND_BY_PROVIDER = {"mock": MockEngine.kind, "claude": ClaudeCodeEngine.kind}


def current_engine(llm_config) -> tuple[str, dict]:
    """当前使用的引擎和它的选项（未校验）。"""
    from ..models import ReviewEngineConfig

    config = ReviewEngineConfig.current()
    if config is not None and config.engine in ENGINES:
        return config.engine, config.options or {}
    provider = llm_config.provider if llm_config is not None else None
    return _KIND_BY_PROVIDER.get(provider, DiffLLMEngine.kind), {}


def engine_for(llm_config, request_id: str | None = None) -> ReviewEngine:
    kind, options = current_engine(llm_config)
    try:
        return ENGINES[kind](llm_config, request_id=request_id, options=options)
    except ValueError as exc:
        raise EngineError(f"审查引擎配置无效: {exc}") from exc


__all__ = ["ENGINES", "EngineError", "ReviewEngine", "current_engine", "engine_for"]
