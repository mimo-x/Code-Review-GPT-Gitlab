"""The final review: one model call over every comment left after the post-filter (see
postprocess). Comments go straight to the author, so it keeps at most max_comments, the
most important first, settles each kept comment's severity, and folds comments that repeat
one mistake in several places into the clearest of them.

Default-keep in order: when the call fails or names no usable comment, the first
max_comments of the post-processed order are kept as they are.
The call is saved as a one-step episode and loaded instead of repeated on resume.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from review_core.common import stable_id

from . import repair
from .agent import episode_id_for
from .aggregate import Comment
from .config import FinalReviewConfig
from .findings import Severity
from .policy import Usage
from .postfilter import Filtered, ask
from .schemas import tool_schema
from .trajectory import EpisodeStore
from .versions import FINAL_REVIEW_VERSION

SYSTEM = """\
You are the last reviewer of a pull request's review comments before they are posted to \
its author. Choose at most {limit} comments to post, the most important first, and call \
select_comments once.

- Keep a comment only when it names concrete code and a consequence the author should fix \
before merging. Drop comments that are speculative, about style or naming, weakly \
supported by the code they quote, or contradicted by other comments.
- Severity of each kept comment: critical = security hole, data loss, crash or a broken \
core feature; major = wrong behaviour in some cases or a likely risk; minor = an edge case, \
performance or maintainability problem worth fixing; nit = wording or naming. Use critical \
and major only when merging as is would cause that harm.
- When several comments describe the same mistake in different places, keep the clearest \
one and list the others in its same_as.

Posting fewer comments is fine, and posting none is fine when no comment deserves it."""


class Pick(BaseModel):
    id: str = Field(description="comment id, e.g. c3")
    severity: Severity
    same_as: list[str] = Field(
        default_factory=list, description="ids of comments that repeat this mistake elsewhere")


class SelectArgs(BaseModel):
    keep: list[Pick] = Field(description="comments to post, most important first")
    reason: str = Field(default="", description="one sentence on what was dropped and why")


TOOLS = [tool_schema("select_comments", SelectArgs,
                     "Choose the comments to post, most important first.")]


def parse(message: dict) -> tuple[SelectArgs | None, str]:
    for call in message.get("tool_calls") or []:
        if call["function"].get("name") != "select_comments":
            continue
        raw = call["function"].get("arguments") or "{}"
        try:
            arguments = repair.loads(raw) if isinstance(raw, str) else raw
            arguments["keep"] = repair.decoded(arguments.get("keep") or [], [], "keep")
            return SelectArgs.model_validate(arguments), ""
        except (ValueError, TypeError, AttributeError, ValidationError):
            continue
    return None, "Error: call select_comments(keep=[{id, severity, same_as}], reason)."


def _block(key: str, comment: Comment) -> str:
    side = " (old version)" if comment.side == "base" else ""
    return (f"[{key}] {comment.path}:{comment.start_line}-{comment.end_line}{side} "
            f"({comment.severity})\n{comment.content.strip()}")


def review(comments: list[Comment], policy, config: FinalReviewConfig, *, store: EpisodeStore,
           run_id: str, case_id: str) -> tuple[list[Comment], list[Filtered], Usage]:
    """comments: post-processed, in order. Returns (comments to post, those left out, the
    call's model usage)."""
    if not comments:
        return [], [], Usage()
    limit = config.max_comments
    system = SYSTEM.format(limit=limit)
    ids = {f"c{n + 1}": i for n, i in enumerate(range(len(comments)))}
    user = "\n\n".join(_block(key, comments[i]) for key, i in ids.items())
    user += f"\n\nCall select_comments with at most {limit} comments."
    digest = stable_id({"v": FINAL_REVIEW_VERSION, "system": system, "user": user})[:16]
    result, episode = ask(
        policy, system, user, TOOLS, parse, config,
        identifier=episode_id_for(run_id, case_id, f"final/{digest}"), store=store,
        task={"case_id": case_id, "stage": "final-review"}, version=FINAL_REVIEW_VERSION)
    kept = _apply(comments, ids, result, limit)
    chosen = {id(c) for c in kept}
    left = [
        Filtered(stage="final", reason=(result.reason if result else "") or "not selected",
                 comment=c.model_copy(deep=True))
        for c in comments if id(c) not in chosen and not c.provenance.get("final", {}).get("folded")
    ]
    left += [
        Filtered(stage="final", reason="same mistake as a kept comment",
                 comment=c.model_copy(deep=True))
        for c in comments if c.provenance.get("final", {}).get("folded")
    ]
    return kept, left, episode.usage


def _apply(comments: list[Comment], ids: dict[str, int], result: SelectArgs | None,
           limit: int) -> list[Comment]:
    def index(key: str) -> int | None:
        return ids.get(str(key).strip().strip("[]").lower())

    picks = []
    used: set[int] = set()
    for pick in (result.keep if result else []):
        i = index(pick.id)
        if i is None or i in used:
            continue
        used.add(i)
        picks.append((i, pick))
        if len(picks) == limit:
            break
    if not picks:  # no usable answer: the post-processed order decides
        kept = comments[:limit]
        for c in kept:
            c.provenance["final"] = {"version": FINAL_REVIEW_VERSION, "selected": "default"}
        return kept
    kept = []
    for i, pick in picks:
        comment = comments[i]
        record = {"version": FINAL_REVIEW_VERSION, "selected": "model"}
        if pick.severity != comment.severity:
            record["severity_was"] = comment.severity
            comment.severity = pick.severity
        also = []
        for key in pick.same_as:
            j = index(key)
            if j is None or j in used:
                continue
            used.add(j)
            other = comments[j]
            other.provenance["final"] = {"version": FINAL_REVIEW_VERSION, "folded": True}
            comment.duplicates += [dict(other.provenance), *other.duplicates]
            also.append({"path": other.path, "side": other.side,
                         "start_line": other.start_line, "end_line": other.end_line})
        if also:
            record["also"] = also
        comment.provenance["final"] = record
        kept.append(comment)
    return kept
