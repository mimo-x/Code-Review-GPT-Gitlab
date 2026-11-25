"""The post-filter stages of post-processing (see postprocess), over the aggregated comments:

rules: drop comments on test or doc files and comments outside the diff.
merge: per file, the model names nearby comments that describe the same problem; one of
each set is kept, the others become its duplicates.

The stages update the comments' provenance in place.

Default-keep: failed calls and unknown ids keep comments.
Every call is saved as a one-step episode and loaded instead of repeated on resume.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from review_core.common import stable_id

from . import repair
from .agent import episode_id_for
from .aggregate import Comment
from .files import file_role
from .findings import SEVERITY_ORDER
from .policy import ModelRequest, PolicyError, Usage
from .schemas import tool_schema
from .trajectory import PRIVATE_KEYS, Episode, EpisodeStore, now
from .versions import FILTER_PROMPT_VERSION

MAX_LINE_CHARS = 400


class PostFilterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: bool = True
    merge: bool = True
    window: int = Field(default=10, ge=0)
    diff_chars: int = Field(default=24000, ge=1000)
    temperature: float | None = 0.7
    max_output_tokens: int | None = None


class Filtered(BaseModel):
    stage: Literal["rules", "merge", "final"]
    reason: str
    into: dict | None = None  # merge: provenance of the comment that was kept
    comment: Comment


# -- diff --------------------------------------------------------------------------------

MARKS = {"add": "+", "delete": "-", "context": " "}


def file_diffs(changes) -> dict[str, list]:
    """path (new or old) -> the hunks of its change."""
    out: dict[str, list] = {}
    for change in changes:
        for path in dict.fromkeys(p for p in (change.new_path, change.old_path) if p):
            out.setdefault(path, []).extend(change.hunks)
    return out


def _span(hunk, side: str) -> tuple[int, int]:
    if side == "base":
        return hunk.old_start, hunk.old_start + max(hunk.old_length, 1) - 1
    return hunk.new_start, hunk.new_start + max(hunk.new_length, 1) - 1


def _distance(lo: int, hi: int, comment: Comment) -> int:
    return max(0, lo - comment.end_line, comment.start_line - hi)


def _line(line) -> str:
    text = line.text.rstrip("\n")
    if len(text) > MAX_LINE_CHARS:
        text = text[:MAX_LINE_CHARS] + " [...]"
    return MARKS[line.kind] + text


def _hunk_lines(hunk, comments: list[Comment], budget: int) -> list[str]:
    """The hunk as diff lines; cut to the lines nearest the comments if over budget."""
    lines = [_line(line) for line in hunk.lines]
    if sum(len(x) + 1 for x in lines) <= budget:
        return lines

    def far(line) -> int:
        number = line.old_line if line.kind == "delete" else line.new_line
        if number is None:
            return 1 << 30
        return min(max(0, c.start_line - number, number - c.end_line) for c in comments)

    center = min(range(len(lines)), key=lambda i: far(hunk.lines[i]))
    lo = hi = center
    used = len(lines[center]) + 1
    while True:
        grown = False
        for step in (-1, 1):
            i = lo - 1 if step < 0 else hi + 1
            if 0 <= i < len(lines) and used + len(lines[i]) + 1 <= budget:
                used += len(lines[i]) + 1
                lo, hi = (i, hi) if step < 0 else (lo, i)
                grown = True
        if not grown:
            break
    return lines[lo : hi + 1]


def diff_view(diffs: dict[str, list], comments: list[Comment], limit: int) -> str:
    """Unified diff of the commented files; over `limit` characters, the hunks nearest the
    comments are kept."""
    paths = list(dict.fromkeys(c.path for c in comments))
    pieces = []
    for p, path in enumerate(paths):
        mine = [c for c in comments if c.path == path]
        for h, hunk in enumerate(diffs.get(path, [])):
            distance = min(_distance(*_span(hunk, c.side), c) for c in mine)
            pieces.append((distance, p, h))
    chosen: dict[tuple[int, int], list[str]] = {}
    used = sum(len(path) * 2 + 20 for path in paths)
    for _, p, h in sorted(pieces):
        hunk = diffs[paths[p]][h]
        header = f"@@ -{hunk.old_start},{hunk.old_length} +{hunk.new_start},{hunk.new_length} @@"
        room = limit - used - len(header) - 1
        if room < 200:
            continue
        mine = [c for c in comments if c.path == paths[p]]
        lines = _hunk_lines(hunk, mine, room)
        chosen[(p, h)] = [header, *lines]
        used += len(header) + 1 + sum(len(x) + 1 for x in lines)
    out = []
    for p, path in enumerate(paths):
        hunks = diffs.get(path, [])
        out += [f"--- a/{path}", f"+++ b/{path}"]
        shown = [chosen[(p, h)] for h in range(len(hunks)) if (p, h) in chosen]
        for lines in shown:
            out += lines
        if not hunks:
            out.append("(no diff for this file)")
        elif len(shown) < len(hunks):
            out.append(f"({len(hunks) - len(shown)} more hunks of this file not shown)")
    return "\n".join(out)


# -- rules -------------------------------------------------------------------------------


def rule_reason(comment: Comment) -> str | None:
    role = file_role(comment.path)
    if role in ("test", "doc"):
        return f"{role} file"
    if not comment.in_diff:
        return "not in the diff"
    return None


# -- model calls -------------------------------------------------------------------------


class SameProblemArgs(BaseModel):
    groups: list[list[str]] = Field(
        default_factory=list,
        description="sets of comment ids that describe the same problem, each with 2 or more "
        "ids; [] when every comment describes a different problem",
    )
    reason: str = Field(default="", description="one sentence")


class NoArgs(BaseModel):
    pass


MERGE_TOOLS = [
    tool_schema("same_problem", SameProblemArgs,
                "Report the sets of comments that describe the same problem."),
    tool_schema("no_duplicates", NoArgs, "Every comment describes a different problem."),
]

MERGE_SYSTEM = """\
You compare code review comments on one file of a pull request. The comments point at \
nearby lines, and some of them may describe the same problem in different words. Two \
comments describe the same problem when they are about the same cause in the same code, so \
that fixing one would also fix the other, even if their wording, severity or suggested fix \
differ. Two different problems on the same lines are not the same problem.

