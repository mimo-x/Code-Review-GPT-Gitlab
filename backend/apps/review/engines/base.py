"""审查引擎的契约：平台给引擎什么、引擎交回什么。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from ..scope import ReviewScope

SEVERITIES = ("critical", "major", "minor", "nit")
CATEGORIES = ("defect", "security", "performance", "maintainability", "style")


class EngineError(Exception):
    """引擎无法完成本次审查，消息会写入审查记录。"""


@dataclass(frozen=True)
class Option:
    """引擎可配置的一项。前端按这些声明显示配置表单，新增引擎不需要改前端。"""

    key: str
    label: str
    kind: str  # "select" 或 "number"
    default: Any
    choices: tuple[tuple[str, str], ...] = ()  # select：(值, 显示名)
    minimum: int | None = None
    maximum: int | None = None
    # 放在默认收起的“高级设置”里
    advanced: bool = False
    help: str = ""

    def clean(self, value: Any) -> Any:
        if value is None:
            return self.default
        if self.kind == "select":
            if not isinstance(value, str) or value not in {choice for choice, _ in self.choices}:
                raise ValueError(f"{self.label}：不支持的取值 {value!r}")
            return value
        if isinstance(value, bool):
            raise ValueError(f"{self.label}：需要整数")
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{self.label}：需要整数") from None
        if number != value and not isinstance(value, str):
            raise ValueError(f"{self.label}：需要整数")
        if self.minimum is not None and number < self.minimum:
            raise ValueError(f"{self.label}：不能小于 {self.minimum}")
        if self.maximum is not None and number > self.maximum:
            raise ValueError(f"{self.label}：不能大于 {self.maximum}")
        return number

    def describe(self) -> dict[str, Any]:
        return {**asdict(self), "choices": [list(choice) for choice in self.choices]}


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
    scope: ReviewScope = field(default_factory=ReviewScope)


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
    failed_investigations: int = 0
    reviewed_paths: tuple[str, ...] | None = None
    excluded_paths: tuple[str, ...] = ()


class ReviewEngine(ABC):
    kind: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str] = ""
    needs_model: ClassVar[bool] = True
    needs_worktree: ClassVar[bool] = False
    reviews_local_diff: ClassVar[bool] = False
    options: ClassVar[tuple[Option, ...]] = ()

    def __init__(self, llm_config, request_id: str | None = None, options: dict | None = None):
        self.llm_config = llm_config
        self.request_id = request_id
        self.settings = self.clean_options(options or {})

    @classmethod
    def clean_options(cls, values: dict) -> dict[str, Any]:
        """补上默认值并校验；未声明的键会被丢弃。取值不合法时抛出 ValueError。"""
        return {option.key: option.clean(values.get(option.key)) for option in cls.options}

    @classmethod
    def describe(cls) -> dict[str, Any]:
        return {
            "kind": cls.kind,
            "label": cls.label,
            "description": cls.description,
            "options": [option.describe() for option in cls.options],
        }

    @abstractmethod
    def review(self, request: ReviewRequest) -> ReviewResult:
        """执行审查；无法完成时抛出 EngineError。"""
