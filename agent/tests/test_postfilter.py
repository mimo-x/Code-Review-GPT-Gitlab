from __future__ import annotations

import json

from test_agent import call, coverage_tiers, planned, standard_script  # noqa: F401

from review_agent.aggregate import Comment
from review_agent.config import PostprocessConfig, ReviewConfig
from review_agent.orchestrator import review
from review_agent.policy import ScriptedPolicy, Usage
from review_agent.postfilter import (
    MERGE_SYSTEM,
    PostFilterConfig,
    apply_rules,
    diff_view,
    file_diffs,
    keeper,
    merge_duplicates,
    merge_sets,
    neighbourhoods,
    parse_merge,
)
from review_agent.trajectory import EpisodeStore


def comment(path="api.py", start=4, end=None, text="Result is not checked", **extra):
    return Comment(**{
        "path": path, "side": "head", "start_line": start, "end_line": end or start, "content": text,
        "title": text, "category": "defect", "severity": "major", "in_diff": True,
        "provenance": {"episode_id": "e", "finding_id": f"F{start}", "cluster": "C1"}, **extra})


def system(request) -> str:
    return request.messages[0]["content"]


OFF = dict(rules=False, merge=False)


def merge(comments, changes, policy, store=None):
    return merge_duplicates(comments, changes, policy, PostFilterConfig(),
                            store=store or EpisodeStore(None), run_id="", case_id="")


def test_rules_drop_test_doc_and_out_of_diff_comments():
    comments = [comment(), comment(path="tests/test_users.py"), comment(path="README.md"),
                comment(start=9, in_diff=False)]
    kept, filtered = apply_rules(comments)
    assert [c.path for c in kept] == ["api.py"] and kept[0].start_line == 4
    assert [(f.stage, f.reason) for f in filtered] == [
        ("rules", "test file"), ("rules", "doc file"), ("rules", "not in the diff")]
    assert kept[0].provenance["filter"]["rules"] == "passed"


def test_neighbourhoods_by_window():
    comments = [comment(start=1, end=2), comment(start=12, end=14), comment(start=25),
                comment(start=30, end=31), comment(start=35), comment(path="b.py", start=13),
                comment(start=3, side="base")]
    assert neighbourhoods(comments, 10) == [[0, 1], [2, 3, 4]]
    assert neighbourhoods(comments, 4) == [[3, 4]]
    assert neighbourhoods(comments, 11) == [[0, 1, 2, 3, 4]]
    assert neighbourhoods(comments, 0) == []


def test_parse_merge_answers():
    assert parse_merge(call("same_problem", {"groups": [["c1", "c2"]], "reason": "r"})) == (
        ([["c1", "c2"]], "r"), "")
    assert parse_merge(call("same_problem", {"groups": ["c1", "c2"]}))[0] == ([["c1", "c2"]], "")
    assert parse_merge(call("same_problem", {"groups": '[["c1", "c3"]]'}))[0] == ([["c1", "c3"]], "")
    assert parse_merge(call("no_duplicates", {}))[0] == ([], "")
    assert parse_merge({"role": "assistant", "content": "c1 and c2"})[0] is None


def test_merge_sets_validation_and_keeper():
    ids = {"c1": 0, "c2": 1, "c3": 2, "c4": 3}
    assert merge_sets([["c1", "C3"], ["c2", "zz"], ["c3", "c4"], ["c2", "c2"], "c4"], ids) == [[0, 2]]
    comments = [comment(severity="minor", text="long " * 9), comment(text="short"),
                comment(text="longer text", in_diff=False), comment(text="a bit longer")]
    assert keeper(comments, [0, 1, 2, 3]) == 3  # severity, then in_diff, then length
    assert keeper(comments, [0, 2]) == 2


def test_merge_keeps_one_per_set(reviewed, tmp_path):
    changes = reviewed[1].snapshot.changes
    comments = [comment(start=4, text="Crash on None"), comment(start=4, text="Crashes when the user is None"),
                comment(start=6, text="Unrelated naming issue"), comment(path="users.py", start=2)]

    def script(request):
        assert system(request) == MERGE_SYSTEM
        assert "[c1] lines 4-4 (major)" in request.messages[1]["content"]
        assert "+    return fetch(id)[\"name\"].upper()" in request.messages[1]["content"]
        return call("same_problem", {"groups": [["c1", "c2"], ["c3", "c9"]], "reason": "both: None"})

    policy = ScriptedPolicy(script, usage=lambda r, m: Usage(input_tokens=10, output_tokens=2))
    originals = [c.model_copy(deep=True) for c in comments]
    kept, filtered, usage = merge([c.model_copy(deep=True) for c in comments], changes, policy,
                                  EpisodeStore(tmp_path))
    assert policy.calls == 1 and usage.total == 12
    assert [c.content for c in kept] == ["Crashes when the user is None", "Unrelated naming issue",
                                         "Result is not checked"]
    assert kept[0].duplicates == [originals[0].provenance]
    assert kept[0].provenance["filter"]["merged"] == 1
    (merged,) = filtered
    assert merged.stage == "merge" and merged.comment.content == "Crash on None"
    assert merged.into == originals[1].provenance and merged.reason == "both: None"
    # the record is the comment as it was merged away, not marked by the later stages
    assert merged.comment.provenance.get("filter") is None
    assert kept[0].provenance["filter"]["merge"] == "checked"
    again = ScriptedPolicy(script)
    resumed = merge(comments, changes, again, EpisodeStore(tmp_path))
    assert again.calls == 0 and resumed == (kept, filtered, usage)


