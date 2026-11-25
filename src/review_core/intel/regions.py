from __future__ import annotations

from bisect import bisect_left, bisect_right

from .models import ChangeBoundary


def change_boundaries(intel, change, lines, reliable) -> tuple[ChangeBoundary, ...]:
    """Retain hunk ends and AST nesting depth without making token-budget decisions."""
    owned = {line.id for line in lines}
    boundaries = {}
    for hunk in change.hunks:
        members = [line for line in hunk.lines if line.id in owned]
        if members:
            last = members[-1].id
            boundaries[last] = ChangeBoundary(after_line_id=last, kind="hunk")
    if reliable:
        for side, path, kind in (
            ("base", change.old_path, "delete"),
            ("head", change.new_path, "add"),
        ):
            members = [line for line in lines if line.kind == kind]
            if not members:
                continue
            numbers = [line.old_line if side == "base" else line.new_line for line in members]
            content = intel.workspace.read_file(path, side)
            language = intel.classify_file(path, side).language
            root = intel.syntax.root(content.blob_hash, language, content.text)
            stack = [(root, 0)]
            while stack:
                node, depth = stack.pop()
                position = node.range()
                first = position.start.line + 1
                last = position.end.line + (position.end.column > 0)
                start = bisect_left(numbers, first)
                end = bisect_right(numbers, last)
                if start >= end:
                    continue
                if node.is_named():
                    line_id = members[end - 1].id
                    existing = boundaries.get(line_id)
                    if existing is None or (existing.kind == "syntax" and depth < existing.depth):
                        boundaries[line_id] = ChangeBoundary(
                            after_line_id=line_id, kind="syntax", depth=depth
                        )
                stack.extend((child, depth + 1) for child in node.children())
    return tuple(boundaries[line.id] for line in lines if line.id in boundaries)
