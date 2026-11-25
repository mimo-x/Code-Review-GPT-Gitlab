"""Every version string the review agent records, in one place.

Bump the matching version on any change to what it covers: episodes and case records
carry them, so runs and trajectories stay comparable.
"""

from __future__ import annotations

from review_core.intel.tools import TOOLS_VERSION

# the case record (orchestrator.CaseReview)
REVIEW_VERSION = "review-v1"
# investigator prompt text (prompts.SYSTEM), and the low tier's variant (SYSTEM_LOW)
PROMPT_VERSION = "investigator-v5"
LOW_PROMPT_VERSION = "investigator-low-v1"
# the merge-blocking passages swapped into either variant (prompts.MERGE_BLOCKING)
MERGE_BLOCKING_VERSION = "merge-blocking-v1"
# the final review over the post-processed comments (final)
FINAL_REVIEW_VERSION = "final-review-v1"
# budget reminders, the wrap-up without code tools (prompts.budget_low/budget_final, env)
# and when they come (budget: split or pool sharing); shown only in metered episodes
BUDGET_PROMPT_VERSION = "budget-v2"
# the intel tools plus the agent's own tools (env), and how calls are normalized (normalize)
AGENT_TOOLS_VERSION = f"{TOOLS_VERSION}+investigator-v7"
# ideation prompt text (prompts.IDEATION_SYSTEM) and its listing tools (ideation, normalize)
IDEATION_PROMPT_VERSION = "ideation-v1"
IDEATION_TOOLS_VERSION = f"{TOOLS_VERSION}+ideation-v3"
# post-filter prompts and tools; also part of the post-filter's episode ids (postfilter)
FILTER_PROMPT_VERSION = "postfilter-v1"
# context management of the loop: masking, call stubs, progress notes (context)
CONTEXT_VERSION = "context-v2"
# the Episode record format (trajectory)
SCHEMA_VERSION = "episode-v2"


def recorded() -> dict[str, str]:
    return {
        "review": REVIEW_VERSION,
        "prompt": PROMPT_VERSION,
        "low_prompt": LOW_PROMPT_VERSION,
        "merge_blocking": MERGE_BLOCKING_VERSION,
        "final_review": FINAL_REVIEW_VERSION,
        "budget_prompt": BUDGET_PROMPT_VERSION,
        "intel_tools": TOOLS_VERSION,
        "agent_tools": AGENT_TOOLS_VERSION,
        "ideation_prompt": IDEATION_PROMPT_VERSION,
        "ideation_tools": IDEATION_TOOLS_VERSION,
        "filter_prompt": FILTER_PROMPT_VERSION,
        "context": CONTEXT_VERSION,
        "episode_schema": SCHEMA_VERSION,
    }
