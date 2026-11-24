"""把 diff 直接发给模型的审查方式。"""
from __future__ import annotations

from apps.llm.services import LLMError, LLMService

from .base import EngineError, ReviewEngine, ReviewRequest, ReviewResult
from .output import parse_output
from .prompting import build_review_prompt


class DiffLLMEngine(ReviewEngine):
    kind = "diff_llm"

    def review(self, request: ReviewRequest) -> ReviewResult:
        client = LLMService(self.llm_config, request_id=self.request_id)
        try:
            completion = client.complete(build_review_prompt(request))
        except LLMError as exc:
            raise EngineError(f"代码审查失败: {exc}") from exc
        parsed = parse_output(completion.text)
        return ReviewResult(
            provider=self.llm_config.provider,
            model=self.llm_config.model,
            summary=parsed.summary,
            findings=parsed.findings,
            structured=parsed.structured,
            metadata={"client": completion.client},
        )
