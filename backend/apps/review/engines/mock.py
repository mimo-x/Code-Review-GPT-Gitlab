"""Mock 引擎：不调用模型，用一条示例问题走通完整的展示链路。"""
from __future__ import annotations

from ..diff_index import DiffIndex
from .base import Finding, ReviewEngine, ReviewRequest, ReviewResult

_TEXT = {
    "zh-CN": {
        "summary": "这是 Mock 模式生成的示例结果，没有调用任何模型。",
        "title": "[Mock] 示例问题",
        "body": "这条评论用于验证行内评论的展示效果，不代表代码真的有问题。",
    },
    "en": {
        "summary": "This is a sample result from mock mode. No model was called.",
        "title": "[Mock] Sample finding",
        "body": "This comment demonstrates inline rendering and does not describe a real problem.",
    },
}


class MockEngine(ReviewEngine):
    kind = "mock"
    label = "Mock"
    description = "不调用模型，发一条示例评论，用于检查展示和发布流程。"

    def review(self, request: ReviewRequest) -> ReviewResult:
        text = _TEXT.get(request.language, _TEXT["zh-CN"])
        findings = []
        first_added = DiffIndex(request.changes).first_added_line()
        if first_added:
            path, line = first_added
            findings.append(Finding(
                path=path,
                title=text["title"],
                body=text["body"],
                severity="minor",
                category="maintainability",
                start_line=line,
                end_line=line,
            ))
        return ReviewResult(
            provider="mock",
            model="mock",
            summary=text["summary"],
            findings=findings,
            metadata={"is_mock": True},
        )
