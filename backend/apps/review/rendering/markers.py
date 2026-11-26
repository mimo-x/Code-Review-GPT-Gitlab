"""评论里的隐藏标记：不新增数据表，靠它识别机器人自己发过的内容。"""
from __future__ import annotations

import base64
import json
import re

from ..engines.base import Finding

# 总结标记记录这一轮的全部问题，只出现在总结里的问题下次也能认出来
_SUMMARY = re.compile(
    r"\A<!-- code-review-gpt:summary:v[12] review=(\d+)(?: ([A-Za-z0-9_=-]+))? -->"
)
# v1 一条评论一个问题；v2 一条评论可以包含相邻的几个问题
_FINDINGS = re.compile(r"\A<!-- code-review-gpt:(finding:v1|findings:v2) ([A-Za-z0-9_=-]+) -->")


def summary_marker(
    review_id: int, findings: list[Finding], threads: dict[str, str] | None = None,
    *, retained: tuple[dict, ...] = (),
) -> str:
    """threads：指纹变了但沿用旧讨论的问题，记下讨论标记里的旧指纹，下次才能接上。"""
    return f"<!-- code-review-gpt:summary:v2 review={review_id} {_encode(findings, threads, retained)} -->"


def parse_summary_marker(body: str) -> tuple[int, list[dict]] | None:
    match = _SUMMARY.match(body or "")
    if not match:
        return None
    return int(match.group(1)), _decode(match.group(2)) if match.group(2) else []


def findings_marker(findings: list[Finding]) -> str:
    return f"<!-- code-review-gpt:findings:v2 {_encode(findings)} -->"


def parse_findings_marker(body: str) -> list[dict]:
    match = _FINDINGS.match(body or "")
    if not match:
        return []
    return _decode(match.group(2), single=match.group(1) == "finding:v1")


def _encode(
    findings: list[Finding], threads: dict[str, str] | None = None, retained: tuple[dict, ...] = (),
) -> str:
    threads = threads or {}
    items = list(retained)
    for finding in findings:
        item = {
            "fp": finding.fingerprint,
            "title": finding.title,
            "severity": finding.severity,
            "location": finding.location,
        }
        if finding.fingerprint in threads:
            item["thread"] = threads[finding.fingerprint]
        items.append(item)
    payload = json.dumps(items, ensure_ascii=False)
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode(encoded: str, single: bool = False) -> list[dict]:
    try:
        data = json.loads(base64.urlsafe_b64decode(encoded))
    except ValueError:
        return []
    items = [data] if single else data
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict) and item.get("fp")]
