"""GitLab diff 的行索引：判断一个位置是否在改动里，并换算成评论 position。"""
from __future__ import annotations

import re
from dataclasses import dataclass

_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_DIFF_MARKER = re.compile(r"^[+\-](?![+\-])")


@dataclass(frozen=True)
class DiffLine:
    hunk: int
    old_line: int | None
    new_line: int | None
    text: str

    @property
    def is_added(self) -> bool:
        return self.old_line is None


class FileDiff:
    def __init__(self, old_path: str, new_path: str, diff: str):
        self.old_path = old_path
        self.new_path = new_path
        self.lines = list(_parse(diff))
        self._new = {line.new_line: line for line in self.lines if line.new_line}
        self._old = {line.old_line: line for line in self.lines if line.old_line}

    def _side(self, side: str) -> dict[int, DiffLine]:
        return self._old if side == "old" else self._new

    def line(self, side: str, number: int | None) -> DiffLine | None:
        return self._side(side).get(number)

    def covers(self, side: str, start: int, end: int) -> bool:
        """这段行号是否全部落在同一个 hunk 内。"""
        lines = [self.line(side, number) for number in range(start, end + 1)]
        return all(lines) and len({line.hunk for line in lines}) == 1

    def find(self, code: str, side: str, near: int | None = None) -> tuple[int, int] | None:
        """在一侧的改动中定位代码片段，有多处时取最接近 near 的一处。"""
        rows = sorted(self._side(side).items())
        for wanted in _snippet_candidates(code):
            hits = [
                (rows[i][0], rows[i + len(wanted) - 1][0])
                for i in range(len(rows) - len(wanted) + 1)
                if rows[i][1].hunk == rows[i + len(wanted) - 1][1].hunk
                and [row[1].text.strip() for row in rows[i:i + len(wanted)]] == wanted
            ]
            if hits:
                return min(hits, key=lambda hit: abs(hit[1] - near)) if near else hits[0]
        return None

    def position(self, side: str, number: int) -> dict:
        """GitLab 要求上下文行同时给出新旧行号。"""
        line = self.line(side, number)
        position = {"old_path": self.old_path, "new_path": self.new_path}
        if line.new_line:
            position["new_line"] = line.new_line
        if line.old_line:
            position["old_line"] = line.old_line
        return position


class DiffIndex:
    def __init__(self, changes: list[dict]):
        self.files: list[FileDiff] = []
        self._by_path: dict[str, FileDiff] = {}
        for change in changes:
            new_path = change.get("new_path") or change.get("old_path", "")
            old_path = change.get("old_path") or new_path
            file_diff = FileDiff(old_path, new_path, change.get("diff") or "")
            self.files.append(file_diff)
            self._by_path.setdefault(new_path, file_diff)
            self._by_path.setdefault(old_path, file_diff)

    def get(self, path: str) -> FileDiff | None:
        path = path.removeprefix("./")
        return self._by_path.get(path) or self._by_path.get(re.sub(r"^[ab]/", "", path))

    def first_added_line(self) -> tuple[str, int] | None:
        for file_diff in self.files:
            for line in file_diff.lines:
                if line.is_added:
                    return file_diff.new_path, line.new_line
        return None


def _parse(diff: str):
    hunk = 0
    old_line = new_line = None
    for raw in diff.split("\n"):
        header = _HUNK_HEADER.match(raw)
        if header:
            hunk += 1
            old_line, new_line = int(header.group(1)), int(header.group(2))
        elif new_line is None or raw.startswith("\\"):
            continue
        elif raw.startswith("+"):
            yield DiffLine(hunk, None, new_line, raw[1:])
            new_line += 1
        elif raw.startswith("-"):
            yield DiffLine(hunk, old_line, None, raw[1:])
            old_line += 1
        elif raw.startswith(" "):
            yield DiffLine(hunk, old_line, new_line, raw[1:])
            old_line += 1
            new_line += 1


def _snippet_candidates(code: str) -> list[list[str]]:
    """先按原文匹配；模型带上了 diff 的 +/- 前缀时再去掉重试。"""
    candidates = []
    for transform in (lambda line: line, lambda line: _DIFF_MARKER.sub("", line)):
        lines = [transform(line).strip() for line in code.replace("\r\n", "\n").split("\n")]
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        if lines and lines not in candidates:
            candidates.append(lines)
    return candidates
