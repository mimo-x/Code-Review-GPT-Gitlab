"""引擎输出契约 review-result/v1：告诉模型怎么写，并把它写的内容解析回结构。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .base import CATEGORIES, SEVERITIES, Finding

LANGUAGE_NAMES = {"zh-CN": "简体中文", "en": "English"}

SEVERITY_ALIASES = {
    "blocker": "critical", "严重": "critical", "致命": "critical",
    "high": "major", "error": "major", "重要": "major", "高": "major", "高危": "major",
    "medium": "minor", "warning": "minor", "一般": "minor", "中": "minor", "中危": "minor",
    "low": "nit", "info": "nit", "轻微": "nit", "低": "nit", "低危": "nit",
}

_INSTRUCTIONS = """## 输出格式（必须遵守）
只输出一个 JSON 对象，放在 ```json 代码块中，代码块外不要写任何文字：
{{
  "summary": "一到两句话的结论：这个 MR 最需要关注什么",
  "findings": [
    {{
      "path": "改动文件的路径",
      "side": "new；问题在被删除的代码上时写 old",
      "start_line": 起始行号,
      "end_line": 结束行号,
      "existing_code": "从 diff 原样复制的 1-10 行连续代码，不带 +/- 前缀",
      "severity": "critical | major | minor | nit",
      "category": "defect | security | performance | maintainability | style",
      "title": "一句话说明问题",
      "body": "一到三句话：会造成什么后果，以及怎么改"
    }}
  ]
}}

严重程度：critical＝安全漏洞、数据丢失、崩溃或核心功能损坏；major＝部分场景行为错误或明显风险；minor＝性能、可维护性或边界问题；nit＝命名、措辞等小问题。

要求：
- 只报告有代码依据的具体问题，同一问题只报告一次；没有问题时 findings 写空数组。
- 不要写优点、评分，也不要写"建议增加注释、补充单元测试"这类没有定位的泛泛建议。
- body 不要复述代码，也不要写分析过程。
- summary、title、body 使用{language}；代码、路径和标识符保持原文。"""


def output_instructions(language: str) -> str:
    return _INSTRUCTIONS.format(language=LANGUAGE_NAMES.get(language, language))


@dataclass
class ParsedOutput:
    structured: bool
    summary: str = ""
    findings: list[Finding] = field(default_factory=list)


def parse_output(text: str) -> ParsedOutput:
    """解析模型输出；不符合契约时把原文作为总结保留，不丢内容。"""
    data = _find_result_object(text or "")
    if data is None:
        return ParsedOutput(structured=False, summary=(text or "").strip())
    findings = [f for f in map(_to_finding, data["findings"]) if f is not None]
    return ParsedOutput(
        structured=True,
        summary=_text(data.get("summary")),
        findings=findings,
    )


def _find_result_object(text: str) -> dict | None:
    decoder = json.JSONDecoder()
    position = text.find("{")
    while position != -1:
        try:
            value, end = decoder.raw_decode(text, position)
        except json.JSONDecodeError:
            position = text.find("{", position + 1)
            continue
        if isinstance(value, dict) and isinstance(value.get("findings"), list):
            return value
        position = text.find("{", end)
    return None


def _to_finding(raw) -> Finding | None:
    if not isinstance(raw, dict):
        return None
    path = _text(raw.get("path")).removeprefix("./")
    body = _text(raw.get("body") or raw.get("description"))
    title = _text(raw.get("title")) or (body.splitlines()[0] if body else "")
    if not path or not title:
        return None
    start = _line(raw.get("start_line", raw.get("line")))
    end = _line(raw.get("end_line")) or start
    return Finding(
        path=path,
        title=title,
        body=body,
        severity=_severity(raw.get("severity")),
        category=_category(raw.get("category")),
        side="old" if _text(raw.get("side")).lower() == "old" else "new",
        start_line=start or end,
        end_line=end,
        existing_code=_code(raw.get("existing_code")),
    )


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _code(value) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _line(value) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _severity(value) -> str:
    key = _text(value).lower()
    if key in SEVERITIES:
        return key
    return SEVERITY_ALIASES.get(key, "minor")


def _category(value) -> str:
    key = _text(value).lower()
    return key if key in CATEGORIES else "defect"
