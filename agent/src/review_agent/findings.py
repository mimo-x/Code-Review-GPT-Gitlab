"""Findings and their anchors.

A finding is anchored by a snippet of the code it is about, never by a line number the
model wrote: the snippet is located deterministically (diff new side, diff old side, then
whole files), so line numbers are always real and line errors never reach training data.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from review_core.common import ReviewCoreError, Side, source_lines

Category = Literal["defect", "security", "performance", "maintainability"]
Severity = Literal["critical", "major", "minor", "nit"]
SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2, "nit": 3}
# Prefixes our own tools put in front of code lines: "+L12 ", "-L3 ", " L4 ", "* L5 ";
# models also write "L12: ", "L46-47: " or "266<TAB>".
TOOL_PREFIX = re.compile(r"^\s*[*+\-]?\s*(?:L\d+(?:-\d+)?:? ?|\d+\t)")
NUMBERED = re.compile(r"^\s*([*+\-]?)\s*(?:L(\d+)(?:-\d+)?:? ?|(\d+)\t)(.*)$")
# A path written in front of a numbered line: "src/a.php L90: code".
PATH_PREFIX = re.compile(r"^\s*[\w./\-]+\.\w+:?\s+(?=[*+\-]?\s*L\d)")
WORDY = re.compile(r"\w{2,}")
DIFF_MARKER = re.compile(r"^[+\-](?![+\-])")
MAX_ANCHOR_LINES = 40
MIN_PARTIAL_CHARS = 4


# What the model reports; validated before it becomes a Finding. (A comment, not a
# docstring: docstrings end up in the tool schema the model sees.)
class FindingInput(BaseModel):
    path: str
    existing_code: str = Field(
        description="required: 1-10 consecutive lines copied from read_diff or read_file "
        "output, the code the issue is about"
    )
    title: str = Field(description="one sentence: what is wrong")
    description: str = Field(description="why it is wrong and its consequence; how to fix")
    category: Category
    severity: Severity
    condition: str | None = Field(
        default=None, description="for a conditional risk: when the problem happens"
    )
    evidence: list[str] = Field(description="evidence ids of the tool results showing the code")
    suggestion: str | None = Field(default=None, description="optional replacement code")
    candidate: str | None = Field(default=None, description="the K# this finding resolves")
    about_removal: bool | None = Field(
        default=None,
        description="true only when removing the code in existing_code is itself the problem",
    )
    line_hint: int | None = Field(
        default=None, ge=1, description="optional, to pick among repeated snippets"
    )

    @field_validator("title", "description", "existing_code")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value


class Finding(BaseModel):
    id: str
    path: str
    side: Side
    start_line: int
    end_line: int
    in_diff: bool
    anchor: str  # how the snippet was located
    title: str
    description: str
    category: Category
    severity: Severity
    condition: str | None = None
    evidence: list[str]
    suggestion: str | None = None
    existing_code: str
    unit: str | None = None
    cluster: str | None = None
    reported_step: int
    updated_step: int | None = None
    about_removal: bool = False
    withdrawn: bool = False
    withdraw_reason: str | None = None


def snippet_lines(snippet: str) -> list[str]:
    lines = []
    for line in snippet.replace("\r\n", "\n").split("\n"):
        line = PATH_PREFIX.sub("", line, count=1)
        line = TOOL_PREFIX.sub("", line, count=1)
        line = DIFF_MARKER.sub("", line, count=1)
        lines.append(line.strip())
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _windows(target: list[str], numbers: list[int], wanted: list[str], loose: bool):
    """(start, end) line numbers where wanted occurs as a contiguous run of target."""
    if loose:
        target = [re.sub(r"\s+", "", line) for line in target]
        wanted = [re.sub(r"\s+", "", line) for line in wanted]
    size = len(wanted)
    for index in range(len(target) - size + 1):
        if target[index : index + size] == wanted:
            yield numbers[index], numbers[index + size - 1]


class Anchorer:
    """Locates snippets in one snapshot; reads files through the workspace."""

    def __init__(self, workspace):
        self.workspace = workspace

    def locate(self, path: str, snippet: str, line_hint: int | None = None):
        wanted = snippet_lines(snippet)
        if not wanted:
            raise ReviewCoreError("existing_code has no code lines")
        if not any(WORDY.search(line) for line in wanted):
            raise ReviewCoreError(
                "existing_code has only brackets or punctuation; copy the line(s) with the "
                "code the issue is about"
            )
        if len(wanted) > MAX_ANCHOR_LINES:  # anchor on the start of an overlong snippet
            wanted = wanted[:10]
            snippet = "\n".join(snippet.replace("\r\n", "\n").split("\n")[:10])
        changes = [
            change
            for change in self.workspace.snapshot.changes
            if path in (change.old_path, change.new_path)
        ]
        in_tree = {side: path in self.workspace.tree(side) for side in ("head", "base")}
        if not changes and not any(in_tree.values()):
            raise ReviewCoreError(f"{path} is neither changed nor present in the repository")
        sources = []
        for change in changes:
            for hunk in change.hunks:
                new = [line for line in hunk.lines if line.kind != "delete"]
                old = [line for line in hunk.lines if line.kind != "add"]
                changed_new = {line.new_line for line in hunk.lines if line.kind == "add"}
                changed_old = {line.old_line for line in hunk.lines if line.kind == "delete"}
                sources.append(("diff-head", "head", new, lambda line: line.new_line, changed_new))
                sources.append(("diff-base", "base", old, lambda line: line.old_line, changed_old))
        for kind in ("exact", "loose"):
            for name, side, lines, number, changed in sources:
                hits = list(
                    _windows(
                        [line.text.strip() for line in lines],
                        [number(line) for line in lines],
                        wanted,
                        kind == "loose",
                    )
                )
                if hits:
                    return self._pick(hits, changed, line_hint, side, True, f"{name}/{kind}")
        for side in ("head", "base"):
            if not in_tree[side]:
                continue
            try:
                content = self.workspace.read_file(path, side)
            except ReviewCoreError:
                continue
            text = [line.strip() for line in source_lines(content.text)]
            numbers = list(range(1, len(text) + 1))
            for kind in ("exact", "loose"):
                hits = list(_windows(text, numbers, wanted, kind == "loose"))
                if hits:
                    changed = {
                        line.old_line if side == "base" else line.new_line
                        for change in changes
                        for hunk in change.hunks
                        for line in hunk.lines
                        if line.kind == ("delete" if side == "base" else "add")
                    }
                    in_diff = bool(changed)
                    return self._pick(
                        hits, changed, line_hint, side, in_diff, f"file-{side}/{kind}"
                    )
        partial = self._partial(wanted, changes, line_hint)
        if partial:
            return partial
        numbered = self._numbered(path, snippet, changes, in_tree)
        if numbered:
            return numbered
        hint = self._actual_lines(path, snippet, line_hint, in_tree)
        raise ReviewCoreError(
            f"existing_code was not found in {path}; copy 1-10 consecutive lines exactly as "
            "they appear in read_diff or read_file output, from one side of the diff" + hint
        )

    def in_file(self, path: str, snippet: str, side: str, line_hint: int | None = None):
        """The anchor of a snippet in one side's whole file, or None when it is not there."""
        wanted = snippet_lines(snippet)
        if not wanted or path not in self.workspace.tree(side):
            return None
        try:
            text = [line.strip() for line in source_lines(self.workspace.read_file(path, side).text)]
        except ReviewCoreError:
            return None
        changes = [c for c in self.workspace.snapshot.changes if path in (c.old_path, c.new_path)]
        changed = {
            line.old_line if side == "base" else line.new_line
            for change in changes
            for hunk in change.hunks
            for line in hunk.lines
            if line.kind == ("delete" if side == "base" else "add")
        }
        numbers = list(range(1, len(text) + 1))
        for kind in ("exact", "loose"):
            hits = list(_windows(text, numbers, wanted, kind == "loose"))
            if hits:
                return self._pick(hits, changed, line_hint, side, bool(changed), f"file-{side}/{kind}")
        return None

    def text(self, path: str, side: str) -> str:
        if path not in self.workspace.tree(side):
            return ""
        try:
            return self.workspace.read_file(path, side).text
        except ReviewCoreError:
            return ""

    def _side_lines(self, path: str, side: str, in_tree) -> list[str] | None:
        if not in_tree.get(side):
            return None
        try:
            return source_lines(self.workspace.read_file(path, side).text)
        except ReviewCoreError:
            return None

    def _numbered(self, path: str, snippet: str, changes, in_tree):
        """Snippets copied with their line prefixes ("-L124 ...", "+L27 ...") but not as one
        run (lines from two hunks, a skipped line): anchor on the prefixed lines whose text
        really is at that line, on the side the prefix names."""
        verified: dict[str, list[int]] = {"head": [], "base": []}
        files = {}
        for raw in snippet.replace("\r\n", "\n").split("\n"):
            match = NUMBERED.match(PATH_PREFIX.sub("", raw, count=1))
            if not match:
                continue
            marker, text = match.group(1), match.group(4)
            number = int(match.group(2) or match.group(3))
            if not WORDY.search(text):
                continue
            side = "base" if marker == "-" else "head"
            if side not in files:
                files[side] = self._side_lines(path, side, in_tree)
            lines = files[side]
            if not lines or not 1 <= number <= len(lines):
                continue
            if re.sub(r"\s+", "", lines[number - 1]) == re.sub(r"\s+", "", text):
                verified[side].append(number)
        side = max(verified, key=lambda key: len(verified[key]))
        numbers = sorted(set(verified[side]))
        if not numbers:
            return None
        run = [numbers[0]]  # the first block of nearby verified lines
        for number in numbers[1:]:
            if number - run[-1] > 2:
                break
            run.append(number)
        changed = {
            line.old_line if side == "base" else line.new_line
            for change in changes
            for hunk in change.hunks
            for line in hunk.lines
            if line.kind == ("delete" if side == "base" else "add")
        }
        start, end = run[0], run[-1]
        return {
            "side": side,
            "start_line": start,
            "end_line": end,
            "in_diff": any(start <= line <= end for line in changed),
            "anchor": f"numbered, {len(run)}/{len(numbers)} lines",
        }

    def _actual_lines(self, path: str, snippet: str, line_hint: int | None, in_tree) -> str:
        """For the error message: the real code at the lines the model pointed at."""
        wanted = []
        for raw in snippet.replace("\r\n", "\n").split("\n"):
            match = NUMBERED.match(PATH_PREFIX.sub("", raw, count=1))
            if match:
                number = int(match.group(2) or match.group(3))
                wanted.append(("base" if match.group(1) == "-" else "head", number))
        if line_hint:
            wanted.append(("head", line_hint))
        shown = []
        for side, number in dict.fromkeys(wanted):
            lines = self._side_lines(path, side, in_tree)
            if lines and 1 <= number <= len(lines):
                shown.append(f"{'-' if side == 'base' else '+'}L{number} {lines[number - 1]}")
            if len(shown) >= 4:
                break
        return (". The file has at those lines:\n" + "\n".join(shown)) if shown else ""

    def code_at(self, path: str, line: int) -> tuple[str, str] | None:
        """(code, side) of a changed line the model named only by number: an added line at
        that head line, else a deleted line at that base line."""
        for kind, side in (("add", "head"), ("delete", "base")):
            for change in self.workspace.snapshot.changes:
                if path not in (change.old_path, change.new_path):
                    continue
                for hunk in change.hunks:
                    for item in hunk.lines:
                        number = item.new_line if side == "head" else item.old_line
                        if item.kind == kind and number == line and WORDY.search(item.text):
                            return item.text, side
        return None

    @staticmethod
    def _partial(wanted: list[str], changes, line_hint: int | None):
        """Last resort inside one hunk: snippets that interleave deleted and added lines
        (copied from read_diff) or skip lines. At least half of the snippet's non-trivial
        lines must occur in the hunk; the anchor spans the matched lines of one side."""

        def key(text: str) -> str:
            return re.sub(r"\s+", "", text)

        targets = {key(line) for line in wanted if len(key(line)) >= MIN_PARTIAL_CHARS}
        if not targets:
            return None
        need = max(1, -(-len(targets) // 2))
        best = None
        for change in changes:
            for hunk in change.hunks:
                hits = [line for line in hunk.lines if key(line.text) in targets]
                distinct = len({key(line.text) for line in hits})
                if distinct < need:
                    continue
                head = [line.new_line for line in hits if line.kind != "delete"]
                touched_head = any(line.kind == "add" for line in hits)
                if head and (touched_head or not any(line.kind == "delete" for line in hits)):
                    side, numbers = "head", head
                else:
                    side, numbers = "base", [line.old_line for line in hits if line.kind != "add"]
                distance = abs(min(numbers) - line_hint) if line_hint else 0
                score = (-distinct, not any(line.kind != "context" for line in hits), distance)
                if best is None or score < best[0]:
                    best = (score, side, min(numbers), max(numbers), distinct)
        if best is None:
            return None
        _, side, start, end, distinct = best
        return {
            "side": side,
            "start_line": start,
            "end_line": end,
            "in_diff": True,
            "anchor": f"diff-partial, {distinct}/{len(targets)} lines",
        }

    @staticmethod
    def _pick(hits, changed, line_hint, side, in_diff, how):
        def score(hit):
            start, end = hit
            touches = any(start <= line <= end for line in changed)
            distance = abs(start - line_hint) if line_hint else 0
            return (not touches, distance, start)

        start, end = min(hits, key=score)
        touches = any(start <= line <= end for line in changed)
        return {
            "side": side,
            "start_line": start,
            "end_line": end,
            "in_diff": in_diff and touches if how.startswith("file") else in_diff,
            "anchor": how + (f", {len(hits)} matches" if len(hits) > 1 else ""),
        }
