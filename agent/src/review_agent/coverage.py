"""Coverage check (off by default: ReviewConfig investigate.coverage): every unit of the
assignment needs a candidate, a finding or a "reviewed" mark before finish is accepted. On,
the note_candidates tool gains a reviewed field and progress notes list the uncovered
units."""

from __future__ import annotations

import re

from pydantic import Field

from .agent_tools import CandidatesArgs


class CoverageCandidatesArgs(CandidatesArgs):
    reviewed: list[str] = Field(
        default_factory=list,
        description="unit handles (U#) you reviewed and found nothing worth noting",
    )


class CoverageCheck:
    def __init__(self, handles: list[str]):
        self.handles = handles  # the assignment's unit handles, in order
        self.reviewed: set[str] = set()
        self.warned = False

    def tools(self, agent_tools: dict) -> dict:
        tools = dict(agent_tools)
        tools["note_candidates"] = (
            CoverageCandidatesArgs,
            agent_tools["note_candidates"][1]
            + " Mark units you reviewed and found nothing worth noting in reviewed.",
        )
        return tools

    def mark_reviewed(self, entries: list[str]) -> None:
        for entry in entries:
            self.reviewed.update(
                h for h in re.findall(r"\bU\d+\b", str(entry)) if h in self.handles
            )

    def uncovered(self, candidates: list[dict], findings) -> list[str]:
        noted = {c["unit"] for c in candidates if c["unit"]}
        found = {f.unit for f in findings if f.unit and not f.withdrawn}
        return [h for h in self.handles if h not in noted | found | self.reviewed]

    def line(self, candidates: list[dict], findings) -> str:
        missing = self.uncovered(candidates, findings)
        if not missing:
            return "Coverage: every unit has a candidate, a finding or a reviewed mark."
        return ("Units with no candidate, finding or reviewed mark: " + ", ".join(missing)
                + " (note a candidate for each, or mark it reviewed).")

    def refuse_finish(self, candidates: list[dict], findings) -> str | None:
        """The message refusing the first finish that leaves units uncovered, else None."""
        missing = self.uncovered(candidates, findings)
        if not missing or self.warned:
            return None
        self.warned = True
        return (
            f"Not finished: units {', '.join(missing)} have no candidate, finding or "
            "reviewed mark. Read their diff and note candidates for them, or mark them "
            "reviewed with note_candidates(reviewed=[...]), then call finish again."
        )
