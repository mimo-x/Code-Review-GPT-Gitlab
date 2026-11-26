"""行内讨论：哪些问题挂到代码行上，以及条数限制。"""
from apps.review.engines.base import Finding
from apps.review.publishers.threads import plan_threads


def item(severity, line, fp=None, path="a.py", in_diff=True):
    return Finding(
        path=path, title=f"{severity}-{line}", severity=severity, start_line=line, end_line=line,
        in_diff=in_diff, fingerprint=fp or f"{path}-{severity}-{line}",
    )


def titles(threads):
    return [[finding.title for finding in thread] for thread in threads]


def test_only_severe_issues_go_inline_each_in_its_own_thread():
    threads = plan_threads([item("critical", 1), item("major", 2), item("minor", 3),
                            item("nit", 4)], {}, 10)
    assert titles(threads) == [["critical-1"], ["major-2"]]


def test_unlocated_issues_stay_in_the_summary():
    assert plan_threads([item("major", 2, in_diff=False)], {}, 10) == []


def test_threads_are_capped():
    findings = [item("major", line) for line in range(1, 15)]
    assert len(plan_threads(findings, {}, 10)) == 10


def test_published_issues_are_skipped_and_count_against_the_limit():
    findings = [item("major", line) for line in range(1, 9)]
    published = {f.fingerprint: {"severity": "major", "discussion": f"d{i}"}
                 for i, f in enumerate(findings[:3])}
    threads = plan_threads(findings, published, 5)
    assert titles(threads) == [["major-4"], ["major-5"]]


def test_issues_no_longer_reported_free_their_slots():
    published = {"gone": {"severity": "major", "discussion": "d1"}}
    assert len(plan_threads([item("major", 1)], published, 1)) == 1
