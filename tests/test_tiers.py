from __future__ import annotations

import pytest
from pydantic import ValidationError

from review_agent import tiers
from review_agent.budget import allocate
from review_agent.config import BudgetConfig, InvestigateConfig, PostprocessConfig, ReviewConfig


def test_high_is_the_default_tier_and_the_expanded_config_round_trips():
    config = ReviewConfig()
    assert config.tier == "high" and ReviewConfig.model_validate({}) == config
    budget = config.investigate.budget
    assert (budget.case_tokens, budget.sharing) == (5_000_000, "pool")
    # uncapped high is the review before tiers: every other value is the field default, but
    # for the sharing of a budget it has not
    uncapped = ReviewConfig.model_validate({"investigate": {"budget": {"case_tokens": None}}})
    investigate = InvestigateConfig(budget=BudgetConfig(sharing="pool"), reporting="merge_blocking")
    assert uncapped.model_dump(exclude={"tier"}) == {
        "triage": None, "language": "en", "investigate": investigate.model_dump(),
        "postprocess": PostprocessConfig(final_review={"max_comments": 20}).model_dump()}
    dumped = config.model_dump(mode="json")
    assert dumped["tier"] == "high"
    assert ReviewConfig.model_validate(dumped) == config
    with pytest.raises(ValidationError, match="unknown tier"):
        ReviewConfig.model_validate({"tier": "ultra"})


def test_explicit_fields_override_the_preset_field_by_field(monkeypatch):
    preset = {"investigate": {"tool_output_tokens": 1000, "coverage": True,
                              "loop": {"max_steps": 9, "temperature": 0.3}},
              "postprocess": {"postfilter": None}}
    monkeypatch.setitem(tiers.TIERS, "probe", preset)
    config = ReviewConfig.model_validate({
        "tier": "probe",
        "investigate": {"coverage": False, "loop": {"temperature": None}},
        "postprocess": {"postfilter": {}},
    })
    loop = config.investigate.loop
    assert (config.investigate.tool_output_tokens, loop.max_steps) == (1000, 9)
    assert config.investigate.coverage is False and loop.temperature is None
    assert config.postprocess.postfilter is not None
    assert preset["investigate"]["coverage"] is True  # the preset itself is untouched
    # the dump is complete: it validates to the same config, preset or not
    dumped = config.model_dump(mode="json")
    assert ReviewConfig.model_validate(dumped) == config
    # model instances count with the fields set on them only
    built = ReviewConfig(tier="probe", investigate=InvestigateConfig(coverage=False))
    assert built.investigate.tool_output_tokens == 1000 and not built.investigate.coverage


class Cluster:
    def __init__(self, rank, budget, priority=1):
        self.handle, self.rank, self.budget_tokens, self.priority = f"C{rank}", rank, budget, priority


class Plan:
    def __init__(self, *clusters):
        self.clusters = clusters


def test_case_budget_allocation_weights_rank_and_keeps_the_floor():
    config = BudgetConfig(case_tokens=1_000_000, floor_tokens=40_000)
    plan = Plan(Cluster(1, 10_000), Cluster(2, 10_000), Cluster(3, 10_000), Cluster(4, 10_000),
                Cluster(5, 10_000))
    budgets = allocate(plan, config)
    # 800k beyond the floors, by triage budget x weight: 1.5, 0.85, 0.85, 0.4, 0.4 of 4.0
    assert budgets == {"C1": 340_000, "C2": 210_000, "C3": 210_000, "C4": 120_000,
                       "C5": 120_000}
    assert sum(budgets.values()) == 1_000_000
    # triage's own shares still count: a small rank-1 cluster gets less than a big rank-2 one
    budgets = allocate(Plan(Cluster(1, 5_000), Cluster(2, 30_000)), config)
    assert budgets["C1"] < budgets["C2"]
    # floors win over the case budget
    assert allocate(plan, BudgetConfig(case_tokens=100_000, floor_tokens=40_000)) == dict.fromkeys(
        ["C1", "C2", "C3", "C4", "C5"], 40_000)
    # weight 0 leaves the floor; all weights 0 falls back to triage's shares
    zero = BudgetConfig(case_tokens=200_000, floor_tokens=40_000, rank_weights=[1, 0],
                        priority_zero_weight=0)
    budgets = allocate(Plan(Cluster(1, 10_000), Cluster(2, 10_000), Cluster(3, 10_000, 0)), zero)
    assert budgets == {"C1": 120_000, "C2": 40_000, "C3": 40_000}
    budgets = allocate(Plan(Cluster(1, 10_000, 0), Cluster(2, 30_000, 0)), zero)
    assert budgets == {"C1": 70_000, "C2": 130_000}
    assert allocate(plan, BudgetConfig()) == dict.fromkeys(["C1", "C2", "C3", "C4", "C5"], None)
    # a pool has no episode budgets
    pooled = BudgetConfig(case_tokens=1_000_000, sharing="pool")
    assert allocate(plan, pooled) == dict.fromkeys(["C1", "C2", "C3", "C4", "C5"], None)


def test_low_tier_preset_and_its_allocation():
    config = ReviewConfig.model_validate({"tier": "low", "investigate": {"loop": {"context_window": 32000}}})
    investigate = config.investigate
    assert investigate.prompt == "low" and investigate.tool_output_tokens == 3000
    assert (investigate.loop.max_steps, investigate.loop.context_window) == (20, 32000)
    assert (investigate.budget.case_tokens, investigate.budget.sharing) == (600_000, "split")
    assert not investigate.coverage and investigate.examples.path is None
    assert investigate.ideation.samples == 0 and config.postprocess.postfilter.merge
    plan = Plan(Cluster(1, 20_000), Cluster(2, 20_000), Cluster(3, 10_000, priority=0),
                Cluster(4, 30_000), Cluster(5, 30_000))
    budgets = allocate(plan, investigate.budget)
    floor = investigate.budget.floor_tokens
    # rank 4+ and priority-0 clusters get the floor only; the rest goes to the top clusters
    assert budgets["C3"] == budgets["C4"] == budgets["C5"] == floor
    assert budgets["C1"] > budgets["C2"] > floor and sum(budgets.values()) <= 600_000

