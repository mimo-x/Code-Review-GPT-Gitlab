"""Lenient reading of tool arguments written by small models.

Every repair is deterministic and recorded (the observation lists what was changed), so
training data can keep, drop or relabel repaired calls. Repairs never invent content:
they undo encoding slips (a list sent as a JSON string, bad escapes), map near-miss enum
values, and fill fields that follow from other fields.
"""

from __future__ import annotations

import json
import re

ESCAPE = re.compile(r'\\(["\\/bfnrtu])|\\')

SEVERITY_ALIASES = {
    "blocker": "critical",
    "severe": "critical",
    "high": "major",
    "important": "major",
    "medium": "minor",
    "moderate": "minor",
    "warning": "minor",
    "low": "nit",
    "minimal": "nit",
    "trivial": "nit",
    "info": "nit",
    "suggestion": "nit",
}
CATEGORY_ALIASES = {
    "bug": "defect",
    "correctness": "defect",
    "defact": "defect",
    "error": "defect",
    "logic": "defect",
    "reliability": "defect",
    "maintenance": "maintainability",
    "style": "maintainability",
    "readability": "maintainability",
    "documentation": "maintainability",
    "docs": "maintainability",
    "testing": "maintainability",
    "perf": "performance",
    "efficiency": "performance",
}
SEVERITIES = ("critical", "major", "minor", "nit")
CATEGORIES = ("defect", "security", "performance", "maintainability")
CODE_ALIASES = ("code", "snippet", "code_snippet", "existing", "lines", "existing_lines")


def loads(text: str):
    """json.loads that also accepts raw control characters and stray backslashes."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        fixed = ESCAPE.sub(lambda m: m.group(0) if m.group(1) else "\\\\", text)
        return json.loads(fixed, strict=False)


def decoded(value, repairs: list[str], name: str):
    """A list or object that was sent as a JSON string, decoded; anything else as is."""
    if isinstance(value, str) and value.strip()[:1] in ("[", "{"):
        try:
            result = loads(value.strip())
        except json.JSONDecodeError:
            return value
        repairs.append(f"{name}: decoded from a JSON string")
        return result
    return value


def enum_value(value, choices, aliases, repairs: list[str], name: str):
    if not isinstance(value, str):
        return value
    key = value.strip().lower()
    if key in choices:
        if key != value:
            repairs.append(f"{name}: {value!r} -> {key!r}")
        return key
    if key in aliases:
        repairs.append(f"{name}: {value!r} -> {aliases[key]!r}")
        return aliases[key]
    return value


def evidence_ids(value, repairs: list[str]) -> list[str] | None:
    value = decoded(value, repairs, "evidence")
    if value is None:
        return None
    if isinstance(value, str):
        parts = [part for part in re.split(r"[\s,;]+", value) if part]
        repairs.append("evidence: split from a string")
        return parts
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str):
                out += [part for part in re.split(r"[\s,;]+", item) if part]
            elif item is not None:
                out.append(str(item))
        return out
    return [str(value)]


def first_sentence(text: str, limit: int = 140) -> str:
    sentence = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]
    return sentence if len(sentence) <= limit else sentence[: limit - 1].rstrip() + "…"


def finding_item(item: dict, repairs: list[str]) -> dict:
    """Normalize one report_finding item (before validation)."""
    item = dict(item)
    if "existing_code" not in item:
        for alias in CODE_ALIASES:
            if isinstance(item.get(alias), str) and item[alias].strip():
                item["existing_code"] = item.pop(alias)
                repairs.append(f"existing_code: taken from {alias!r}")
                break
    code = item.get("existing_code")
    if isinstance(code, list) and all(isinstance(line, str) for line in code):
        item["existing_code"] = "\n".join(code)
        repairs.append("existing_code: joined from a list of lines")
    elif isinstance(code, str) and "\n" not in code and "\\n" in code:
        item["existing_code"] = code.replace("\\n", "\n")
        repairs.append("existing_code: unescaped \\n")
    severity, category = item.get("severity"), item.get("category")
    if isinstance(severity, str) and severity.strip().lower() in CATEGORIES:
        if not isinstance(category, str) or category.strip().lower() not in CATEGORIES:
            item["category"], item["severity"] = severity, category  # swapped fields
            repairs.append("severity/category: swapped")
    item["severity"] = enum_value(
        item.get("severity"), SEVERITIES, SEVERITY_ALIASES, repairs, "severity"
    )
    item["category"] = enum_value(
        item.get("category"), CATEGORIES, CATEGORY_ALIASES, repairs, "category"
    )
    if item.get("severity") not in SEVERITIES:
        if item.get("severity") is not None:
            repairs.append(f"severity: unknown {item['severity']!r} -> 'minor'")
        else:
            repairs.append("severity: missing -> 'minor'")
        item["severity"] = "minor"  # severity only orders comments
    if item.get("category") not in CATEGORIES:
        repairs.append(f"category: {item.get('category')!r} -> 'maintainability'")
        item["category"] = "maintainability"
    title, description = item.get("title"), item.get("description")
    if not (isinstance(title, str) and title.strip()) and isinstance(description, str):
        if description.strip():
            item["title"] = first_sentence(description)
            repairs.append("title: first sentence of description")
    elif isinstance(title, str) and not (isinstance(description, str) and description.strip()):
        item["description"] = title
        repairs.append("description: copied from title")
    if "evidence" in item:
        item["evidence"] = evidence_ids(item["evidence"], repairs)
        if item["evidence"] is None:
            item.pop("evidence")
    else:
        item["evidence"] = []
    if item.get("line_hint") in (0, "", None):
        item.pop("line_hint", None)
    elif isinstance(item.get("line_hint"), str):
        digits = re.findall(r"\d+", item["line_hint"])
        if digits:
            item["line_hint"] = int(digits[0])
            repairs.append("line_hint: parsed from a string")
        else:
            item.pop("line_hint")
    return item


def report_arguments(arguments, repairs: list[str]) -> dict:
    """report_finding arguments in the {"findings": [...]} shape, items normalized."""
    arguments = decoded(arguments, repairs, "arguments")
    if isinstance(arguments, list):
        arguments = {"findings": arguments}
        repairs.append("findings: a bare list")
    if not isinstance(arguments, dict):
        return {"findings": arguments}
    if "findings" not in arguments:
        if "finding" in arguments:
            arguments = {**arguments, "findings": arguments.pop("finding")}
            repairs.append("findings: from 'finding'")
        elif "path" in arguments or "existing_code" in arguments or "title" in arguments:
            arguments = {"findings": [arguments]}  # one finding passed flat
    findings = decoded(arguments.get("findings"), repairs, "findings")
    if isinstance(findings, dict):
        findings = [findings]
        repairs.append("findings: one object, not a list")
    if isinstance(findings, list):
        items = []
        for item in findings:
            item = decoded(item, repairs, "finding")
            items.append(finding_item(item, repairs) if isinstance(item, dict) else item)
        findings = items
    return {**arguments, "findings": findings}