Call same_problem with the sets of comment ids that describe the same problem, or \
no_duplicates when every comment describes a different problem."""


def _calls(message: dict) -> list[tuple[str, dict | None]]:
    out = []
    for call in message.get("tool_calls") or []:
        raw = call["function"].get("arguments") or "{}"
        try:
            arguments = repair.loads(raw) if isinstance(raw, str) else raw
        except ValueError:
            arguments = None
        out.append((call["function"]["name"], arguments if isinstance(arguments, dict) else None))
    return out


def parse_merge(message: dict) -> tuple[tuple[list[list[str]], str] | None, str]:
    for name, arguments in _calls(message):
        if name == "no_duplicates":
            return ([], ""), ""
        if name != "same_problem" or arguments is None:
            continue
        groups = repair.decoded(arguments.get("groups") or [], [], "groups")
        if isinstance(groups, list) and groups and all(isinstance(g, str) for g in groups):
            groups = [groups]  # one set sent flat: ["c1", "c2"]
        arguments["groups"] = groups
        try:
            args = SameProblemArgs.model_validate(arguments)
        except ValidationError:
            continue
        return (args.groups, args.reason.strip()), ""
    return None, "Error: call same_problem(groups=[[ids], ...], reason) or no_duplicates()."


def ask(policy, system: str, user: str, tools: list[dict], parse, config: PostFilterConfig, *,
        identifier: str, store: EpisodeStore, task: dict,
        version: str = FILTER_PROMPT_VERSION) -> tuple[object, Episode]:
    """One tool call without an environment; an unusable answer is retried once with the
    error. Returns (parsed result of the last answer or None, episode). config: anything
    with max_output_tokens and temperature."""
    episode = store.load_or_run(
        identifier,
        lambda: _ask(policy, system, user, tools, parse, config, identifier, task, version))
    return (parse(episode.steps[-1].response)[0] if episode.steps else None), episode


def _ask(policy, system: str, user: str, tools: list[dict], parse, config: PostFilterConfig,
         identifier: str, task: dict, version: str = FILTER_PROMPT_VERSION) -> Episode:
    episode = Episode(
        id=identifier, role=task.get("stage", "postfilter"), task=task, policy=policy.describe(),
        prompt_version=version, tools_version=version, tools=tools,
        budget_tokens=None, context_window=0, started_at=now(),
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for _ in range(2):
        request = ModelRequest(messages=tuple(messages), tools=tuple(tools),
                               max_output_tokens=config.max_output_tokens,
                               temperature=config.temperature)
        try:
            response = policy.complete(request)
        except PolicyError as exc:
            episode.termination, episode.error = "error", str(exc)
            break
        episode.add_step(messages, response, [])
        result, error = parse(response.message)
        if result is not None:
            episode.termination = "finished"
            break
        shown = {k: v for k, v in response.message.items() if k not in PRIVATE_KEYS}
        calls = shown.get("tool_calls") or []
        messages = [*messages, shown, *(
            [{"role": "tool", "tool_call_id": c["id"], "content": error} for c in calls]
            or [{"role": "user", "content": error}])]
    else:
        episode.termination = "no_action"
    episode.ended_at = now()
    return episode


def _comment_block(key: str, comment: Comment) -> str:
    side = " (old version)" if comment.side == "base" else ""
    return (f"[{key}] lines {comment.start_line}-{comment.end_line}{side} "
            f"({comment.severity})\n{comment.content.strip()}")


# -- stages ------------------------------------------------------------------------------


def neighbourhoods(comments: list[Comment], window: int) -> list[list[int]]:
    """Indexes of comments on the same file whose line ranges overlap or lie within `window`
    lines of each other (transitively); only groups of two or more."""
    by_file: dict[tuple[str, str], list[int]] = {}
    for i, c in enumerate(comments):
        by_file.setdefault((c.path, c.side), []).append(i)
    out = []
    for indexes in by_file.values():
        indexes.sort(key=lambda i: (comments[i].start_line, comments[i].end_line))
        group: list[int] = []
        end = 0
        for i in indexes:
            c = comments[i]
            if group and c.start_line - end <= window:
                group.append(i)
                end = max(end, c.end_line)
                continue
            if len(group) > 1:
                out.append(group)
            group, end = [i], c.end_line
        if len(group) > 1:
            out.append(group)
    return out


def merge_sets(groups: list[list[str]], ids: dict[str, int]) -> list[list[int]]:
    """Valid sets: known ids of this group, two or more each, every id in one set only."""
    used: set[int] = set()
    out = []
    for group in groups:
        if not isinstance(group, list):
            continue
        members = []
        for key in group:
            index = ids.get(str(key).strip().strip("[]").lower())
            if index is not None and index not in used and index not in members:
                members.append(index)
        if len(members) > 1:
            used.update(members)
            out.append(members)
    return out


def keeper(comments: list[Comment], members: list[int]) -> int:
    return min(members, key=lambda i: (SEVERITY_ORDER.get(comments[i].severity, 9),
                                       not comments[i].in_diff, -len(comments[i].content), i))


def apply_rules(comments: list[Comment]) -> tuple[list[Comment], list[Filtered]]:
    kept, filtered = [], []
    for c in comments:
        reason = rule_reason(c)
        if reason:
            filtered.append(Filtered(stage="rules", reason=reason, comment=c))
        else:
            c.provenance["filter"] = {"rules": "passed"}
            kept.append(c)
    return kept, filtered


def merge_duplicates(comments: list[Comment], changes, policy, config: PostFilterConfig, *,
                     store: EpisodeStore, run_id: str,
                     case_id: str) -> tuple[list[Comment], list[Filtered], Usage]:
    diffs = file_diffs(changes)
    filtered: list[Filtered] = []
    usage = Usage()

    def identifier(stage: str, system: str, user: str) -> str:
        digest = stable_id({"v": FILTER_PROMPT_VERSION, "system": system, "user": user})[:16]
        return episode_id_for(run_id, case_id, f"filter/{stage}/{digest}")

    groups = neighbourhoods(comments, config.window)

    def merge_one(group: list[int]):
        path = comments[group[0]].path
        ids = {f"c{n + 1}": i for n, i in enumerate(group)}
        blocks = "\n\n".join(_comment_block(k, comments[i]) for k, i in ids.items())
        diff = diff_view(diffs, [comments[i] for i in group], config.diff_chars)
        user = (f"Comments on {path}:\n\n{blocks}\n\nDiff of {path} around them:\n"
                f"```diff\n{diff}\n```\n\nCall same_problem or no_duplicates.")
        result, episode = ask(
            policy, MERGE_SYSTEM, user, MERGE_TOOLS, parse_merge, config,
            identifier=identifier("merge", MERGE_SYSTEM, user), store=store,
            task={"case_id": case_id, "stage": "postfilter-merge", "path": path})
        return ids, result, episode

    with ThreadPoolExecutor(max_workers=max(1, len(groups))) as pool:
        answers = list(pool.map(merge_one, groups))
    dropped: set[int] = set()
    for ids, result, episode in answers:
        usage = usage + episode.usage
        groups_, reason = result if result is not None else ([], "")
        for members in merge_sets(groups_, ids):
            keep = keeper(comments, members)
            origin = {k: v for k, v in comments[keep].provenance.items() if k != "filter"}
            for i in members:
                if i == keep:
                    continue
                own = {k: v for k, v in comments[i].provenance.items() if k != "filter"}
                comments[keep].duplicates += [own, *comments[i].duplicates]
                # a copy: the working list's comments are still marked below
                filtered.append(Filtered(stage="merge", reason=reason, into=origin,
                                         comment=comments[i].model_copy(deep=True)))
                dropped.add(i)
            comments[keep].provenance.setdefault("filter", {})["merged"] = len(members) - 1
        for i in ids.values():
            comments[i].provenance.setdefault("filter", {}).setdefault(
                "merge", "checked" if result is not None else "no answer")
    return [c for i, c in enumerate(comments) if i not in dropped], filtered, usage


def stamp(comments: list[Comment]) -> None:
    for c in comments:
        c.provenance.setdefault("filter", {})["version"] = FILTER_PROMPT_VERSION