def test_failed_merge_answers_keep_comments(reviewed):
    changes = reviewed[1].snapshot.changes
    comments = [comment(path="users.py", start=2), comment(path="users.py", start=3, text="Other")]
    policy = ScriptedPolicy(lambda r: {"role": "assistant", "content": "c1 and c2 are the same."})
    kept, filtered, _ = merge(comments, changes, policy)
    assert len(kept) == 2 and not filtered
    assert policy.calls == 2  # one retry with the error
    assert [c.provenance["filter"]["merge"] for c in kept] == ["no answer", "no answer"]


def test_diff_view_keeps_hunks_nearest_the_comments(reviewed):
    diffs = file_diffs(reviewed[1].snapshot.changes)
    text = diff_view(diffs, [comment(path="users.py", start=2)], 24000)
    assert text.startswith("--- a/users.py\n+++ b/users.py\n@@ ")
    assert "+    if id is None:" in text


def filter_script(request):
    if system(request) == MERGE_SYSTEM:
        return call("no_duplicates", {})
    return standard_script(request)


def test_filter_on_by_default_and_null_turns_it_off(planned, tmp_path):  # noqa: F811
    assert ReviewConfig().postprocess.postfilter == PostFilterConfig()
    assert ReviewConfig.model_validate({}).postprocess.postfilter == PostFilterConfig()
    assert ReviewConfig.model_validate(
        {"postprocess": {"postfilter": None}}).postprocess.postfilter is None

    intel, _ = planned
    off = review(intel, ScriptedPolicy(standard_script),
                 ReviewConfig(postprocess=PostprocessConfig(postfilter=None, final_review=None)),
                 run_id="r", case_id="c", out_dir=tmp_path / "off")
    data = off.model_dump(mode="json")
    assert "filtered" not in data and data["config"]["postprocess"]["postfilter"] is None
    assert ReviewConfig.model_validate(data["config"]).postprocess.postfilter is None
    idle = review(intel, ScriptedPolicy(standard_script),
                  ReviewConfig(postprocess=PostprocessConfig(postfilter=PostFilterConfig(**OFF))),
                  run_id="r", case_id="c", out_dir=tmp_path / "idle")
    strip = [c.model_dump(exclude={"provenance"}) for c in idle.comments]
    assert strip == [c.model_dump(exclude={"provenance"}) for c in off.comments] and idle.filtered == []

    policy = ScriptedPolicy(filter_script)
    on = review(intel, policy, ReviewConfig(), run_id="r", case_id="c", out_dir=tmp_path / "on")
    assert [c.model_dump(exclude={"provenance"}) for c in on.comments] == strip and on.filtered == []
    assert policy.calls == 3  # one comment: no merge call
    assert on.comments[0].provenance["filter"] == {"rules": "passed", "version": "postfilter-v1"}
    assert json.loads(on.model_dump_json())["config"]["postprocess"]["postfilter"]["window"] == 10


def test_cap_counts_only_comments_left_after_the_filter():
    from review_agent.aggregate import AggregateConfig
    from review_agent.postprocess import postprocess

    class Ep:
        id = "e"

        def __init__(self, findings):
            self.findings = findings

    def item(index, path, severity):
        return {"id": f"F{index}", "path": path, "side": "head", "start_line": 3, "end_line": 3,
                "in_diff": True, "title": f"issue {index}", "description": f"issue {index} in {path}",
                "category": "defect", "severity": severity, "existing_code": "x", "withdrawn": False}

    config = PostprocessConfig(aggregate=AggregateConfig(max_comments=1),
                               postfilter=PostFilterConfig(merge=False))
    episodes = [(0, Ep([item(1, "tests/test_a.py", "critical"), item(2, "a.py", "major")]))]
    kept, filtered, _ = postprocess(episodes, None, None, config, store=EpisodeStore(None),
                                    run_id="", case_id="")
    assert [c.path for c in kept] == ["a.py"]
    assert [f.comment.path for f in filtered] == ["tests/test_a.py"]
