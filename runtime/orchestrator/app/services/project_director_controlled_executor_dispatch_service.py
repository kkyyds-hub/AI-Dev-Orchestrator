"""Controlled Project Director executor dispatch pilot service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.project_director_controlled_executor_dispatch import (
    LaunchMode,
    ProjectDirectorControlledExecutorDispatchPlan,
    ProjectDirectorControlledExecutorDispatchResult,
    ProjectDirectorControlledExecutorLifecycleResult,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository


P12_DISPATCH_SOURCE_DETAIL = "p12_dry_run_task_dispatch"
P12_WORKER_RESULT_SOURCE_DETAIL = "p12_dry_run_task_worker_result"
P13_DISPATCH_SOURCE_DETAIL = "p13_controlled_executor_dispatch"
P13_LIFECYCLE_RESULT_SOURCE_DETAIL = "p13_controlled_executor_lifecycle_result"

_P13_ALLOWED_FILES = [
    "runtime/orchestrator/app/domain/project_director_controlled_executor_dispatch.py",
    "runtime/orchestrator/app/services/project_director_controlled_executor_dispatch_service.py",
    "runtime/orchestrator/app/api/routes/project_director.py",
    "runtime/orchestrator/scripts/p13_project_director_controlled_executor_lifecycle_smoke.py",
    "runtime/orchestrator/tests/test_project_director_controlled_executor_dispatch_*.py",
    "runtime/orchestrator/tests/test_project_director_controlled_executor_lifecycle_smoke.py",
]

_P13_FORBIDDEN_FILES = [
    "apps/web/**",
    "docs/superpowers/**",
    "runtime/orchestrator/app/services/worktree_create_service.py",
    "runtime/orchestrator/app/services/worktree_cleanup_service.py",
    "runtime/orchestrator/app/services/worktree_write_command_runner.py",
    "migrations/**",
]

_P13_TARGETED_TESTS = [
    "tests/test_project_director_controlled_executor_dispatch_contract.py",
    "tests/test_project_director_controlled_executor_dispatch_api.py",
    "tests/test_project_director_controlled_executor_lifecycle_smoke.py",
]


@dataclass(frozen=True, slots=True)
class ConfirmedControlledExecutorDispatch:
    """Planned dispatch result and bound session message."""

    result: ProjectDirectorControlledExecutorDispatchResult
    message: ProjectDirectorMessage | None


class ProjectDirectorControlledExecutorDispatchService:
    """Plan and record controlled executor-backed pilot dispatches."""

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

    def build_plan_from_sources(
        self,
        *,
        session_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        requested_agent_role: str = "programmer",
        requested_executor: str = "codex",
        launch_mode: LaunchMode = "dry_run",
    ) -> ProjectDirectorControlledExecutorDispatchPlan:
        """Build a no-execution controlled dispatch plan from P12 evidence."""

        blocked_reasons: list[str] = []
        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        if source_message is None:
            blocked_reasons.append("source_message_missing")

        if source_message is not None:
            if source_message.session_id != session_id:
                blocked_reasons.append("source_message_not_in_session")
            if source_message.source_detail not in {
                P12_DISPATCH_SOURCE_DETAIL,
                P12_WORKER_RESULT_SOURCE_DETAIL,
            }:
                blocked_reasons.append("source_message_is_not_p12_dispatch")

        if source_task is not None and source_message is not None:
            if source_task.source_draft_id != f"p12-{source_message.id}":
                blocked_reasons.append("source_task_not_bound_to_source_message")
            if not self._is_safe_dry_run_task(source_task):
                blocked_reasons.append("source_task_is_not_safe_dry_run")

        if launch_mode == "controlled_smoke":
            blocked_reasons.append("controlled_smoke_not_enabled_in_api")

        return ProjectDirectorControlledExecutorDispatchPlan(
            session_id=session_id,
            source_task_id=source_task.id if source_task is not None else None,
            source_message_id=(
                source_message.id if source_message is not None else None
            ),
            user_confirmed=user_confirmed,
            requested_agent_role=requested_agent_role,  # type: ignore[arg-type]
            requested_executor=requested_executor,  # type: ignore[arg-type]
            launch_mode=launch_mode,
            dispatch_status="blocked" if blocked_reasons else "planned",
            blocked_reasons=blocked_reasons,
            risks=[
                "controlled executor pilot is not production Git write authorization",
                "dry_run API dispatch does not start Codex or Claude Code",
                "controlled smoke requires supervisor, timeout, termination, and cleanup",
            ],
            unknowns=[
                "production-safe long-running executor lifecycle is not fully proven",
            ],
        )

    def confirm_dispatch(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        requested_agent_role: str,
        requested_executor: str,
        launch_mode: LaunchMode = "dry_run",
    ) -> ConfirmedControlledExecutorDispatch:
        """Record one confirmed controlled executor dispatch intent."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("controlled dispatch repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        if source_task is None:
            raise ValueError(f"Task {source_task_id} not found")

        source_message = self._message_repository.get_by_id(source_message_id)
        if source_message is None:
            raise ValueError(f"Project Director message {source_message_id} not found")

        plan = self.build_plan_from_sources(
            session_id=session_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            requested_agent_role=requested_agent_role,
            requested_executor=requested_executor,
            launch_mode=launch_mode,
        )
        if plan.blocked_reasons:
            raise ValueError(";".join(plan.blocked_reasons))

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已记录 controlled executor lifecycle pilot dispatch intent。"
                    "默认 dry_run 不启动 executor、不创建 Run、不授权产品运行时 Git 写；"
                    "AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="controlled_executor_dispatch",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P13_DISPATCH_SOURCE_DETAIL,
                suggested_actions=[
                    {
                        "type": "p13_controlled_executor_dispatch_record",
                        "source_task_id": str(source_task_id),
                        "source_message_id": str(source_message_id),
                        "requested_agent_role": requested_agent_role,
                        "requested_executor": requested_executor,
                        "launch_mode": launch_mode,
                        "controlled_executor_pilot": True,
                        "executor_backed_agent": True,
                        "supervisor_required": True,
                        "auto_terminate_required": True,
                        "cleanup_required": True,
                        "product_runtime_git_write_allowed": False,
                        "worktree_write_allowed": False,
                        "frontend_required": False,
                        "native_executor_started": False,
                        "codex_started": False,
                        "claude_code_started": False,
                        "agent_session_bound": False,
                        "process_handle_id_present": False,
                        "supervisor_registered": False,
                        "supervisor_cleanup_done": False,
                        "run_created": False,
                        "ai_project_director_total_loop": "Partial",
                    }
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.LOW,
                forbidden_actions_detected=[
                    "no_product_runtime_git_write",
                    "no_worktree_write",
                    "no_executor_start_in_dry_run_api",
                    "no_worker_dispatch",
                    "no_run_creation_in_dispatch_api",
                ],
            )
        )
        self._message_repository.commit()

        result = self._result_from_plan(plan, message_bound=True)
        return ConfirmedControlledExecutorDispatch(result=result, message=message)

    def record_lifecycle_result(
        self,
        *,
        result: ProjectDirectorControlledExecutorLifecycleResult,
    ) -> ProjectDirectorMessage:
        """Bind one controlled lifecycle readback message to a session."""

        if self._session_repository is None or self._message_repository is None:
            raise ValueError("controlled dispatch repositories are required")
        session_obj = self._session_repository.get_by_id(result.session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {result.session_id} not found")

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=result.session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已记录 controlled executor lifecycle readback。该记录不代表"
                    "真实代码修改完成，也不授权产品运行时 Git 写；AI Project Director "
                    "总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=result.session_id
                ),
                intent="controlled_executor_lifecycle_result",
                related_project_id=session_obj.project_id,
                related_task_id=result.source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P13_LIFECYCLE_RESULT_SOURCE_DETAIL,
                suggested_actions=[
                    {
                        "type": "p13_controlled_executor_lifecycle_result_record",
                        "source_task_id": str(result.source_task_id),
                        "source_message_id": str(result.source_message_id),
                        "requested_agent_role": result.requested_agent_role,
                        "requested_executor": result.requested_executor,
                        "launch_mode": result.launch_mode,
                        "controlled_executor_pilot": True,
                        "executor_backed_agent": True,
                        "native_executor_started": result.native_executor_started,
                        "codex_started": result.codex_started,
                        "claude_code_started": result.claude_code_started,
                        "agent_session_bound": result.agent_session_bound,
                        "runtime_handle_id_present": result.runtime_handle_id_present,
                        "process_handle_id_present": result.process_handle_id_present,
                        "supervisor_required": True,
                        "supervisor_registered": result.supervisor_registered,
                        "auto_terminate_required": True,
                        "terminate_attempted": result.terminate_attempted,
                        "cleanup_required": True,
                        "supervisor_cleanup_done": result.supervisor_cleanup_done,
                        "product_runtime_git_write_allowed": False,
                        "worktree_write_allowed": False,
                        "frontend_required": False,
                        "run_created": result.run_created,
                        "real_code_modified": False,
                        "git_write_performed": False,
                        "ai_project_director_total_loop": "Partial",
                        "p9_production_safe_long_running_executor_lifecycle": (
                            result.p9_production_safe_long_running_executor_lifecycle
                        ),
                        "blocked_reasons": list(result.blocked_reasons),
                    }
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.LOW,
                forbidden_actions_detected=[
                    "no_product_runtime_git_write",
                    "no_worktree_write",
                    "no_real_code_modification_as_pass_condition",
                ],
            )
        )
        self._message_repository.commit()
        return message

    @staticmethod
    def _is_safe_dry_run_task(task: Task) -> bool:
        criteria = set(task.acceptance_criteria)
        summary = task.input_summary
        return (
            task.source_draft_id is not None
            and task.source_draft_id.startswith("p12-")
            and "SAFE DRY-RUN TASK DISPATCH ONLY" in summary
            and "safe_dry_run_task=true" in criteria
            and "worker_simulate_required=true" in criteria
            and "product_runtime_git_write_allowed=false" in criteria
            and "native_executor_started=false" in criteria
            and "codex_started=false" in criteria
            and "claude_code_started=false" in criteria
        )

    @staticmethod
    def _result_from_plan(
        plan: ProjectDirectorControlledExecutorDispatchPlan,
        *,
        message_bound: bool,
    ) -> ProjectDirectorControlledExecutorDispatchResult:
        data: dict[str, Any] = plan.model_dump()
        data["message_bound"] = message_bound
        return ProjectDirectorControlledExecutorDispatchResult(**data)


__all__ = (
    "ConfirmedControlledExecutorDispatch",
    "P13_DISPATCH_SOURCE_DETAIL",
    "P13_LIFECYCLE_RESULT_SOURCE_DETAIL",
    "ProjectDirectorControlledExecutorDispatchService",
)
