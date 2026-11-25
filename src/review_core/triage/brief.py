"""The model-facing assignment for one cluster: what to review, how it relates, where to
start, and the whole change around it. Text only; the plan itself stays the record.

By default the budget is shown as a plain value; an agent runtime that meters it passes
its own budget_line (for example "Budget: 40000 tokens of model input and output").
"""

from __future__ import annotations

from review_core.intel.models import ChangeUnit

from .models import TriagePlan

RELATION_WORDS = {
    "call": "calls",
    "test_reference": "is tested by",
    "test_pair": "is the test pair of",
    "mention": "mentions",
    "import": "imports",
    "rename_candidate": "may be renamed to",
}
# Locality links only say "nearby"; listing them would read as a relationship.
SILENT_LINKS = {"same_file", "same_directory", "locality"}
MAX_HITS = 3


def render(
    plan: TriagePlan,
    cluster_key: str,
    units: dict[str, ChangeUnit],
    budget_line: str | None = None,
    *,
    show_budget: bool = True,
) -> str:
    cluster = plan.cluster(cluster_key)
    handle = plan.unit_handles
    out = [
        f"Assignment {cluster.handle} (rank {cluster.rank} of {len(plan.clusters)}): "
        f"review {len(cluster.unit_ids)} changed unit{'s' if len(cluster.unit_ids) != 1 else ''}."
    ]
    if show_budget:
        out.append(
            budget_line
            or f"Budget value: {cluster.budget_tokens}. More can be requested from the shared "
            "pool by citing an open major hypothesis of this assignment."
        )
    if cluster.priority_reasons:
        out.append("Why it ranks here: " + "; ".join(cluster.priority_reasons) + ".")
    if cluster.bulk:
        out.append(f"Bulk material ({cluster.bulk}): read it folded, skim for what matters.")
    out += ["", "Units:"]
    for key in cluster.unit_ids:
        out.append(f"  {handle[key]} {_describe(units[key])}")
    related = [link for link in cluster.links if link.kind not in SILENT_LINKS]
    if related:
        out += ["", "How they relate (bound = proven binding, candidate = name match):"]
        for link in related:
            words = RELATION_WORDS.get(link.kind, link.kind)
            out.append(f"  {handle[link.source]} {words} {handle[link.target]} ({link.confidence})")
    seeds = {seed.id: seed for seed in plan.seeds}
    if cluster.seed_ids:
        out += ["", "Starting hypotheses (facts found by rules; verify before reporting):"]
        for seed_id in cluster.seed_ids:
            seed = seeds[seed_id]
            out.append(f"  - {handle[seed.unit_id]}: {seed.claim}")
            for hit in seed.hits[:MAX_HITS]:
                out.append(f"      {hit.path}:{hit.line} {hit.text}")
            if seed.total_hits > MAX_HITS:
                out.append(
                    f"      ... {seed.total_hits - MAX_HITS} more, find them with code_search"
                )
    if not plan.complete:
        out += ["", _coverage(plan)]
    out += ["", plan.catalog.rstrip()]
    return "\n".join(out)


def _describe(unit: ChangeUnit) -> str:
    symbol = unit.head_symbol or unit.base_symbol
    name = symbol.qualified_name if symbol else "<outside any symbol>"
    added = [line.new_line for line in unit.lines if line.kind == "add"]
    deleted = [line.old_line for line in unit.lines if line.kind == "delete"]
    # Same notation as read_diff: + head lines, - base lines.
    spans = [
        f"{sign}L{min(numbers)}" + (f"-{max(numbers)}" if max(numbers) != min(numbers) else "")
        for sign, numbers in (("+", added), ("-", deleted))
        if numbers
    ]
    path = unit.new_path or unit.old_path
    where = " ".join(spans) or "metadata only"
    return f"{path} {name} [{', '.join(unit.kinds)}] {where} (+{len(added)} -{len(deleted)})"


def _coverage(plan: TriagePlan) -> str:
    parts = []
    if plan.gap_counts:
        parts.append(
            "analysis gaps: " + ", ".join(f"{k} {v}" for k, v in sorted(plan.gap_counts.items()))
        )
    if plan.limits:
        parts.append("stopped by: " + "; ".join(plan.limits))
    return (
        "Analysis is partial ("
        + "; ".join(parts or ["see plan issues"])
        + "); relations may be missing."
    )
