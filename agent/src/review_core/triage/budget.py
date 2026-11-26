"""Investigation budgets: a guaranteed floor per cluster, a cap, and a shared pool.

Initial allocations follow observable size and seed count only. Extra budget is drawn from
the pool at run time and must cite open, major hypotheses of the requesting cluster; the
investigation layer owns hypotheses and answers that check through a callback.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable

from review_core.common import Record, ReviewCoreError

from .models import TriageConfig, TriagePlan


def initial_budget(diff_tokens: int, seeds: int, config: TriageConfig) -> int:
    wanted = (
        config.floor_tokens
        + round(config.tokens_per_diff_token * diff_tokens)
        + config.seed_bonus_tokens * seeds
    )
    return max(config.floor_tokens, min(config.cap_tokens, wanted))


def pool_size(allocations: Iterable[int], config: TriageConfig) -> int:
    return round(config.pool_ratio * sum(allocations))


class Grant(Record):
    cluster: str
    requested: int
    granted: int
    hypothesis_ids: tuple[str, ...]
    reason: str


class BudgetLedger:
    """Thread-safe pool accounting for one plan; every decision is kept as a Grant."""

    def __init__(self, plan: TriagePlan, is_open_major: Callable[[str, str], bool]):
        self._plan = plan
        self._check = is_open_major
        self._lock = threading.Lock()
        self._pool = plan.pool_tokens
        self._allowance = {cluster.id: cluster.budget_tokens for cluster in plan.clusters}
        self.grants: list[Grant] = []

    @property
    def pool(self) -> int:
        return self._pool

    def allowance(self, cluster: str) -> int:
        return self._allowance[self._plan.cluster(cluster).id]

    def request(self, cluster: str, tokens: int, hypothesis_ids: Iterable[str]) -> Grant:
        if tokens <= 0:
            raise ReviewCoreError("A budget request must ask for a positive token amount")
        key = self._plan.cluster(cluster).id
        cited = tuple(dict.fromkeys(hypothesis_ids))
        with self._lock:
            headroom = self._plan.config.ceiling_tokens - self._allowance[key]
            if not cited:
                granted, reason = 0, "no hypothesis cited"
            elif not all(self._check(key, hypothesis) for hypothesis in cited):
                granted, reason = 0, "cited hypotheses must be open and major in this cluster"
            elif headroom <= 0:
                granted, reason = 0, "cluster reached its ceiling"
            elif self._pool <= 0:
                granted, reason = 0, "shared pool is exhausted"
            else:
                granted = min(tokens, headroom, self._pool)
                reason = "granted" if granted == tokens else "partially granted"
            self._pool -= granted
            self._allowance[key] += granted
            grant = Grant(
                cluster=key,
                requested=tokens,
                granted=granted,
                hypothesis_ids=cited,
                reason=reason,
            )
            self.grants.append(grant)
            return grant
