"""Project Director evidence-to-agent dry-run orchestration service."""

from __future__ import annotations

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


class ProjectDirectorEvidenceToAgentDryRunService:
    """Run the P10 evidence-to-agent chain without starting executors."""

    def __init__(self, *, repo_root: Path) -> None:
        self._repo_root = repo_root.resolve()

    def run(self, *, user_goal: str) -> dict[str, Any]:
        trimmed_goal = user_goal.strip()
        if not trimmed_goal:
            raise ValueError("user_goal must not be empty or whitespace-only")

        evidence_pack = ProjectDirectorRepoEvidenceService(
            repo_root=self._repo_root
        ).build_evidence_pack(goal_text=trimmed_goal)
        task_composition = ProjectDirectorEvidenceTaskComposerService().compose_tasks(
            evidence_pack=evidence_pack,
            user_goal=trimmed_goal,
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
                task_composition.source_evidence_pack_id
                == evidence_pack.evidence_pack_id
                and task_composition.composition_status == "composed"
            ),
            "composed_tasks_count": len(task_composition.composed_tasks),
            "every_task_has_evidence_refs": every_task_has_evidence_refs,
            "every_task_has_allowed_forbidden_files": (
                every_task_has_allowed_forbidden_files
            ),
            "every_task_has_targeted_tests": every_task_has_targeted_tests,
            "programmer_assignment_created": assignment.programmer_agent is not None,
            "reviewer_assignment_created": assignment.reviewer_agent is not None,
            "reviewer_readonly": assignment.reviewer_readonly,
            "director_permanent_executor": assignment.director_permanent_executor,
            "native_executor_started": False,
            "codex_started": False,
            "claude_code_started": False,
            "worker_started": False,
            "real_task_created": False,
            "product_runtime_git_write_allowed": False,
            "frontend_required": False,
            "ai_project_director_total_loop": "Partial",
            "blocked_reasons": blocked_reasons,
            "risks": sorted(set([*evidence_pack.risks, *assignment.risks])),
            "unknowns": sorted(set([*evidence_pack.unknowns, *assignment.unknowns])),
        }
