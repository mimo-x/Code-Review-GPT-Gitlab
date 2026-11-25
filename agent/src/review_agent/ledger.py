"""The investigator's record of one episode: candidate concerns, reported findings and the
evidence (tool results) they cite.

The environment routes the agent tools here (note_candidates -> note, report_finding ->
report, update_finding -> update, finish -> finish); each returns the observation text, an
error or None, and None. Findings are anchored to the code and vetted before they are kept.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from review_core.common import ReviewCoreError
from review_core.intel.render import SHORT_ID
from review_core.intel.tools import drop_empty

from . import checks
from .agent_tools import CandidatesArgs, FinishArgs, UpdateArgs, validation_message
from .coverage import CoverageCheck
from .findings import WORDY, Finding, FindingInput, snippet_lines

MAX_RECENT_EVIDENCE = 8
CANDIDATE_ID = re.compile(r"\bK\d+\b")
MAX_NEW_CANDIDATES = 30  # per call; small models sometimes repeat a list in a loop
MAX_SHOWN_CANDIDATES = 30


def _normalized(text: str) -> str:
    return re.sub(r"\s+", "", text)


class FindingLedger:
    def __init__(self, workspace, plan, cluster, units: dict, anchorer, lock, *,
                 coverage: CoverageCheck | None = None):
        self.workspace = workspace
        self.plan = plan
        self.cluster = cluster
        self.units = units
        self.anchorer = anchorer
        self.lock = lock
        self.coverage = coverage
        self.unit_cluster = {
            key: cluster.handle for cluster in plan.clusters for key in cluster.unit_ids
        }
        self.findings: list[Finding] = []
        self.evidence: dict[str, str] = {}  # short id -> full id, in order seen
        self.evidence_text: dict[str, str] = {}  # short id -> tool output, for auto-citing
        self.candidates: list[dict] = []
        self.report_streak = 0  # consecutive report_finding calls with nothing accepted
        self.finish_warned = False
        # deterministic fixes made during the current tool call (reset by the environment)
        self.repairs: list[str] = []
        self.summary: dict | None = None  # set by an accepted finish

    def seed(self, seeds: list[dict]) -> None:
        """Candidates from earlier sampling passes, recorded before the episode starts."""
        for seed in seeds:
            self.candidates.append({
                "id": f"K{len(self.candidates) + 1}", "concern": seed["concern"],
                "unit": seed.get("unit"), "priority": seed.get("priority", "medium"),
                "status": "open", "note": None,
            })

    def record_evidence(self, short: str, full: str, text: str) -> None:
        self.evidence[short] = full
        self.evidence_text.pop(short, None)  # keep insertion order = recency
        self.evidence_text[short] = text

    def coverage_line(self) -> str | None:
        if self.coverage is None:
            return None
        return self.coverage.line(self.candidates, self.findings)

    # -- candidates ---------------------------------------------------------------------

    def open_candidates(self) -> list[dict]:
        return [c for c in self.candidates if c["status"] == "open"]

    def candidates_line(self) -> str:
        if not self.candidates:
            return "Candidates: none noted yet (use note_candidates)."
        open_ = self.open_candidates()
        if not open_:
            return f"Candidates: all {len(self.candidates)} reported or dismissed."
        shown = "; ".join(
            f"{c['id']} [{c['priority']}]{' ' + c['unit'] if c['unit'] else ''} {c['concern']}"
            for c in open_[:MAX_SHOWN_CANDIDATES]
        )
        more = len(open_) - MAX_SHOWN_CANDIDATES
        tail = f"; and {more} more" if more > 0 else ""
        return f"Open candidates ({len(open_)} of {len(self.candidates)}): {shown}{tail}"

    def _close_candidates(self, entries, status: str, finding: str | None = None) -> list[str]:
        closed = []
        for entry in entries:
            for key in CANDIDATE_ID.findall(str(entry)):
                for candidate in self.candidates:
                    if candidate["id"] == key and candidate["status"] == "open":
                        candidate.update(status=status, note=finding or str(entry))
                        closed.append(key)
        return closed

    def note(self, args: CandidatesArgs):
        added, repeated = [], 0
        known = {_normalized(c["concern"].lower()) for c in self.candidates}
        for item in args.add:
            key = _normalized(item.concern.lower())
            if not key or key in known:
                repeated += bool(key)
                continue
            if len(added) >= MAX_NEW_CANDIDATES:
                break
            known.add(key)
            candidate = {
                "id": f"K{len(self.candidates) + 1}",
                "concern": item.concern.strip(),
                "unit": item.unit.strip() if item.unit else None,
                "priority": item.priority,
                "status": "open",
                "note": None,
            }
            self.candidates.append(candidate)
            added.append(candidate["id"])
        dismissed = self._close_candidates(args.dismiss, "dismissed")
        if self.coverage is not None:
            self.coverage.mark_reviewed(getattr(args, "reviewed", []))
        parts = []
        if added:
            parts.append(f"Added {', '.join(added)}.")
        if repeated:
            parts.append(f"{repeated} already noted, not added again.")
        if dismissed:
            parts.append(f"Dismissed {', '.join(dismissed)}.")
        parts.append(self.candidates_line())
        if self.coverage_line():
            parts.append(self.coverage_line())
        return " ".join(parts), None, None

    def finish(self, args: FinishArgs):
        self._close_candidates(args.dismissed, "dismissed")
        remaining = self.open_candidates()
        if remaining and not self.finish_warned:
            self.finish_warned = True
            ids = ", ".join(c["id"] for c in remaining)
            return (
                f"Not finished: candidates {ids} are neither reported nor dismissed. Report "
                "them with report_finding, or call finish again listing them in dismissed "
                "with the reason.\n" + self.candidates_line(),
                "open candidates",
                None,
            )
        if self.coverage is not None:
            refusal = self.coverage.refuse_finish(self.candidates, self.findings)
            if refusal:
                return refusal, "uncovered units", None
        for candidate in remaining:
            candidate.update(status="unresolved")
        self.summary = args.model_dump() | {"candidates": self.candidates}
        return "Review of this assignment finished.", None, None

    # -- findings -----------------------------------------------------------------------

    def _evidence(self, ids: list[str]) -> tuple[list[str], list[str]]:
        known, unknown = [], []
        for identifier in ids:
            key = identifier.strip().removeprefix("evidence").strip()[:SHORT_ID]
            (known if key in self.evidence else unknown).append(key)
        return list(dict.fromkeys(known)), unknown

    def _recent_evidence(self) -> str:
        recent = list(self.evidence)[-MAX_RECENT_EVIDENCE:]
        return ", ".join(recent) if recent else "none yet (call a tool first)"

    def _anchor(self, path: str, snippet: str, hint: int | None) -> dict:
        with self.lock:
            return self.anchorer.locate(path, snippet, hint)

    def _unit_of(self, path: str, side: str, start: int, end: int) -> str | None:
        best = None
        for key, unit in self.units.items():
            if path not in (unit.old_path, unit.new_path):
                continue
            numbers = [
                line.old_line if side == "base" else line.new_line
                for line in unit.lines
                if line.kind != "context"
            ]
            numbers = [n for n in numbers if n is not None]
            if any(start <= n <= end for n in numbers):
                return key
            symbol = unit.base_symbol if side == "base" else unit.head_symbol
            if symbol and symbol.location.start_line <= start <= symbol.location.end_line:
                best = best or key
        return best

    def _changed_paths(self) -> list[str]:
        paths = []
        for change in self.workspace.snapshot.changes:
            paths += [change.new_path, change.old_path]
        return list(dict.fromkeys(p for p in paths if p))

    def _infer_path(self, code: str) -> str | None:
        """The changed file a snippet comes from, when the model left path out."""
        first = code.strip().split("\n", 1)[0]
        for path in self._changed_paths():
            if first.startswith(path):
                return path
        hits = []
        for path in self._changed_paths():
            try:
                self._anchor(path, code, None)
            except ReviewCoreError:
                continue
            hits.append(path)
        return hits[0] if len(hits) == 1 else None

    def _cite(self, path: str, code: str) -> str | None:
        """The most recent tool result showing the snippet (else the path), for a finding
        whose evidence ids were missing or wrong."""
        wanted = [_normalized(line) for line in snippet_lines(code) if WORDY.search(line)]
        recent = list(self.evidence_text.items())[::-1]
        for short, text in recent:
            flat = _normalized(text)
            if wanted and any(line in flat for line in wanted):
                return short
        for short, text in recent:
            if path in text:
                return short
        return None

    def report(self, arguments: dict, step: int):
        """Validate items one by one, so one bad item does not reject the others."""
        findings = arguments.get("findings")
        if not isinstance(findings, list) or not findings:
            text = (
                "Error: invalid arguments for report_finding: findings must be a non-empty "
                "array of finding objects."
            )
            return self._failed(text, "findings: not a list", [])
        valid, lines, errors = [], [], []
        for position, raw in enumerate(findings, start=1):
            label = f"finding {position}" if len(findings) > 1 else "finding"
            if not isinstance(raw, dict):
                errors.append(f"{label}: not an object")
                lines.append(f"{label} rejected: each finding must be a JSON object.")
                continue
            item = drop_empty(FindingInput, raw)
            code = item.get("existing_code")
            if not item.get("path") and isinstance(code, str) and code.strip():
                path = self._infer_path(code)
                if path:
                    item["path"] = path
                    self.repairs.append(f"{label} path: inferred {path}")
            if not (isinstance(code, str) and code.strip()) and item.get("path"):
                found = None
                if isinstance(item.get("line_hint"), int):
                    with self.lock:
                        found = self.anchorer.code_at(item["path"], item["line_hint"])
                if found:
                    item["existing_code"] = found[0]
                    self.repairs.append(
                        f"{label} existing_code: changed line {item['line_hint']} "
                        f"({found[1]}) taken from line_hint"
                    )
            try:
                valid.append((label, FindingInput.model_validate(item)))
            except ValidationError as exc:
                message = validation_message(exc)
                errors.append(f"{label}: {message}")
                lines.append(f"{label} rejected: invalid arguments: {message}")
        if not valid:
            return self._failed("\n".join(lines), "; ".join(errors), findings)
        text, error, _ = self._report(valid, step)
        lines.append(text)
        if error:
            errors.append(error)
        accepted = any(" recorded at " in line for line in lines)
        message = "\n".join(line for line in lines if line)
        if not accepted:
            return self._failed(message, "; ".join(errors), findings)
        self.report_streak = 0
        return message, ("; ".join(errors) or None), None

    def _failed(self, text: str, error: str, findings):
        """A report_finding call that recorded nothing; repeated failures get a template."""
        self.report_streak += 1
        if self.report_streak >= 2:
            text += "\n" + self._template(findings)
        return text, error, None

    def _template(self, findings) -> str:
        first = next((f for f in findings or [] if isinstance(f, dict)), {})
        code = first.get("existing_code") if isinstance(first.get("existing_code"), str) else ""
        line = next((x for x in snippet_lines(code) if WORDY.search(x)), "") if code else ""
        recent = list(self.evidence)[-1:] or ["<evidence id from a tool result>"]
        example = {
            "findings": [
                {
                    "path": first.get("path") or "<changed file path>",
                    "existing_code": line or "<one line copied from read_diff output>",
                    "title": first.get("title") or "<what is wrong>",
                    "description": "<why it is wrong, its consequence, how to fix>",
                    "category": "defect",
                    "severity": "major",
                    "evidence": recent,
                }
            ]
        }
        return (
            "Several report_finding calls failed. Send one finding per call, shaped like "
            "this (findings and evidence are JSON arrays, not strings; existing_code is one "
            "line copied exactly from a tool result):\n" + json.dumps(example, ensure_ascii=False)
        )

    def _report(self, items: list[tuple[str, FindingInput]], step: int):
        lines, errors = [], []
        for label, item in items:
            try:
                anchor = self._anchor(item.path, item.existing_code, item.line_hint)
            except ReviewCoreError as exc:
                errors.append(f"{label} rejected: {exc}")
                lines.append(f"{label} rejected: {exc}")
                continue
            item, anchor, rejected = self._vet(label, item, anchor)
            if rejected:
                errors.append(f"{label} rejected: {rejected.split(':')[0]}")
                lines.append(f"{label} rejected: {rejected}")
                continue
            known, unknown = self._evidence(item.evidence)
            if not known:
                cited = self._cite(item.path, item.existing_code)
                if cited is None:
                    errors.append(f"{label} rejected: no valid evidence id")
                    lines.append(
                        f"{label} rejected: cite evidence ids shown at the end of tool "
                        f"results (recent: {self._recent_evidence()})."
                    )
                    continue
                known = [cited]
                self.repairs.append(f"{label} evidence: cited {cited} (showing the code)")
            unit = self._unit_of(
                item.path, anchor["side"], anchor["start_line"], anchor["end_line"]
            )
            finding = Finding(
                id=f"F{len(self.findings) + 1}",
                path=item.path,
                title=item.title.strip(),
                description=item.description.strip(),
                category=item.category,
                severity=item.severity,
                condition=item.condition.strip() if item.condition else None,
                evidence=known,
                suggestion=item.suggestion,
                existing_code=item.existing_code,
                about_removal=bool(item.about_removal),
                unit=self.plan.unit_handles.get(unit) if unit else None,
                cluster=self.unit_cluster.get(unit) if unit else None,
                reported_step=step,
                **anchor,
            )
            self.findings.append(finding)
            if item.candidate:
                self._close_candidates([item.candidate], "reported", finding.id)
            where = f"{finding.path}:L{finding.start_line}"
            if finding.end_line != finding.start_line:
                where += f"-{finding.end_line}"
            notes = [finding.side, "in diff" if finding.in_diff else "NOT in the diff"]
            if finding.unit:
                notes.append(finding.unit)
            if finding.cluster and finding.cluster != self.cluster.handle:
                notes.append(f"belongs to {finding.cluster}")
            if unknown:
                notes.append(f"ignored unknown evidence {', '.join(unknown)}")
            if any(r.startswith(f"{label} evidence: cited") for r in self.repairs):
                notes.append(f"evidence {known[0]} cited for you")
            lines.append(f"{finding.id} recorded at {where} ({'; '.join(notes)}).")
        error = "; ".join(errors) if errors else None
        return "\n".join(lines), error, None

    def _clean(self, label: str, field: str, text: str, source: str) -> tuple[str, list[str]]:
        cleaned = checks.cut_field_leak(text)
        if cleaned != text:
            self.repairs.append(f"{label} {field}: cut JSON fields written into the text")
        ids = {candidate["id"] for candidate in self.candidates}
        cleaned, removed = checks.clean_ids(cleaned, ids, source)
        if removed:
            self.repairs.append(f"{label} {field}: removed candidate ids {', '.join(removed)}")
        return cleaned, removed

    def _vet(self, label: str, item: FindingInput, anchor: dict):
        """Rules checked against the code before a finding is recorded: text clean-up,
        removed code, and typo claims. Returns (item, anchor, rejection message or None)."""
        with self.lock:
            head = self.anchorer.text(item.path, "head")
            base = self.anchorer.text(item.path, "base")
        title, removed = self._clean(label, "title", item.title, head)
        description, _ = self._clean(label, "description", item.description, head)
        update: dict = {}
        if title.strip() and title != item.title:
            update["title"] = title
        if description.strip() and description != item.description:
            update["description"] = description
        if removed and not item.candidate and len(set(removed)) == 1:
            update["candidate"] = removed[0]
            self.repairs.append(f"{label} candidate: {removed[0]} taken from the title")
        if update:
            item = item.model_copy(update=update)
        if anchor["side"] == "base":
            with self.lock:
                moved = self.anchorer.in_file(item.path, item.existing_code, "head", item.line_hint)
            if moved:
                anchor = moved
                self.repairs.append(f"{label} anchor: the code is unchanged in the new version")
            elif not item.about_removal:
                return item, anchor, (
                    f"removed code: {item.path}:L{anchor['start_line']} is deleted by this pull "
                    "request (a -L line) and is not in the new version, so a problem in that "
                    "code is already gone. Report problems in the new code (+L or unchanged "
                    "lines). If removing this code is itself the problem (a check, call or case "
                    "that is now missing), report it again with about_removal: true."
                )
        verdict = checks.typo_check(f"{item.title}\n{item.description}", head, base)
        if verdict:
            status, word, other = verdict
            if status == "fixed":
                return item, anchor, (
                    f"already fixed: '{other}' occurs only in the old version of {item.path}; "
                    "this pull request fixes it. Report only problems present in the new code."
                )
            if status == "missing":
                return item, anchor, (
                    f"word not found: '{word}' does not occur in {item.path}; quote the "
                    "misspelled word exactly as it is written in the code."
                )
            if status == "corrected":
                item = item.model_copy(update={
                    "title": checks.replace_word(item.title, word, other),
                    "description": checks.replace_word(item.description, word, other),
                })
                self.repairs.append(f"{label} typo: '{word}' corrected to '{other}' as in the code")
        return item, anchor, None

    def update(self, args: UpdateArgs, step: int):
        finding = next((f for f in self.findings if f.id == args.id.strip()), None)
        if finding is None:
            ids = ", ".join(f.id for f in self.findings) or "none"
            key = args.id.strip()
            if CANDIDATE_ID.fullmatch(key):
                return (
                    f"Error: {key} is a candidate, not a finding; update_finding changes "
                    f"reported findings (reported: {ids}). Dismiss candidates with "
                    f'note_candidates(dismiss=["{key}: reason"]).',
                    "candidate id",
                    None,
                )
            return f"Error: no finding {args.id}; reported: {ids}.", "unknown finding", None
        changes: dict = {"updated_step": step}
        if args.withdraw:
            changes.update(withdrawn=True, withdraw_reason=args.reason)
        for field in ("title", "description", "category", "severity", "condition", "suggestion"):
            value = getattr(args, field)
            if field in ("title", "description") and isinstance(value, str):
                with self.lock:
                    source = self.anchorer.text(finding.path, "head")
                value, _ = self._clean(finding.id, field, value, source)
            if value is not None:
                changes[field] = value.strip() if isinstance(value, str) else value
        if args.evidence is not None:
            known, _ = self._evidence(args.evidence)
            if not known:
                return "Error: no valid evidence id given.", "no valid evidence", None
            changes["evidence"] = known
        if args.existing_code is not None:
            try:
                anchor = self._anchor(finding.path, args.existing_code, None)
            except ReviewCoreError as exc:
                return f"Error: {exc}", str(exc), None
            changes.update(anchor, existing_code=args.existing_code)
        index = self.findings.index(finding)
        self.findings[index] = finding.model_copy(update=changes)
        state = "withdrawn" if args.withdraw else "updated"
        return f"{finding.id} {state}.", None, None
