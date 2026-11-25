from __future__ import annotations

import json

import pytest

from review_agent.config import ReviewConfig
from review_agent.focus import Location, select
from review_agent.orchestrator import review
from review_agent.policy import ScriptedPolicy, Usage
from review_core.intel import CodeIntel
from review_core.triage import Triage
from review_core.workspace import Workspace


def finish(request):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "c0",
                "type": "function",
                "function": {"name": "finish", "arguments": json.dumps({"summary": "done"})},
            }
        ],
    }


@pytest.fixture
def two_clusters(repository, tmp_path):
    """Two unrelated files in different directories: one cluster each."""
    alpha = "def alpha(x):\n    y = x + 1\n    z = y * 2\n    w = z - 3\n    return w\n"
    beta = "class Beta:\n    def run(self):\n        a = 1\n        b = 2\n        return a + b\n"
    repository.write("one/alpha.py", alpha)
    repository.write("two/beta.py", beta)
    base = repository.commit("base")
    repository.write("one/alpha.py", alpha.replace("x + 1", "x + 10"))
    repository.write("two/beta.py", beta.replace("b = 2", "b = 20"))
    head = repository.commit("head")
    workspace = Workspace.create(repository.path, tmp_path / "state", "test/two", base, head)
    intel = CodeIntel(workspace)
    plan = Triage(intel).plan()
    handles = {}
    for unit in intel.changed_symbols():
        cluster = next(c for c in plan.clusters if unit.id in c.unit_ids)
        handles[unit.new_path] = cluster.handle
    assert len(plan.clusters) == 2 and handles["one/alpha.py"] != handles["two/beta.py"]
    return intel, plan, handles


def test_focus_selects_the_clusters_a_location_points_at(two_clusters):
    intel, plan, handles = two_clusters
    changes = intel.workspace.snapshot.changes
    units = intel.changed_symbols()

    def chosen(*locations):
        return select(plan, units, changes, list(locations))

    # on the changed line
    focus = chosen(Location(path="two/beta.py", side="head", start_line=4, end_line=4))
    assert focus.clusters == [handles["two/beta.py"]] and focus.skipped == [handles["one/alpha.py"]]
    # an unchanged line inside the changed method
    assert chosen(Location(path="two/beta.py", side="head", start_line=5)).clusters == [
        handles["two/beta.py"]
    ]
    # no lines: anywhere in the file; no side: either side
    assert chosen(Location(path="one/alpha.py")).clusters == [handles["one/alpha.py"]]
    assert chosen(Location(path="one/alpha.py", side="base", start_line=2)).clusters == [
        handles["one/alpha.py"]
    ]
    # a line far from any change (a file-level comment on line 1): the file's units
    far = Location(path="two/beta.py", side="head", start_line=40)
    assert chosen(far).clusters == [handles["two/beta.py"]] and not chosen(far).unmatched
    # a path outside the diff matches nothing
    missing = Location(path="one/gamma.py", side="head", start_line=1)
    focus = chosen(missing, Location(path="one/alpha.py", side="head", start_line=2))
    assert focus.clusters == [handles["one/alpha.py"]] and focus.unmatched == [missing]
    assert chosen().clusters == []


def test_focused_review_runs_the_rest_later_under_the_same_ids(two_clusters, tmp_path):
    intel, plan, handles = two_clusters
    policy = ScriptedPolicy(finish, usage=lambda r, m: Usage(input_tokens=100))
    target = Location(path="one/alpha.py", side="head", start_line=2, end_line=2)
    focused = review(
        intel, policy, ReviewConfig(), run_id="r", case_id="c", out_dir=tmp_path, focus=[target]
    )
    assert focused.focus.clusters == [handles["one/alpha.py"]]
    assert focused.focus.skipped == [handles["two/beta.py"]] and not focused.focus.unmatched
    assert [e.cluster for e in focused.episodes] == [handles["one/alpha.py"]]
    spent = focused.budget_pool["used"]
    calls = policy.calls
    # the full review loads the focused episode, spends it from the pool, runs the other
    full = review(intel, policy, ReviewConfig(), run_id="r", case_id="c", out_dir=tmp_path)
    assert full.focus is None and "focus" not in full.model_dump()
    assert sorted(e.cluster for e in full.episodes) == sorted(handles.values())
    assert focused.episodes[0] in full.episodes
    assert full.budget_pool["resumed"] == spent
    assert policy.calls - calls == calls  # one cluster's episode, as many calls again
    assert full.budget_pool["used"] == 2 * spent
