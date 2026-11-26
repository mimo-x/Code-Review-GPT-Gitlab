"""Review tiers: named presets of ReviewConfig values, cheapest first.

A config names its tier ("high" unless it says otherwise). The preset is expanded when the
config is validated, and every field the config sets explicitly overrides it (an explicit
null too), so a validated config is complete: storing its dump stores the tier and every
value in effect, and validating that dump again gives the same config.

A preset is a partial ReviewConfig written as plain data; adding a tier is adding an entry.
"""

from __future__ import annotations

import copy

from pydantic import BaseModel

DEFAULT_TIER = "high"

TIERS: dict[str, dict] = {
    # A quick review of the most important problems: its own prompt, smaller tool
    # outputs, at most 20 turns, and a 600k case budget split towards the top-ranked
    # clusters (rank 4+ and priority-0 clusters get the floor only).
    # Post-filter on; examples, candidate sampling and the coverage check off.
    "low": {
        "investigate": {
            "prompt": "low",
            "loop": {"max_steps": 20, "milestones": [5, 2, 1]},
            "tool_output_tokens": 3000,
            "budget": {
                "case_tokens": 600_000,
                "rank_weights": [1.5, 0.85, 0.85, 0.0],
                "priority_zero_weight": 0.0,
            },
            "coverage": False,
            "examples": {"path": None},
            "ideation": {"samples": 0},
            "reporting": "merge_blocking",
        },
        "postprocess": {
            "postfilter": {"rules": True, "merge": True},
            "final_review": {"max_comments": 10},
        },
    },
    # The default review. The case budget is a safety cap, shared as a pool: replayed on
    # three uncapped dev runs (330 case runs), a 5M pool cuts 8 cases and ~4% of findings;
    # split by triage's shares, 3M cut 91 cases (a pool at 3M: 41). An explicit null runs
    # high uncapped.
    # Comments go straight to the author: the low and high tiers report only problems that
    # should be fixed before merging, and a final review keeps the most important ones.
    "high": {
        "investigate": {
            "budget": {"case_tokens": 5_000_000, "sharing": "pool"},
            "reporting": "merge_blocking",
        },
        "postprocess": {"final_review": {"max_comments": 20}},
    },
    # high's budget with three candidate-listing passes per assignment before the
    # investigation (ideation), reporting every concern; the final review keeps 30.
    "xhigh": {
        "investigate": {
            "budget": {"case_tokens": 5_000_000, "sharing": "pool"},
            "ideation": {"samples": 3, "steps": 6},
        },
        "postprocess": {"final_review": {"max_comments": 30}},
    },
}


def expand(data: dict) -> dict:
    """The config data with its tier's preset under it."""
    tier = data.get("tier", DEFAULT_TIER)
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r}; tiers: {', '.join(TIERS)}")
    return {**overlay(copy.deepcopy(TIERS[tier]), data), "tier": tier}


def overlay(base: dict, explicit: dict) -> dict:
    """base with explicit on top, merged field by field into nested settings. A model
    instance counts with only the fields that were set on it."""
    out = dict(base)
    for key, value in explicit.items():
        if isinstance(value, BaseModel):
            value = value.model_dump(exclude_unset=True)
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = overlay(out[key], value)
        else:
            out[key] = value
    return out
