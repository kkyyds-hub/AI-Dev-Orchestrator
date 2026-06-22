"""Safe Project Director dry-run task dispatch planning service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.project_director_dry_run_task_dispatch import (
    ProjectDirectorDryRunTaskDispatchPlan,
    ProjectDirectorDryRunTaskDispatchResult,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.task import Task, TaskPriority, TaskRiskLevel
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository


P11_DRY_RUN_SOURCE_DETAIL = "p11_evidence_to_agent_session_dry_run"
P12_DISPATCH_SOURCE_DETAIL = "p12_dry_run_task_dispatch"

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


@dataclass(frozen=True, slots=True)
class ConfirmedDryRunTaskDispatch:
    """Created task and session message for one confirmed P12 dispatch."""

    result: ProjectDirectorDryRunTaskDispatchResult
    task: Task | None
    message: ProjectDirectorMessage | None


class ProjectDirectorDryRunTaskDispatchService:
    """Build safe task dispatch drafts from P11 dry-run evidence messages."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository | None = None,
        message_repository: ProjectDirectorMessageRepository | None = None,
        task_repository: TaskRepository | None = None,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository

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

    def confirm_dispatch(
        self,
        *,
        session_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
    ) -> ConfirmedDryRunTaskDispatch:
        """Create one safe dry-run task from a confirmed P11 session message."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("dispatch repositories are required")
        if not user_confirmed:
            raise ValueError("user_confirmation_required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_message = self._message_repository.get_by_id(source_message_id)
        if source_message is None:
            raise ValueError(f"Project Director message {source_message_id} not found")
        if source_message.session_id != session_id:
            raise ValueError("source_message_not_in_session")

        plan = self.build_plan_from_message(
            session_id=session_id,
            source_message=source_message,
            user_goal=session_obj.goal_text,
        )
        if plan.blocked_reasons:
            raise ValueError(";".join(plan.blocked_reasons))

        task = self._task_repository.create(
            Task(
                project_id=session_obj.project_id,
                title=plan.task_title,
                input_summary=plan.task_input_summary,
                priority=TaskPriority.NORMAL,
                acceptance_criteria=[
                    "safe_dry_run_task=true",
                    "worker_simulate_required=true",
                    "product_runtime_git_write_allowed=false",
                    "native_executor_started=false",
                    "codex_started=false",
                    "claude_code_started=false",
                    "AI Project Director total loop remains Partial",
                ],
                risk_level=TaskRiskLevel.LOW,
                source_draft_id=f"p12-{source_message_id}",
            )
        )

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已根据确认创建 safe dry-run Task。该 Task 仅用于 Worker "
                    "simulate，不代表真实代码执行、Git 写入或外部 executor 启动；"
                    "AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="dry_run_task_dispatch",
                related_project_id=session_obj.project_id,
                related_task_id=task.id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P12_DISPATCH_SOURCE_DETAIL,
                suggested_actions=[
                    {
                        "type": "p12_dry_run_task_dispatch_record",
                        "source_message_id": str(source_message_id),
                        "created_task_id": str(task.id),
                        "evidence_pack_id": plan.evidence_pack_id,
                        "safe_dry_run_task": True,
                        "worker_simulate_required": True,
                        "product_runtime_git_write_allowed": False,
                        "frontend_required": False,
                        "native_executor_started": False,
                        "codex_started": False,
                        "claude_code_started": False,
                        "worker_started": False,
                        "ai_project_director_total_loop": "Partial",
                    }
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.LOW,
                forbidden_actions_detected=[
                    "no_product_runtime_git_write",
                    "no_worker_dispatch_in_dispatch_api",
                    "no_executor_start",
                    "no_run_creation_in_dispatch_api",
                ],
            )
        )
        self._message_repository.commit()

        result = ProjectDirectorDryRunTaskDispatchResult(
            dispatch_status="dispatched",
            session_id=session_id,
            source_message_id=source_message_id,
            created_task_id=task.id,
            evidence_pack_id=plan.evidence_pack_id,
            message_bound=True,
            risks=plan.risks,
            unknowns=plan.unknowns,
        )
        return ConfirmedDryRunTaskDispatch(
            result=result,
            task=task,
            message=message,
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
