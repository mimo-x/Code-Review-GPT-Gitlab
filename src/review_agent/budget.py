"""Token budgets of the investigation (ReviewConfig investigate.budget).

A case budget counts the model input plus output tokens of every investigator episode of a
case; triage, candidate listing and the post-filter are not counted. It is shared in one of
two ways (BudgetConfig.sharing):

- split: allocate splits it among the clusters before the episodes start, and each
  episode's BudgetMeter enforces its share.
- pool: every episode draws from one CasePool of the whole budget (a PoolMeter each); no
  share is reserved, so the episodes that need it most can use the most.

Either way an episode is told to stop exploring once WARN_AT of its budget is used or it
pays for fewer than WARN_TURNS more turns, and given its wrap-up turns, in which no code is
read, when the next turn would pass the limit (see agent.run_episode). An episode can pass
its budget by those wrap-up turns. Unmetered episodes (budget None) show and enforce
nothing.
"""

from __future__ import annotations

import threading
from typing import Literal

from .policy import Usage

# an episode is told to stop exploring after this share of its budget, or earlier when
# what is left pays for fewer turns than WARN_TURNS (a turn costs more as context grows)
WARN_AT = 0.8
WARN_TURNS = 3


def allocate(plan, config) -> dict[str, int | None]:
    """Episode budget by cluster handle, from a BudgetConfig. Every cluster gets
    floor_tokens; the rest of the case budget is split in proportion to triage's budget for
    the cluster times its weight (BudgetConfig.weight). When the floors alone exceed the
    case budget, every cluster still gets its floor. Unmetered or pool sharing: None."""
    clusters = plan.clusters
    if config.case_tokens is None or config.sharing == "pool":
        return dict.fromkeys((cluster.handle for cluster in clusters), None)
    rest = max(0, config.case_tokens - config.floor_tokens * len(clusters))
    shares = {cluster.handle: cluster.budget_tokens * config.weight(cluster) for cluster in clusters}
    if not sum(shares.values()):  # every weight is 0: by triage's budgets alone, else evenly
        shares = {cluster.handle: cluster.budget_tokens or 1 for cluster in clusters}
    total = sum(shares.values())
    return {handle: config.floor_tokens + int(rest * share / total) for handle, share in shares.items()}


class BudgetMeter:
    def __init__(self, limit: int | None):
        self.limit = limit
        self.used = Usage()
        self.last = 0  # tokens of the last charged turn: the estimate of the next one

    def charge(self, usage: Usage) -> None:
        self.used = self.used + usage
        self.last = usage.total

    @property
    def left(self) -> int:
        return max(0, self.limit - self.used.total) if self.limit is not None else 0

    def state(self) -> Literal["ok", "low", "out"]:
        """out: the next turn, estimated as the last one, would pass the limit; low: WARN_AT
        of the budget is used, or it pays for fewer than WARN_TURNS turns; ok otherwise,
        and always when unmetered."""
        if self.limit is None:
            return "ok"
        used = self.used.total
        if used + self.last >= self.limit:
            return "out"
        low = used >= WARN_AT * self.limit or used + WARN_TURNS * self.last >= self.limit
        return "low" if low else "ok"

    def turns_left(self) -> int:
        """Turns the budget left pays for, at the cost of the last turn."""
        return self.left // max(1, self.last)

    def detail(self) -> dict:
        """What the last state() was decided on, for the episode's events (see PoolMeter)."""
        return {}


class CasePool:
    """The budget of a case shared by all its episodes, which run in threads. used counts
    every charged turn, including those of finished episodes (precharge: episodes loaded
    on resume); running holds the last turn's tokens of every running episode."""

    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0
        self.running: dict[str, int] = {}
        self._lock = threading.Lock()

    @classmethod
    def of(cls, config) -> CasePool | None:
        """The pool of a BudgetConfig; None unless it shares a case budget as a pool."""
        if config.case_tokens is None or config.sharing != "pool":
            return None
        return cls(config.case_tokens)

    def precharge(self, tokens: int) -> None:
        with self._lock:
            self.used += tokens

    def meter(self, key: str) -> PoolMeter:
        """The meter of a starting episode, which runs until leave(key)."""
        with self._lock:
            self.running[key] = 0
        return PoolMeter(self, key)

    def leave(self, key: str) -> None:
        with self._lock:
            self.running.pop(key, None)

    def charge(self, key: str, tokens: int) -> None:
        with self._lock:
            self.used += tokens
            self.running[key] = tokens

    def snapshot(self) -> dict:
        # round: the next turn of every running episode, estimated as its last
        with self._lock:
            return {"limit": self.limit, "used": self.used, "running": len(self.running),
                    "round": sum(self.running.values())}


class PoolMeter(BudgetMeter):
    """An episode's view of the CasePool: it charges its own usage and the pool's. out:
    the pool cannot pay for this episode's next turn; low: WARN_AT of the pool is used, or
    it pays for fewer than WARN_TURNS turns of all running episodes. What is left for the
    episode (left, turns_left) is the pool's remainder split evenly among them."""

    def __init__(self, pool: CasePool, key: str):
        super().__init__(pool.limit)
        self.pool, self.key = pool, key
        self.seen = pool.snapshot()

    def charge(self, usage: Usage) -> None:
        super().charge(usage)
        self.pool.charge(self.key, usage.total)

    @property
    def left(self) -> int:
        return max(0, self.limit - self.seen["used"]) // max(1, self.seen["running"])

    def state(self) -> Literal["ok", "low", "out"]:
        self.seen = self.pool.snapshot()
        used = self.seen["used"]
        if used + self.last >= self.limit:
            return "out"
        low = used >= WARN_AT * self.limit or used + WARN_TURNS * self.seen["round"] >= self.limit
        return "low" if low else "ok"

    def detail(self) -> dict:
        return {"pool": {**self.seen, "episode_used": self.used.total}}
