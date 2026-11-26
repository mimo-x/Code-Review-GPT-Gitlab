from __future__ import annotations

from difflib import SequenceMatcher

from review_core.common import ReviewCoreError, source_lines

from .models import Relocation


def relocate(intel, old_location, snippet: str, new_side: str = "head") -> Relocation:
    if not snippet.strip():
        raise ReviewCoreError("Relocation requires a nonempty source snippet")
    if old_location.sha != intel.workspace.snapshot.sha(old_location.side):
        raise ReviewCoreError("Old location SHA does not belong to this snapshot side")
    old_content = intel.workspace.read_file(
        old_location.path, old_location.side, old_location.start_line, old_location.end_line
    )
    if old_content.blob_hash != old_location.blob_hash or old_content.text != snippet:
        raise ReviewCoreError("Old snippet does not match its recorded source")
    old_symbol = intel.enclosing_symbol(
        old_location.path, old_location.start_line, old_location.side
    )
    language = intel.classify_file(old_location.path, old_location.side).language
    expected = intel.normalize(snippet, language)
    candidates = []
    if old_location.path in intel.workspace.tree(new_side):
        outline = intel.outline(old_location.path, new_side)
        candidates = [
            symbol
            for symbol in outline.items
            if old_symbol and symbol.qualified_name == old_symbol.qualified_name
        ]
    same_symbol = bool(candidates)
    if not candidates:
        for change in intel.workspace.snapshot.changes:
            if change.new_path and change.new_path in intel.workspace.tree(new_side):
                candidates.extend(intel.outline(change.new_path, new_side).items)
    exact = []
    fuzzy = []
    width = len(source_lines(snippet))
    for symbol in candidates:
        content = intel.read_symbol(symbol.id, new_side)
        lines = source_lines(content.text)
        for index in range(max(0, len(lines) - width + 1)):
            window = "".join(lines[index : index + width])
            normalized = intel.normalize(window, language)
            location = symbol.location.model_copy(
                update={
                    "start_line": content.start_line + index,
                    "end_line": content.start_line + index + width - 1,
                    "start_column": 0,
                }
            )
            if normalized.digest == expected.digest:
                exact.append(location)
            else:
                score = SequenceMatcher(None, snippet, window, autojunk=False).ratio()
                if score >= 0.8:
                    fuzzy.append((score, location))
    if not old_symbol and old_location.path in intel.workspace.tree(new_side):
        same_symbol = True
        content = intel.workspace.read_file(old_location.path, new_side)
        lines = source_lines(content.text)
        for index in range(max(0, len(lines) - width + 1)):
            window = "".join(lines[index : index + width])
            if intel.normalize(window, language).digest == expected.digest:
                exact.append(
                    intel.location(old_location.path, index + 1, new_side).model_copy(
                        update={"end_line": index + width}
                    )
                )
    unique = {(value.sha, value.path, value.start_line, value.end_line): value for value in exact}
    if unique:
        locations = tuple(unique.values())
        status = "ambiguous"
        confidence = 0
        if len(locations) == 1:
            status = "exact" if same_symbol else "candidate"
            confidence = 1.0 if same_symbol else 0.8
        return Relocation(
            status=status,
            locations=locations,
            confidence=confidence,
            basis="same normalized source; cross-symbol lineage and issue resolution require separate verification",
        )
    if fuzzy:
        score = max(value[0] for value in fuzzy)
        locations = tuple(value[1] for value in fuzzy if value[0] == score)
        return Relocation(
            status="candidate" if len(locations) == 1 else "ambiguous",
            locations=locations,
            confidence=score,
            basis="similar source; requires investigation",
        )
    return Relocation(
        status="unlocated", basis="No reliable location found; issue status remains unknown"
    )
