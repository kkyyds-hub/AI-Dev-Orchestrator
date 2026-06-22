"""Safe Project Director dry-run task dispatch planning service."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.domain.project_director_dry_run_task_dispatch import (
    ProjectDirectorDryRunTaskDispatchPlan,
)
from app.domain.project_director_message import ProjectDirectorMessage


P11_DRY_RUN_SOURCE_DETAIL = "p11_evidence_to_agent_session_dry_run"

_DISPATCH_ALLOWED_FILES = [
    "runtime/orchestrator/app/domain/project_director_dry_run_task_dispatch.py",
    "runtime/orchestrator/app/services/project_director_dry_run_task_dispatch_service.py",
    "runtime/orchestrator/app/api/routes/project_director.py",
    "runtime/orchestrator/tests/test_project_director_dry_run_task_dispatch_*.py",
]

_DISPATCH_FORBIDDEN_FILES = [
    "apps/web/**",
    "docs/superpowers/**",
    "runtime/orchestrator/app/external_executors/**",
    "runtime/orchestrator/app/services/worktree_create_service.py",
    "runtime/orchestrator/app/services/worktree_cleanup_service.py",
    "runtime/orchestrator/app/services/worktree_write_command_runner.py",
    "migrations/**",
]

_DISPATCH_TARGETED_TESTS = [
    "tests/test_project_director_dry_run_task_dispatch_contract.py",
    "tests/test_project_director_dry_run_task_dispatch_api.py",
    "tests/test_project_director_dry_run_task_dispatch_smoke.py",
]


class ProjectDirectorDryRunTaskDispatchService:
    """Build safe task dispatch drafts from P11 dry-run evidence messages."""

    def build_plan_from_message(
        self,
        *,
        session_id: UUID,
        source_message: ProjectDirectorMessage,
        user_goal: str | None = None,
    ) -> ProjectDirectorDryRunTaskDispatchPlan:
        """Build a confirmation-required dispatch plan without creating a task."""

        blocked_reasons: list[str] = []
        if source_message.session_id != session_id:
            blocked_reasons.append("source_message_not_in_session")
        if source_message.source_detail != P11_DRY_RUN_SOURCE_DETAIL:
            blocked_reasons.append("source_message_is_not_p11_dry_run")

        action = self._extract_dry_run_action(source_message.suggested_actions)
        if action is None:
            blocked_reasons.append("source_message_missing_dry_run_action")
            action = {}

        evidence_pack_id = self._string_or_none(action.get("evidence_pack_id"))
        if evidence_pack_id is None:
            blocked_reasons.append("evidence_pack_id_missing")
        if action.get("dry_run_status") not in (None, "passed"):
            blocked_reasons.append("source_dry_run_not_passed")

        normalized_goal = (user_goal or source_message.content).strip()
        if not normalized_goal:
            normalized_goal = "Confirmed Project Director safe dry-run task dispatch"

        task_title = self._build_task_title(evidence_pack_id)
        task_input_summary = self._build_task_input_summary(
            source_message_id=source_message.id,
            evidence_pack_id=evidence_pack_id,
            user_goal=normalized_goal,
        )

        return ProjectDirectorDryRunTaskDispatchPlan(
            session_id=session_id,
            source_message_id=source_message.id,
            evidence_pack_id=evidence_pack_id,
            user_goal=normalized_goal,
            task_title=task_title,
            task_input_summary=task_input_summary,
            allowed_files=list(_DISPATCH_ALLOWED_FILES),
            forbidden_files=list(_DISPATCH_FORBIDDEN_FILES),
            targeted_tests=list(_DISPATCH_TARGETED_TESTS),
            dispatch_status=(
                "blocked" if blocked_reasons else "ready_for_confirmation"
            ),
            blocked_reasons=blocked_reasons,
            risks=[
                "safe dry-run task must remain simulate-only",
                "confirmation does not authorize product runtime Git writes",
            ],
            unknowns=[
                "P11 summary does not prove product-grade long-running executor lifecycle",
            ],
        )

    def build_plan_from_dry_run_summary(
        self,
        *,
        session_id: UUID,
        source_message_id: UUID,
        dry_run_summary: dict[str, Any],
        user_goal: str,
    ) -> ProjectDirectorDryRunTaskDispatchPlan:
        """Build the same safe plan from a P11 dry-run summary object."""

        evidence_pack_id = self._string_or_none(dry_run_summary.get("evidence_pack_id"))
        blocked_reasons: list[str] = []
        if evidence_pack_id is None:
            blocked_reasons.append("evidence_pack_id_missing")
        if dry_run_summary.get("dry_run_status") != "passed":
            blocked_reasons.append("source_dry_run_not_passed")

        normalized_goal = user_goal.strip()
        if not normalized_goal:
            blocked_reasons.append("user_goal_missing")
            normalized_goal = "Confirmed Project Director safe dry-run task dispatch"

        return ProjectDirectorDryRunTaskDispatchPlan(
            session_id=session_id,
            source_message_id=source_message_id,
            evidence_pack_id=evidence_pack_id,
            user_goal=normalized_goal,
            task_title=self._build_task_title(evidence_pack_id),
            task_input_summary=self._build_task_input_summary(
                source_message_id=source_message_id,
                evidence_pack_id=evidence_pack_id,
                user_goal=normalized_goal,
            ),
            allowed_files=list(_DISPATCH_ALLOWED_FILES),
            forbidden_files=list(_DISPATCH_FORBIDDEN_FILES),
            targeted_tests=list(_DISPATCH_TARGETED_TESTS),
            dispatch_status=(
                "blocked" if blocked_reasons else "ready_for_confirmation"
            ),
            blocked_reasons=blocked_reasons,
            risks=[
                "safe dry-run task must remain simulate-only",
                "confirmation does not authorize product runtime Git writes",
            ],
            unknowns=[
                "P11 summary does not prove product-grade long-running executor lifecycle",
            ],
        )

    @staticmethod
    def _extract_dry_run_action(actions: list[dict]) -> dict[str, Any] | None:
        for action in actions:
            if not isinstance(action, dict):
                continue
            if action.get("type") == "evidence_to_agent_dry_run_record":
                return action
        return None

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _build_task_title(evidence_pack_id: str | None) -> str:
        suffix = evidence_pack_id or "missing-evidence-pack"
        return f"Safe dry-run task dispatch for {suffix}"[:200]

    @staticmethod
    def _build_task_input_summary(
        *,
        source_message_id: UUID,
        evidence_pack_id: str | None,
        user_goal: str,
    ) -> str:
        return (
            "SAFE DRY-RUN TASK DISPATCH ONLY. "
            f"source_message_id={source_message_id}; "
            f"evidence_pack_id={evidence_pack_id or 'missing'}; "
            f"user_goal={user_goal[:500]}; "
            "worker_simulate_required=true; "
            "product_runtime_git_write_allowed=false; "
            "native_executor_started=false; codex_started=false; "
            "claude_code_started=false; "
            "AI Project Director total loop remains Partial."
        )[:2000]
