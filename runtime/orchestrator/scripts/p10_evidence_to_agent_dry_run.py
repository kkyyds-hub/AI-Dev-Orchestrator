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

from app.services.project_director_agent_assignment_service import (
    ProjectDirectorAgentAssignmentService,
)
from app.services.project_director_evidence_task_composer_service import (
    ProjectDirectorEvidenceTaskComposerService,
)
from app.services.project_director_repo_evidence_service import (
    ProjectDirectorRepoEvidenceService,
)


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = RUNTIME_ROOT.parents[1]


def run_dry_run(*, repo_root: Path, user_goal: str) -> dict[str, Any]:
    evidence_pack = ProjectDirectorRepoEvidenceService(
        repo_root=repo_root
    ).build_evidence_pack(goal_text=user_goal)
    task_composition = ProjectDirectorEvidenceTaskComposerService().compose_tasks(
        evidence_pack=evidence_pack,
        user_goal=user_goal,
    )
    assignment = ProjectDirectorAgentAssignmentService().assign_agents(
        task_composition=task_composition
    )

    every_task_has_evidence_refs = all(
        bool(task.evidence_refs) for task in task_composition.composed_tasks
    )
    every_task_has_allowed_forbidden_files = all(
        bool(task.allowed_files) and bool(task.forbidden_files)
        for task in task_composition.composed_tasks
    )
    every_task_has_targeted_tests = all(
        bool(task.targeted_tests) for task in task_composition.composed_tasks
    )
    blocked_reasons = [
        *task_composition.blocked_reasons,
        *assignment.blocked_reasons,
    ]
    required_pass = (
        bool(evidence_pack.evidence_refs),
        task_composition.composition_status == "composed",
        bool(task_composition.composed_tasks),
        every_task_has_evidence_refs,
        every_task_has_allowed_forbidden_files,
        every_task_has_targeted_tests,
        assignment.assignment_status == "assigned",
        assignment.programmer_agent is not None,
        assignment.reviewer_agent is not None,
        assignment.reviewer_readonly is True,
        assignment.director_permanent_executor is False,
        assignment.native_executor_started is False,
        assignment.codex_started is False,
        assignment.claude_code_started is False,
        assignment.product_runtime_git_write_allowed is False,
        assignment.frontend_required is False,
        not blocked_reasons,
    )

    return {
        "dry_run_status": "passed" if all(required_pass) else "blocked",
        "origin_main_commit": evidence_pack.origin_main_commit,
        "evidence_pack_created": bool(evidence_pack.evidence_pack_id),
        "evidence_pack_id": evidence_pack.evidence_pack_id,
        "evidence_refs_count": len(evidence_pack.evidence_refs),
        "task_composer_consumed_evidence": (
            task_composition.source_evidence_pack_id == evidence_pack.evidence_pack_id
            and task_composition.composition_status == "composed"
        ),
        "composed_tasks_count": len(task_composition.composed_tasks),
        "every_task_has_evidence_refs": every_task_has_evidence_refs,
        "every_task_has_allowed_forbidden_files": every_task_has_allowed_forbidden_files,
        "every_task_has_targeted_tests": every_task_has_targeted_tests,
        "programmer_assignment_created": assignment.programmer_agent is not None,
        "reviewer_assignment_created": assignment.reviewer_agent is not None,
        "reviewer_readonly": assignment.reviewer_readonly,
        "director_permanent_executor": assignment.director_permanent_executor,
        "native_executor_started": False,
        "codex_started": False,
        "claude_code_started": False,
        "product_runtime_git_write_allowed": False,
        "frontend_required": False,
        "ai_project_director_total_loop": "Partial",
        "blocked_reasons": blocked_reasons,
        "risks": sorted(set([*evidence_pack.risks, *assignment.risks])),
        "unknowns": sorted(set([*evidence_pack.unknowns, *assignment.unknowns])),
    }


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
