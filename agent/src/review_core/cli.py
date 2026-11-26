from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from review_core.common import ReviewCoreError
from review_core.intel import CodeIntel
from review_core.intel.tools import Tools
from review_core.triage import Triage, TriageConfig
from review_core.workspace import Workspace


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Immutable code review snapshots, intelligence and triage"
    )
    root.add_argument(
        "--state-dir",
        type=Path,
        required=True,
        help="Private persistent object/cache/run directory",
    )
    commands = root.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser(
        "snapshot", help="Import already-fetched local Git objects at fixed SHAs"
    )
    snapshot.add_argument("--repository", type=Path, required=True)
    snapshot.add_argument("--repository-id", required=True)
    snapshot.add_argument("--base", required=True)
    snapshot.add_argument("--head", required=True)
    snapshot.add_argument("--start")
    snapshot.add_argument("--previous")
    snapshot.add_argument("--merge-request")
    snapshot.add_argument("--diff-version")
    tool = commands.add_parser("tool", help="Execute a bounded, evidence-recording tool")
    tool.add_argument("--snapshot", required=True)
    tool.add_argument("name", choices=[schema["function"]["name"] for schema in Tools.schemas()])
    tool.add_argument("--arguments", default="{}", help="JSON tool arguments")
    tool.add_argument("--plan", help="triage plan id, to accept unit and cluster handles")
    triage = commands.add_parser(
        "triage", help="Plan review clusters, seeds and budgets (deterministic, no model)"
    )
    triage.add_argument("--snapshot", required=True)
    triage.add_argument("--config", type=Path, help="JSON TriageConfig overrides")
    plan = commands.add_parser("plan", help="Return a stored triage plan")
    plan.add_argument("--snapshot", required=True)
    plan.add_argument("--id", required=True)
    brief = commands.add_parser("brief", help="Render one cluster of a stored plan for an agent")
    brief.add_argument("--snapshot", required=True)
    brief.add_argument("--id", required=True)
    brief.add_argument("--cluster", required=True, help="cluster handle (C1) or id")
    evidence = commands.add_parser("evidence", help="Read a recorded source or tool result")
    evidence.add_argument("--snapshot", required=True)
    evidence.add_argument("--id", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "snapshot":
            workspace = Workspace.create(
                args.repository,
                args.state_dir,
                args.repository_id,
                args.base,
                args.head,
                start_sha=args.start,
                previous_sha=args.previous,
                merge_request=args.merge_request,
                diff_version=args.diff_version,
            )
            print(workspace.snapshot.model_dump_json(indent=2))
            return 0
        workspace = Workspace.load(args.state_dir, args.snapshot)
        intel = CodeIntel(workspace)
        if args.command == "tool":
            plan = Triage(intel).load(args.plan) if args.plan else None
            result = Tools(intel, plan).call(args.name, **json.loads(args.arguments))
            print(result.model_dump_json(indent=2))
            return 2 if result.error else 0
        if args.command == "evidence":
            print(json.dumps(Tools(intel).evidence(args.id), indent=2, ensure_ascii=True))
            return 0
        if args.command == "brief":
            triage = Triage(intel)
            print(triage.brief(triage.load(args.id), args.cluster))
            return 0
        if args.command == "plan":
            print(Triage(intel).load(args.id).model_dump_json(indent=2))
            return 0
        config = TriageConfig.model_validate_json(args.config.read_text()) if args.config else None
        print(Triage(intel, config).plan().model_dump_json(indent=2))
        return 0
    except (ReviewCoreError, ValidationError, ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
