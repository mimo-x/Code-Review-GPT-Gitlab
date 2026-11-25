"""Comments posted straight to the author: what investigators report, in which language,
and the final review that keeps the most important comments."""
from __future__ import annotations

import pytest
from test_agent import call
from test_postfilter import comment

from review_agent import prompts
from review_agent.config import FinalReviewConfig, ReviewConfig
from review_agent.final import review as final_review
from review_agent.policy import PolicyError, ScriptedPolicy
from review_agent.postprocess import postprocess
from review_agent.trajectory import EpisodeStore


@pytest.mark.parametrize("variant", ["standard", "low"])
def test_merge_blocking_replaces_every_coverage_passage(variant):
    text = prompts.system_prompt(variant, "merge_blocking")
    for old, new in prompts.MERGE_BLOCKING[variant]:
        assert old not in text and new in text
    assert prompts.system_prompt(variant) == prompts.VARIANTS[variant].system
    assert prompts.prompt_version(variant) == prompts.VARIANTS[variant].version
    assert prompts.prompt_version(variant, "merge_blocking", "zh-CN").endswith(
        "+merge-blocking-v1+zh-CN")


def test_language_is_told_to_the_investigator():
    text = prompts.system_prompt("standard", language="zh-CN")
    assert "Write findings in Simplified Chinese" in text and "in English" not in text


def test_tiers():
    low, high, xhigh = (ReviewConfig(tier=t) for t in ("low", "high", "xhigh"))
    assert [c.investigate.reporting for c in (low, high, xhigh)] == [
        "merge_blocking", "merge_blocking", "coverage"]
    assert [c.postprocess.final_review.max_comments for c in (low, high, xhigh)] == [10, 20, 30]
    assert (high.investigate.ideation.samples, xhigh.investigate.ideation.samples) == (0, 3)
    assert xhigh.investigate.budget == high.investigate.budget
    assert ReviewConfig(tier="high", postprocess={"final_review": {"max_comments": 5}}
                        ).postprocess.final_review.max_comments == 5
    assert ReviewConfig().language == "en"


def run(comments, script, limit=3):
    return final_review(comments, ScriptedPolicy(script), FinalReviewConfig(max_comments=limit),
                        store=EpisodeStore(None), run_id="r", case_id="c")


def test_final_review_keeps_the_chosen_comments_in_its_order():
    comments = [comment(start=n, text=f"problem {n}") for n in (1, 2, 3, 4)]
    answer = call("select_comments", {"keep": [
        {"id": "c3", "severity": "critical"}, {"id": "c1", "severity": "major", "same_as": ["c4"]},
        {"id": "c3", "severity": "minor"}, {"id": "zz", "severity": "minor"}]})
    kept, left, _ = run(comments, [answer])
    assert [c.start_line for c in kept] == [3, 1]
    assert kept[0].severity == "critical" and kept[0].provenance["final"]["severity_was"] == "major"
    assert kept[1].provenance["final"]["also"] == [
        {"path": "api.py", "side": "head", "start_line": 4, "end_line": 4}]
    assert len(kept[1].duplicates) == 1
    assert sorted((f.stage, f.comment.start_line, f.reason) for f in left) == [
        ("final", 2, "not selected"), ("final", 4, "same mistake as a kept comment")]


def test_final_review_caps_and_may_keep_none():
    comments = [comment(start=n) for n in range(1, 6)]
    keep = [{"id": f"c{n}", "severity": "minor"} for n in range(1, 6)]
    kept, _, _ = run(comments, [call("select_comments", {"keep": keep})], limit=2)
    assert [c.start_line for c in kept] == [1, 2]
    kept, left, _ = run(comments, [call("select_comments", {"keep": []})], limit=2)
    assert len(kept) == 2 and kept[0].provenance["final"]["selected"] == "default"


def test_final_review_falls_back_to_the_order_when_the_call_fails():
    def fail(_request):
        raise PolicyError("down")
    comments = [comment(start=n) for n in range(1, 6)]
    kept, left, _ = run(comments, fail, limit=3)
    assert [c.start_line for c in kept] == [1, 2, 3] and len(left) == 2
    assert run([], fail)[0] == []


def test_postprocess_runs_the_final_review_after_the_filter():
    from types import SimpleNamespace
    findings = [dict(id=f"F{n}", path="api.py", side="head", start_line=n * 20,
                     end_line=n * 20, in_diff=True, title=f"distinct issue number {n}",
                     description="d", category="defect", severity="major", condition=None,
                     evidence=["e"], suggestion=None, existing_code=f"x{n}", unit=None,
                     cluster="C1", reported_step=1, about_removal=False, withdrawn=False)
                for n in (1, 2, 3)]
    episode = SimpleNamespace(id="e1", findings=findings)
    config = ReviewConfig(tier="high", postprocess={
        "postfilter": None, "final_review": {"max_comments": 1}}).postprocess
    answer = call("select_comments", {"keep": [{"id": "c2", "severity": "minor"}]})
    comments, filtered, _ = postprocess([(1, episode)], [], ScriptedPolicy([answer]), config,
                                        store=EpisodeStore(None), run_id="r", case_id="c")
    assert [c.start_line for c in comments] == [40] and comments[0].severity == "minor"
    assert [f.stage for f in filtered] == ["final", "final"]
