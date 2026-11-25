"""Model-facing text for tool results: compact, numbered, with explicit coverage status.

Renderers turn one result item into one text block; Tools decides how many blocks fit.
Structured results stay in the evidence store, so nothing here needs to be parseable.
"""

from __future__ import annotations

from collections import Counter

from review_core.common import Analyzed, source_lines
from review_core.textshape import fold

SHORT_ID = 12


def short(identifier: str) -> str:
    return identifier[:SHORT_ID]


def numbered(item: dict, limit: int, char_offset: int = 0) -> str:
    """Source with snapshot line numbers; * marks lines changed in this review."""
    changed = set(item.get("changed_lines", ()))
    lines = []
    for number, text in enumerate(source_lines(item["text"]), start=item["start_line"]):
        hint = f"read_file start_line={number} end_line={number} char_offset={char_offset + limit}"
        lines.append(
            f"{'*' if number in changed else ' '} L{number} {fold(text, limit, char_offset, hint)}"
        )
    return "\n".join(lines)


def source_header(item: dict) -> str:
    return (
        f"{item['path']} @{item['side']} L{item['start_line']}-{item['end_line']} "
        f"of {item['total_lines']} (* = changed line)"
    )


def _head(signature: str) -> str:
    """First signature line that is not a decorator or annotation."""
    lines = [line.strip() for line in signature.strip().splitlines() if line.strip()]
    return next((line for line in lines if not line.startswith("@")), lines[0] if lines else "")


def outline_item(item: dict, limit: int) -> str:
    location = item["location"]
    first = _head(item["signature"])
    marks = " [changed]" if item.get("changed") else ""
    visibility = "" if item["visibility"] == "unknown" else f" {item['visibility']}"
    return (
        f"L{location['start_line']}-{location['end_line']} {item['kind']}{visibility} "
        f"{item['qualified_name']}{marks}: {fold(first, min(limit, 160))}"
    )


def definition_item(item: dict, limit: int) -> str:
    symbol = item["symbol"]
    location = symbol["location"]
    first = _head(symbol["signature"])
    return (
        f"{location['path']}:{location['start_line']} {symbol['kind']} {symbol['qualified_name']} "
        f"[{item['confidence']}: {item['basis']}] {fold(first, min(limit, 160))}"
    )


def reference_item(item: dict, limit: int) -> str:
    location = item["location"]
    return (
        f"{location['path']}:{location['start_line']} {item['relation']} "
        f"[{item['confidence']}] {fold(item['context'].strip(), limit)}"
    )


def match_item(item: dict, limit: int) -> str:
    location = item["location"]
    text = item["text"].strip().splitlines()
    head = fold(text[0], limit) if text else ""
    more = f" (+{len(text) - 1} lines)" if len(text) > 1 else ""
    bindings = ", ".join(f"{k}={v}" for k, v in item.get("bindings", {}).items())
    return f"{location['path']}:{location['start_line']} {head}{more}" + (
        f"  {{{bindings}}}" if bindings else ""
    )


def change_item(item: dict, limit: int) -> str:
    symbol = item["symbol"] or "<outside any symbol>"
    return (
        f"{item['cluster']} {item['unit']} {item['path']} {symbol} "
        f"[{', '.join(item['kinds'])}] (+{item['added']} -{item['deleted']})"
    )


def path_item(item: dict, limit: int) -> str:
    size = item.get("size")
    return f"{item['path']}" + (f" ({size} bytes)" if size is not None else "")


def search_item(item: dict, limit: int) -> str:
    return f"{item['path']}:{item['line']}: {fold(item['text'], limit)}"


def compare_item(item: dict, limit: int) -> str:
    if not item.get("changed"):
        return f"{item['symbol']['qualified_name']} is not changed in this review."
    unit = item["unit"]
    lines = [f"changed: {', '.join(unit['kinds'])}"]
    lines += [fold(line, limit) for line in item["diff"].splitlines()]
    for candidate in item.get("pairing_candidates", ()):
        lines.append(
            f"possible rename: {candidate['base_symbol']['qualified_name']} -> "
            f"{candidate['head_symbol']['qualified_name']} "
            f"(similarity {candidate['similarity']:.2f}, not established)"
        )
    return "\n".join(lines)


def hunk_lines(item: dict, limit: int) -> list[str]:
    """Diff lines with the line number of their own side: - base, + head, context head."""
    out = []
    for line in item["lines"]:
        if line["kind"] == "delete":
            out.append(f"-L{line['old_line']} {fold(line['text'], limit)}")
        elif line["kind"] == "add":
            out.append(f"+L{line['new_line']} {fold(line['text'], limit)}")
        else:
            out.append(f" L{line['new_line']} {fold(line['text'], limit)}")
    return out


def hunk_header(item: dict) -> str:
    path = item["new_path"] or item["old_path"]
    if item["old_path"] and item["new_path"] and item["old_path"] != item["new_path"]:
        path = f"{item['old_path']} -> {item['new_path']}"
    units = f" [{' '.join(item['units'])}]" if item.get("units") else ""
    if item.get("kind") == "file":
        return f"{path}: {item['summary']}{units}"
    return (
        f"@@ {path} -{item['old_start']},{item['old_length']} "
        f"+{item['new_start']},{item['new_length']} @@{units}"
    )


def status(result: Analyzed, *, next_offset: int | None, error: str | None) -> list[str]:
    """Footer lines saying exactly what is missing and what to do about it."""
    lines = []
    if error:
        lines.append(f"ERROR: {error}")
    if next_offset is not None:
        lines.append(f"More results: call again with offset={next_offset}.")
    if result.limits:
        lines.append(
            "INCOMPLETE, stopped by "
            + "; ".join(result.limits)
            + ". Narrow the query to see the rest."
        )
    if result.gaps:
        counts = Counter(gap.kind for gap in result.gaps)
        summary = ", ".join(f"{kind} {count}" for kind, count in sorted(counts.items()))
        samples = "; ".join(str(gap) for gap in result.gaps[:3])
        lines.append(
            f"PARTIAL ({summary}): {samples}. Text tools (code_search, read_file) still work there."
        )
    if result.issues:
        lines.append("ISSUES: " + "; ".join(result.issues[:3]))
    return lines
