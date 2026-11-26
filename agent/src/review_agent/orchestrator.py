"""Deterministic orchestration of one review: triage -> the case budget split among the
clusters or pooled -> one investigator episode per cluster, all at once -> post-processing.
No model decides the control flow. Load on the model server is bounded by the policy (a
GatedPolicy shared by every case), not here."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic import BaseModel, Field, model_serializer

from review_core.triage import Triage

from .agent import episode_id_for, run_episode
from .aggregate import Comment
from .budget import CasePool, allocate
from .config import ExamplesConfig, ReviewConfig
from .env import InvestigateEnv
from .focus import Focus, Location, select
from .policy import Usage
from .postfilter import Filtered
from .postprocess import postprocess
from .trajectory import Episode, EpisodeStore
from .versions import REVIEW_VERSION, recorded

_INDEXES: dict = {}


def _examples(config: ExamplesConfig):
    if not config.path:
        return None
    from .examples import ExampleIndex

    if config.path not in _INDEXES:
        _INDEXES[config.path] = ExampleIndex.load(Path(config.path))
    return _INDEXES[config.path], config.mode


class EpisodeSummary(BaseModel):
    id: str
    cluster: str
    rank: int
    budget_tokens: int | None
    termination: str | None
    steps: int
    findings: int
    usage: Usage
    error: str | None = None


class CaseReview(BaseModel):
    version: str = REVIEW_VERSION
    # every version string in effect (see versions)
    versions: dict[str, str] = Field(default_factory=recorded)
    run_id: str
    case_id: str
    snapshot_id: str
    plan_id: str
    policy: dict
    config: ReviewConfig
    episodes: list[EpisodeSummary]
    comments: list[Comment]
    usage: Usage
    duration_s: float
    errors: list[str] = Field(default_factory=list)
    # comments the post-filter removed or merged, for auditing; None: filter off
    filtered: list[Filtered] | None = None
    # the shared case budget (limit, used; resumed: of it, by episodes loaded on resume);
    # None: no pool
    budget_pool: dict | None = None
    # the clusters a focused review investigated and skipped; None: every cluster
    focus: Focus | None = None

    @model_serializer(mode="wrap")
    def _dump(self, handler):
        data = handler(self)
        for key in ("filtered", "budget_pool", "focus"):
            if getattr(self, key) is None:
                data.pop(key, None)
        return data


def review(
    intel,
    policy,
    config: ReviewConfig,
    *,
    run_id: str,
    case_id: str,
    out_dir: Path,
    focus: list[Location] | None = None,
) -> CaseReview:
    """focus: investigate only the clusters these locations point at (see focus.select);
    budgets are still allocated over every cluster, as in a full review."""
    started = time.monotonic()
    lock = threading.Lock()
    with lock:
        plan = Triage(intel, config.triage).plan()
        focused = None if focus is None else select(
            plan, intel.changed_symbols(), intel.workspace.snapshot.changes, focus)
    clusters = [c for c in plan.clusters if focused is None or c.handle in focused.clusters]
    investigate_config = config.investigate
    budgets = allocate(plan, investigate_config.budget)
    case_pool = CasePool.of(investigate_config.budget)
    store = EpisodeStore(out_dir / "episodes")
    ids = {c.handle: episode_id_for(run_id, case_id, c.handle) for c in plan.clusters}
    # a resumed case loads its finished episodes instead of running them again; what they
    # used is spent from the pool before the others start
    cached = {handle: store.load(identifier) for handle, identifier in ids.items()}
    resumed = sum(episode.usage.total for episode in cached.values() if episode is not None)
    if case_pool is not None:
        case_pool.precharge(resumed)
    examples = _examples(investigate_config.examples)

    listing: list[Episode] = []  # candidate-listing passes; their usage counts too

    def ideate(cluster) -> list[dict]:
        from .ideation import IdeationEnv, merge

        samples = []
        for sample in range(investigate_config.ideation.samples):
            identifier = episode_id_for(run_id, case_id, f"{cluster.handle}/ideation", sample)
            episode = store.load(identifier)
            if episode is None:
                env = IdeationEnv(
                    intel, plan, cluster.handle, None, lock=lock,
                    max_output_tokens=investigate_config.tool_output_tokens, examples=examples,
                    task={"case_id": case_id, "snapshot_id": intel.workspace.snapshot.id,
                          "plan_id": plan.id, "cluster": cluster.handle, "sample": sample},
                )
                loop = investigate_config.loop.model_copy(
                    update={"max_steps": investigate_config.ideation.steps, "milestones": []})
                try:
                    episode = run_episode(env, policy, loop, episode_id=identifier)
                except Exception:  # a failed pass only means fewer candidates
                    continue
                store.save(episode)
            samples.append(list(episode.candidates))
            listing.append(episode)
        return merge(samples)

    def investigate(cluster) -> tuple[int, Episode]:
        episode = cached[cluster.handle]
        if episode is None:
            episode = run_investigation(cluster, ids[cluster.handle])
            store.save(episode)
        return cluster.rank, episode

    def run_investigation(cluster, identifier: str) -> Episode:
        seeds = ideate(cluster) if investigate_config.ideation.samples else None
        task = {
            "case_id": case_id,
            "snapshot_id": intel.workspace.snapshot.id,
            "plan_id": plan.id,
            "cluster": cluster.handle,
            "budget_tokens": budgets[cluster.handle],
        }
        if case_pool is not None:
            task["budget_pool"] = case_pool.limit
        env = InvestigateEnv(
            intel,
            plan,
            cluster.handle,
            budgets[cluster.handle],
            coverage=investigate_config.coverage,
            seed_candidates=seeds,
            prompt=investigate_config.prompt,
            reporting=investigate_config.reporting,
            language=config.language,
            lock=lock,
            max_output_tokens=investigate_config.tool_output_tokens,
            task=task,
            examples=examples,
            pool=case_pool,
        )
        try:
            episode = run_episode(env, policy, investigate_config.loop, episode_id=identifier)
        except Exception as exc:  # keep the other clusters' work
            episode = Episode(
                id=identifier,
                role=env.role,
                task=env.task,
                policy=policy.describe(),
                prompt_version="",
                tools_version="",
                tools=[],
                budget_tokens=budgets[cluster.handle],
                context_window=investigate_config.loop.context_window,
                termination="error",
                error=f"{type(exc).__name__}: {exc}",
                findings=[f.model_dump(mode="json") for f in env.findings],
            )
        finally:
            env.close()
        return episode

    with ThreadPoolExecutor(max_workers=max(1, len(clusters))) as pool:
        results = list(pool.map(investigate, clusters))
    results.sort(key=lambda item: item[0])
    comments, filtered, usage = postprocess(
        results, intel.workspace.snapshot.changes, policy, config.postprocess,
        store=store, run_id=run_id, case_id=case_id)
    for _, episode in results:
        usage = usage + episode.usage
    for episode in listing:
        usage = usage + episode.usage
    summaries = [
        EpisodeSummary(
            id=episode.id,
            cluster=episode.task.get("cluster", ""),
            rank=rank,
            budget_tokens=episode.budget_tokens,
            termination=episode.termination,
            steps=len(episode.steps),
            findings=len(episode.findings),
            usage=episode.usage,
            error=episode.error,
        )
        for rank, episode in results
    ]
    return CaseReview(
        run_id=run_id,
        case_id=case_id,
        snapshot_id=intel.workspace.snapshot.id,
        plan_id=plan.id,
        policy=policy.describe(),
        config=config,
        episodes=summaries,
        comments=comments,
        usage=usage,
        duration_s=round(time.monotonic() - started, 1),
        errors=[f"{s.cluster}: {s.error}" for s in summaries if s.error],
        filtered=filtered,
        budget_pool=None if case_pool is None else {
            "limit": case_pool.limit, "used": case_pool.used, "resumed": resumed},
        focus=focused,
    )
