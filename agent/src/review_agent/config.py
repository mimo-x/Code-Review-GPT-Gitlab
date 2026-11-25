"""ReviewConfig: the settings of one review, grouped by stage (triage -> investigate ->
postprocess), on top of the preset of its tier (see tiers). Unknown fields are errors, so
stale or misspelled settings cannot be silently ignored. How many model requests run at
once is not a review setting: the caller bounds it with a GatedPolicy (see policy)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from review_core.triage import TriageConfig

from .agent import LoopConfig
from .aggregate import AggregateConfig
from .postfilter import PostFilterConfig
from .tiers import DEFAULT_TIER, expand

STRICT = ConfigDict(extra="forbid")


class BudgetConfig(BaseModel):
    """Case budget of the investigation, in model input + output tokens of all its
    investigator episodes (see budget). split: divided among the clusters by
    budget.allocate; pool: one pool all episodes draw from, floor_tokens and the weights
    unused (no reserve: a cluster may find the pool spent). case_tokens None: unmetered,
    episodes are bounded by max_steps and the context window only."""

    model_config = STRICT

    case_tokens: int | None = Field(default=None, ge=1)
    sharing: Literal["split", "pool"] = "split"
    # the minimal investigation every cluster gets, even beyond the case budget
    floor_tokens: int = Field(default=40000, ge=0)
    # Weight of a cluster's share of triage's budget, by rank 1, 2, ...; the last entry
    # applies to every later rank. Default from dev (cases with >= 3 clusters): reference
    # issues / triage budget share is 54/35 for rank 1, 39/46 for ranks 2-3, 7/19 for 4+.
    rank_weights: list[Annotated[float, Field(ge=0)]] = Field(
        default_factory=lambda: [1.5, 0.85, 0.85, 0.4], min_length=1
    )
    # weight of a priority-0 cluster (triage found no seed hypothesis, non-private signature
    # change, deletion or source behaviour change) in place of its rank weight; None: by rank
    priority_zero_weight: float | None = Field(default=None, ge=0)

    def weight(self, cluster) -> float:
        if cluster.priority == 0 and self.priority_zero_weight is not None:
            return self.priority_zero_weight
        return self.rank_weights[min(cluster.rank, len(self.rank_weights)) - 1]


class ExamplesConfig(BaseModel):
    """Example library shown with the first diff: path to cards.jsonl, and "retrieved" or
    "random" (the control). path None: no examples."""

    model_config = STRICT

    path: str | None = None
    mode: str = "retrieved"


class IdeationConfig(BaseModel):
    """Independent candidate-listing passes per assignment, merged before the
    investigation. samples 0: none."""

    model_config = STRICT

    samples: int = Field(default=0, ge=0)
    steps: int = Field(default=6, ge=2)


class InvestigateConfig(BaseModel):
    model_config = STRICT

    # the investigator prompt variant (prompts.VARIANTS); the tools are the same
    prompt: Literal["standard", "low"] = "standard"
    # coverage: every concern a careful reviewer would raise; merge_blocking: only problems
    # that should be fixed before merging (prompts.MERGE_BLOCKING)
    reporting: Literal["coverage", "merge_blocking"] = "coverage"
    loop: LoopConfig = Field(default_factory=LoopConfig)
    tool_output_tokens: int = Field(default=6000, ge=256)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    # every unit needs a candidate, a finding or a "reviewed" mark before finish
    coverage: bool = False
    examples: ExamplesConfig = Field(default_factory=ExamplesConfig)
    ideation: IdeationConfig = Field(default_factory=IdeationConfig)


class FinalReviewConfig(BaseModel):
    """One model call over every comment left after the post-filter: keeps at most
    max_comments, most important first, settles their severity and folds repeats of one
    mistake into a single comment (see final)."""

    model_config = STRICT

    max_comments: int = Field(ge=1)
    temperature: float | None = None
    max_output_tokens: int | None = None


class PostprocessConfig(BaseModel):
    model_config = STRICT

    aggregate: AggregateConfig = Field(default_factory=AggregateConfig)
    # filter over the aggregated comments (see postfilter); on by default, null: off
    postfilter: PostFilterConfig | None = Field(default_factory=PostFilterConfig)
    # the final review after the filter (see final); null: off
    final_review: FinalReviewConfig | None = None


class ReviewConfig(BaseModel):
    model_config = STRICT

    # the preset under the explicit fields, expanded at validation (see tiers)
    tier: str = DEFAULT_TIER
    # the language findings are written in (prompts.LANGUAGES)
    language: Literal["en", "zh-CN"] = "en"
    triage: TriageConfig | None = None
    investigate: InvestigateConfig = Field(default_factory=InvestigateConfig)
    postprocess: PostprocessConfig = Field(default_factory=PostprocessConfig)

    @model_validator(mode="before")
    @classmethod
    def _expand_tier(cls, data):
        return expand(data) if isinstance(data, dict) else data
