"""Post-processing: the findings of all episodes -> the review's comments, as one fixed
sequence of stages.

    select   drop withdrawn findings and those below min_severity       (aggregate)
    order    by severity, in the diff first, cluster rank, path, line   (aggregate)
    dedupe   lexically similar findings become duplicates of one comment (aggregate)
    rules    drop comments on test or doc files and outside the diff    (postfilter)
    merge    the model names comments that describe the same problem    (postfilter)
    stamp    record the filter version in each comment's provenance     (postfilter)
    final    the model keeps the most important, settles severity and folds
             repeats of one mistake                                     (final)
    cap      keep the first max_comments of what is left                (aggregate)

The post-filter stages (rules, merge, stamp) run only when the filter is on, the final
review only when it is configured.
"""

from __future__ import annotations

from . import aggregate, final, postfilter
from .aggregate import Comment
from .config import PostprocessConfig
from .policy import Usage
from .postfilter import Filtered
from .trajectory import EpisodeStore


def postprocess(
    results: list[tuple[int, object]],
    changes,
    policy,
    config: PostprocessConfig,
    *,
    store: EpisodeStore,
    run_id: str,
    case_id: str,
) -> tuple[list[Comment], list[Filtered] | None, Usage]:
    """results: (cluster rank, Episode) pairs. Returns (comments, what the filter removed or
    merged (None: filter off), the filter's model usage)."""
    candidates = aggregate.order(aggregate.select(results, config.aggregate))
    comments = aggregate.dedupe(candidates, config.aggregate)
    filter_config = config.postfilter
    filtered: list[Filtered] | None = None
    usage = Usage()
    if filter_config is not None:
        filtered = []
        if filter_config.rules:
            comments, removed = postfilter.apply_rules(comments)
            filtered += removed
        if filter_config.merge:
            comments, merged, usage = postfilter.merge_duplicates(
                comments, changes, policy, filter_config,
                store=store, run_id=run_id, case_id=case_id)
            filtered += merged
        postfilter.stamp(comments)
    if config.final_review is not None:
        comments, left, final_usage = final.review(
            comments, policy, config.final_review, store=store, run_id=run_id, case_id=case_id)
        usage = usage + final_usage
        filtered = (filtered or []) + left
    return aggregate.cap(comments, config.aggregate), filtered, usage
