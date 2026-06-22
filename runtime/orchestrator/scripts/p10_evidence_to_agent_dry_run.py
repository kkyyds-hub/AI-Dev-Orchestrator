"""P10-D evidence-to-agent dry-run orchestration.

This script proves the safe Project Director chain:
user goal -> readonly repo evidence -> evidence-grounded tasks ->
programmer/reviewer assignment. It does not start Codex, Claude Code, workers,
native executors, or product runtime Git writes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.project_director_evidence_to_agent_dry_run_service import (
    ProjectDirectorEvidenceToAgentDryRunService,
)


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = RUNTIME_ROOT.parents[1]


def run_dry_run(*, repo_root: Path, user_goal: str) -> dict[str, Any]:
    return ProjectDirectorEvidenceToAgentDryRunService(repo_root=repo_root).run(
        user_goal=user_goal
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON summary.")
    parser.add_argument(
        "--goal",
        default="P10-D evidence-to-agent dry-run chain",
        help="User goal to pass through the dry-run chain.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = run_dry_run(repo_root=REPO_ROOT, user_goal=args.goal)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"P10-D evidence-to-agent dry-run: {summary['dry_run_status']}")

    return 0 if summary["dry_run_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
