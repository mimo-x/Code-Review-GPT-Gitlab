"""审查引擎的契约：平台给引擎什么、引擎交回什么。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, ClassVar

SEVERITIES = ("critical", "major", "minor", "nit")
CATEGORIES = ("defect", "security", "performance", "maintainability", "style")


class EngineError(Exception):
    """引擎无法完成本次审查，消息会写入审查记录。"""


@dataclass(frozen=True)
class Revisions:
    base_sha: str
    start_sha: str
    head_sha: str

    @property
    def unique(self) -> list[str]:
        return list(dict.fromkeys((self.base_sha, self.start_sha, self.head_sha)))


@dataclass(frozen=True)
class MergeRequestInfo:
    project_id: int
    mr_iid: int
    project_name: str
    title: str
    author: str
    description: str
    url: str
    source_branch: str
    target_branch: str
    file_count: int
    changes_count: int

    def as_context(self) -> dict[str, Any]:
        """通知渠道和自定义 Prompt 模板使用的字段。"""
        return {**asdict(self), "web_url": self.url}

    @property
    def project_web_url(self) -> str:
        return self.url.split("/-/merge_requests/")[0] if self.url else ""


@dataclass(frozen=True)
class ReviewRequest:
    request_id: str
    mr: MergeRequestInfo
    changes: list[dict]
    language: str
    revisions: Revisions | None = None
    custom_prompt: str | None = None
    worktree: Path | None = None
    # 不在审查范围内的变更文件：可以读取作为上下文，不能报告问题
    skipped_paths: tuple[str, ...] = ()


@dataclass
class Finding:
    path: str
    title: str
    body: str = ""
    severity: str = "minor"
    category: str = "defect"
    side: str = "new"
    start_line: int | None = None
    end_line: int | None = None
    existing_code: str | None = None
    engine_meta: dict = field(default_factory=dict)
    # 以下字段由平台后处理计算，不采信引擎给的值
    in_diff: bool = False
    fingerprint: str = ""

    @property
    def location(self) -> str:
        return f"{self.path}:{self.end_line}" if self.in_diff else self.path


@dataclass
class ReviewResult:
    provider: str
    model: str
    summary: str = ""
    findings: list[Finding] = field(default_factory=list)
    # False：模型没有按契约输出，summary 中是它的原始 Markdown
    structured: bool = True
    usage: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class ReviewEngine(ABC):
    kind: ClassVar[str]
    needs_worktree: ClassVar[bool] = False

    def __init__(self, llm_config, request_id: str | None = None):
        self.llm_config = llm_config
        self.request_id = request_id

    @abstractmethod
    def review(self, request: ReviewRequest) -> ReviewResult:
        """执行审查；无法完成时抛出 EngineError。"""
