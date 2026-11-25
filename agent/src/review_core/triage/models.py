from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from review_core.common import Analyzed, Record, ReviewCoreError

# Grouping strength for each kind of structural fact, keyed "kind/confidence".
# Facts come from Code Intel (call, test_reference, import, same_file, rename_candidate)
# or from triage's own cheap derivations (mention, test_pair, same_directory).
DEFAULT_LINK_WEIGHTS = {
    "call/bound": 1.0,
    "call/candidate": 0.6,
    "test_reference/bound": 0.9,
    "test_reference/candidate": 0.6,
    "test_pair/candidate": 0.9,
    "rename_candidate/candidate": 0.7,
    "mention/candidate": 0.6,
    "same_file/candidate": 0.5,
    "import/bound": 0.4,
    "import/candidate": 0.3,
    "same_directory/candidate": 0.2,
}

ExclusionReason = Literal["binary", "lock_file", "generated", "minified", "format_only"]
SeedKind = Literal["dangling_reference", "unchanged_callers"]


class TriageConfig(Record):
    tokenizer: str = "cl100k_base"
    # Clustering: capacity is measured on the changed lines a cluster owns.
    max_cluster_tokens: int = Field(default=6000, ge=256)
    max_cluster_units: int = Field(default=24, ge=1)
    link_weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_LINK_WEIGHTS))
    min_link_weight: float = Field(default=0.2, ge=0)
    # Leftover small clusters are packed with path neighbours up to this size (0 disables),
    # so unlinked one-line changes do not each cost a full investigation floor.
    pack_tokens: int = Field(default=1500, ge=0)
    # Bulk: large data-like changes are reviewed alone, last, on the floor budget.
    max_line_chars: int = Field(default=2000, ge=80)
    bulk_min_chars: int = Field(default=20000, ge=0)
    bulk_long_line_share: float = Field(default=0.5, gt=0, le=1)
    bulk_max_letter_share: float = Field(default=0.2, ge=0, le=1)
    # Seeds: one batched literal search over the head tree.
    min_seed_name_length: int = Field(default=4, ge=1)
    max_seed_symbols: int = Field(default=200, ge=0)
    max_seed_hits_per_symbol: int = Field(default=50, ge=1)
    max_seed_locations: int = Field(default=5, ge=1)
    seed_search_timeout: float = Field(default=30, gt=0)
    # Budget, in investigation tokens. No cluster is ever left without its floor.
    floor_tokens: int = Field(default=6000, ge=0)
    cap_tokens: int = Field(default=30000, ge=0)
    ceiling_tokens: int = Field(default=48000, ge=0)
    tokens_per_diff_token: float = Field(default=3.0, ge=0)
    seed_bonus_tokens: int = Field(default=2000, ge=0)
    pool_ratio: float = Field(default=0.25, ge=0)
    # Change catalog shared by every cluster.
    catalog_tokens: int = Field(default=3000, ge=200)

    @model_validator(mode="after")
    def _ordered_budget(self) -> TriageConfig:
        if not self.floor_tokens <= self.cap_tokens <= self.ceiling_tokens:
            raise ValueError("Budget requires floor_tokens <= cap_tokens <= ceiling_tokens")
        return self


class Exclusion(Record):
    unit_id: str
    path: str
    reason: ExclusionReason
    evidence: str
    line_ids: tuple[str, ...]


class Coverage(Record):
    """Every changed line is either owned by exactly one cluster or excluded with evidence."""

    reviewed_units: int
    reviewed_lines: int
    excluded_lines: int
    exclusions: tuple[Exclusion, ...]


class Link(Record):
    source: str
    target: str
    kind: str
    confidence: Literal["bound", "candidate"]
    weight: float
    basis: str


class Hit(Record):
    path: str
    line: int
    text: str
    in_diff: bool


class Seed(Record):
    """A deterministic, fact-backed starting hypothesis; never a finding by itself."""

    id: str
    kind: SeedKind
    unit_id: str
    symbol: str
    claim: str
    hits: tuple[Hit, ...]
    total_hits: int
    complete: bool


class Cluster(Record):
    id: str
    handle: str
    rank: int
    unit_ids: tuple[str, ...]
    links: tuple[Link, ...]
    diff_tokens: int
    oversized: bool
    # Why the cluster holds bulk changes; bulk clusters are never merged with others.
    bulk: str | None = None
    seed_ids: tuple[str, ...]
    priority: int
    priority_reasons: tuple[str, ...]
    budget_tokens: int


class TriagePlan(Analyzed):
    """limits/gaps/issues summarize the analysis behind the plan (gaps capped, see gap_counts)."""

    id: str
    snapshot_id: str
    config: TriageConfig
    unit_handles: dict[str, str]
    clusters: tuple[Cluster, ...]
    seeds: tuple[Seed, ...]
    coverage: Coverage
    catalog: str
    catalog_detail: Literal["unit", "file"]
    pool_tokens: int
    total_tokens: int
    gap_counts: dict[str, int] = Field(default_factory=dict)

    def cluster(self, key: str) -> Cluster:
        for cluster in self.clusters:
            if key in {cluster.id, cluster.handle}:
                return cluster
        raise ReviewCoreError(f"Unknown cluster: {key}")
