"""行内讨论的分组和限额。"""
from apps.review.engines.base import Finding
from apps.review.publishers.threads import MAX_MINOR_THREADS, plan_threads


def item(severity, line, fp=None, path="a.py", in_diff=True):
    return Finding(
        path=path, title=f"{severity}-{line}", severity=severity, start_line=line, end_line=line,
        in_diff=in_diff, fingerprint=fp or f"{path}-{severity}-{line}",
    )


def titles(threads):
    return [[finding.title for finding in thread] for thread in threads]


def test_severe_issues_get_their_own_thread_even_when_adjacent():
    threads = plan_threads([item("critical", 1), item("major", 2)], {}, 20)
    assert titles(threads) == [["critical-1"], ["major-2"]]


def test_minor_issues_within_three_lines_are_merged():
    threads = plan_threads([item("minor", 1), item("minor", 4), item("minor", 8),
                            item("minor", 8, path="b.py")], {}, 20)
    assert titles(threads) == [["minor-1", "minor-4"], ["minor-8"], ["minor-8"]]


def test_nits_and_unlocated_issues_stay_in_the_summary():
    assert plan_threads([item("nit", 1), item("major", 2, in_diff=False)], {}, 20) == []


def test_minor_threads_are_capped():
    findings = [item("minor", line * 10) for line in range(1, 9)]
    assert len(plan_threads(findings, {}, 20)) == MAX_MINOR_THREADS


def test_severe_issues_are_not_crowded_out_by_minor_ones():
    findings = [item("minor", line * 10) for line in range(1, 4)] + [item("major", 100)]
    assert titles(plan_threads(findings, {}, 2)) == [["major-100"], ["minor-10"]]


def test_published_issues_are_skipped_and_count_against_the_limits():
    findings = [item("minor", line * 10) for line in range(1, 9)]
    published = {f.fingerprint: {"severity": "minor", "discussion": f"d{i}"}
                 for i, f in enumerate(findings[:3])}
    threads = plan_threads(findings, published, 20)
    assert len(threads) == MAX_MINOR_THREADS - 3
    assert all(thread[0].fingerprint not in published for thread in threads)


def test_issues_no_longer_reported_free_their_slots():
    published = {"gone": {"severity": "major", "discussion": "d1"}}
    assert len(plan_threads([item("major", 1)], published, 1)) == 1
