"""Candidate sampling: short independent passes that only list candidate concerns.

Which concerns a small model thinks of varies a lot between runs, while the investigation
of a given concern is comparatively stable. So the orchestrator can run a few cheap
listing passes per assignment, merge their candidates, and start one investigation with
the merged list (InvestigateEnv seed_candidates).
"""

from __future__ import annotations

import re

from review_core.intel.tools import SPECS

from . import prompts
from .agent_tools import AGENT_TOOLS
from .env import InvestigateEnv
from .schemas import tool_schema
from .versions import IDEATION_PROMPT_VERSION, IDEATION_TOOLS_VERSION

LISTING_TOOLS = ("read_diff", "read_file", "read_symbol", "list_changes", "outline")
WORD = re.compile(r"[a-z0-9_]+")


class IdeationEnv(InvestigateEnv):
    role = "ideation"
    prompt_version = IDEATION_PROMPT_VERSION
    tools_version = IDEATION_TOOLS_VERSION

    def tool_schemas(self) -> list[dict]:
        core = [tool_schema(n, SPECS[n][0], SPECS[n][3]) for n in LISTING_TOOLS if n in SPECS]
        model, description = AGENT_TOOLS["note_candidates"]
        return core + [tool_schema("note_candidates", model, description)]

    def reset(self):
        self.reset_state()
        with self.lock:
            brief = self.intel_brief()
        first = (f'{brief}\n\nRead the diff with read_diff(cluster="{self.cluster.handle}"), '
                 "then call note_candidates with your candidate concerns.")
        return [{"role": "system", "content": prompts.IDEATION_SYSTEM},
                {"role": "user", "content": first}], {"task": self.task}

    def _dispatch(self, name: str, arguments: dict):
        if name in SPECS and name not in LISTING_TOOLS:
            return (f"Error: {name} is not available in this listing pass; call "
                    "note_candidates.", "unavailable tool", None)
        if name not in SPECS and name != "note_candidates":
            return "Error: only reading tools and note_candidates are available.", "unknown tool", None
        text, error, evidence = super()._dispatch(name, arguments)
        if name == "note_candidates" and self.candidates:
            self.done = True
            self.summary = {"candidates": self.candidates}
            text = "Candidates recorded. This pass is complete."
        return text, error, evidence


def _words(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


def merge(samples: list[list[dict]], limit: int = 40, similarity: float = 0.6) -> list[dict]:
    """Union of candidate lists; a candidate on the same unit whose words overlap an earlier
    one by `similarity` (Jaccard) is a repeat. Concerns found by several passes and higher
    priorities come first."""
    rank = {"high": 0, "medium": 1, "low": 2}
    merged: list[dict] = []
    for sample in samples:
        for candidate in sample:
            words = _words(candidate["concern"])
            for kept in merged:
                if kept.get("unit") != candidate.get("unit"):
                    continue
                union = words | kept["_words"]
                if union and len(words & kept["_words"]) / len(union) >= similarity:
                    kept["_votes"] += 1
                    if rank[candidate["priority"]] < rank[kept["priority"]]:
                        kept["priority"] = candidate["priority"]
                    break
            else:
                merged.append({"concern": candidate["concern"], "unit": candidate.get("unit"),
                               "priority": candidate["priority"], "_words": words, "_votes": 1})
    merged.sort(key=lambda c: (-c["_votes"], rank[c["priority"]]))
    return [{k: v for k, v in c.items() if not k.startswith("_")} | {"votes": c["_votes"]}
            for c in merged[:limit]]
