"""Triage: a deterministic, LLM-free plan that splits a change into review assignments.

Pipeline: hard-evidence filter -> weighted links -> capacity-bounded clustering ->
fact seeds -> priority order -> budgets -> change catalog. Nothing is ever deferred.
"""

from __future__ import annotations

from collections import Counter

from review_core.common import ReviewCoreError, stable_id, unique
from review_core.intel import CodeIntel
from review_core.tokens import TokenCounter

from . import catalog
from .budget import initial_budget, pool_size
from .bulk import bulk_reason
from .clustering import cluster_units, diff_tokens
from .filter import exclusion
from .links import links
from .models import Cluster, Coverage, TriageConfig, TriagePlan
from .ordering import priority
from .seeds import find_seeds

STORE = "triage-plans-v1"
MAX_ISSUES = 20


class Triage:
    def __init__(self, intel: CodeIntel, config: TriageConfig | None = None):
        self.intel = intel
        self.config = config or TriageConfig()

    def plan(self) -> TriagePlan:
        config = self.config
        workspace = self.intel.workspace
        counter = TokenCounter(config.tokenizer)
        graph = self.intel.change_graph()
        changes = {change.id: change for change in workspace.snapshot.changes}

        exclusions, reviewed = [], []
        for unit in graph.units:
            found = exclusion(self.intel, unit, changes[unit.file_change_id])
            (exclusions if found else reviewed).append(found or unit)
        reviewed = tuple(reviewed)
        by_id = {unit.id: unit for unit in graph.units}

        sizes = {unit.id: diff_tokens(unit, counter) for unit in reviewed}
        bulk = {unit.id: reason for unit in reviewed if (reason := bulk_reason(unit, config))}
        linked = tuple(unit for unit in reviewed if unit.id not in bulk)
        grouped = cluster_units(linked, links(graph, linked, config), sizes, config)
        bulk_files = {}
        for unit in reviewed:
            if unit.id in bulk:
                bulk_files.setdefault(unit.file_change_id, []).append(unit.id)
        grouped += [(tuple(sorted(ids)), ()) for _, ids in sorted(bulk_files.items())]
        seeds, seed_shortfalls = find_seeds(workspace, reviewed, config)
        seeds_by_unit = {}
        for seed in seeds:
            seeds_by_unit.setdefault(seed.unit_id, []).append(seed)

        drafts = []
        for members, internal in grouped:
            units = sorted((by_id[key] for key in members), key=_unit_order)
            owned = [seed for unit in units for seed in seeds_by_unit.get(unit.id, [])]
            score, reasons = priority(units, owned)
            size = sum(sizes[unit.id] for unit in units)
            note = "; ".join(dict.fromkeys(bulk[unit.id] for unit in units if unit.id in bulk))
            drafts.append((score, size, units, internal, owned, reasons, note or None))
        drafts.sort(
            key=lambda draft: (
                draft[6] is not None,
                -draft[0],
                -draft[1],
                _unit_order(draft[2][0]),
            )
        )

        handles = {}
        for _, _, units, *_ in drafts:
            for unit in units:
                handles[unit.id] = f"U{len(handles) + 1}"
        excluded_units = sorted((by_id[item.unit_id] for item in exclusions), key=_unit_order)
        for unit in excluded_units:
            handles[unit.id] = f"U{len(handles) + 1}"

        clusters = []
        for rank, (score, size, units, internal, owned, reasons, note) in enumerate(drafts, 1):
            unit_ids = tuple(unit.id for unit in units)
            clusters.append(
                Cluster(
                    id=stable_id(["cluster-v2", sorted(unit_ids)]),
                    handle=f"C{rank}",
                    rank=rank,
                    unit_ids=unit_ids,
                    links=internal,
                    diff_tokens=size,
                    oversized=size > config.max_cluster_tokens,
                    bulk=note,
                    seed_ids=tuple(seed.id for seed in owned),
                    priority=score,
                    priority_reasons=reasons,
                    # Bulk material is skimmed through folded views, not read in full.
                    budget_tokens=config.floor_tokens
                    if note
                    else initial_budget(size, len(owned), config),
                )
            )
        reasons_by_unit = {item.unit_id: item.reason for item in exclusions}
        text, detail = catalog.render(
            [
                (
                    f"{cluster.handle} (bulk)" if cluster.bulk else cluster.handle,
                    [by_id[key] for key in cluster.unit_ids],
                )
                for cluster in clusters
            ],
            handles,
            [(unit, reasons_by_unit[unit.id]) for unit in excluded_units],
            counter,
            config.catalog_tokens,
        )
        coverage = Coverage(
            reviewed_units=len(reviewed),
            reviewed_lines=sum(len(unit.lines) for unit in reviewed),
            excluded_lines=sum(len(item.line_ids) for item in exclusions),
            exclusions=tuple(sorted(exclusions, key=lambda item: (item.path, item.unit_id))),
        )
        _check_coverage(graph.units, clusters, coverage)
        pool = pool_size((cluster.budget_tokens for cluster in clusters), config)
        body = dict(
            snapshot_id=workspace.snapshot.id,
            config=config,
            unit_handles=handles,
            clusters=tuple(clusters),
            seeds=seeds,
            coverage=coverage,
            catalog=text,
            catalog_detail=detail,
            pool_tokens=pool,
            total_tokens=pool + sum(cluster.budget_tokens for cluster in clusters),
            limits=unique([*graph.limits, *seed_shortfalls.limits]),
            gaps=_capped([*graph.gaps, *seed_shortfalls.gaps]),
            gap_counts=dict(sorted(Counter(gap.kind for gap in graph.gaps).items())),
            issues=_capped([*graph.issues, *seed_shortfalls.issues]),
        )
        plan_id = stable_id(["triage-plan-v1", {key: _dump(value) for key, value in body.items()}])
        plan = TriagePlan(id=plan_id, **body)
        workspace.store.put(STORE, plan.id, plan.model_dump(mode="json"))
        return plan

    def brief(self, plan: TriagePlan, cluster: str, budget_line: str | None = None) -> str:
        """The model-facing assignment text for one cluster of a plan."""
        from .brief import render

        units = {unit.id: unit for unit in self.intel.changed_symbols()}
        return render(plan, cluster, units, budget_line)

    def load(self, plan_id: str) -> TriagePlan:
        payload = self.intel.workspace.store.get(STORE, plan_id)
        if payload is None:
            raise ReviewCoreError("Triage plan not found")
        plan = TriagePlan.model_validate(payload)
        if plan.snapshot_id != self.intel.workspace.snapshot.id:
            raise ReviewCoreError("Triage plan belongs to a different snapshot")
        return plan


def _unit_order(unit) -> tuple:
    lines = [line.new_line or line.old_line or 0 for line in unit.lines]
    return (unit.new_path or unit.old_path or "", min(lines, default=0), unit.id)


def _check_coverage(units, clusters, coverage) -> None:
    """Core invariant: each change unit is reviewed by one cluster or excluded, never both."""
    owners = Counter(unit for cluster in clusters for unit in cluster.unit_ids)
    owners.update(item.unit_id for item in coverage.exclusions)
    if owners != Counter(unit.id for unit in units):
        raise RuntimeError("Triage lost, duplicated or invented change units")


def _capped(values) -> tuple:
    """At most MAX_ISSUES distinct entries; gap_counts keeps the totals."""
    return unique(values)[:MAX_ISSUES]


def _dump(value):
    if isinstance(value, tuple):
        return [_dump(item) for item in value]
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value
