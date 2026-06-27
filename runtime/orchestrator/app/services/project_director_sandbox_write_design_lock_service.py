"""Controlled sandbox write design-lock service for Project Director P21-B."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_write_design_lock import (
    ProjectDirectorSandboxWriteDesignLockResult,
    SandboxWriteDesignLockMode,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_write_execution_service import (
    P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
)


P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL = (
    "p21_b_sandbox_write_design_lock"
)
P21_SANDBOX_WRITE_EXECUTION_ACTION_TYPE = "p21_sandbox_write_execution_record"

REQUIRED_PRECONDITIONS = [
    "p17_programmer_no_write_execution_required",
    "p20_policy_only_preflight_passed_required",
    "p21_sandbox_write_execution_required",
    "operation_intent_preserved_required",
    "source_task_message_binding_required",
    "user_confirmation_required",
    "controlled_sandbox_write_separate_enablement_required",
    "rollback_snapshot_design_required_before_real_write",
    "readonly_reviewer_required_after_real_diff",
]

ALLOWED_FUTURE_WRITE_SCOPE = [
    "future write may only target isolated sandbox/worktree",
    "future write may only use P20 accepted_operations",
    "future write may only support create/update initially",
    "future write must not target main worktree",
    "future write must not perform product runtime Git operations",
]

FORBIDDEN_RUNTIME_ACTIONS = [
    "no_product_runtime_git_write",
    "no_main_worktree_write",
    "no_unapproved_path_write",
    "no_delete_operation",
    "no_target_file_content_read_in_design_lock",
    "no_real_diff_generation_in_design_lock",
    "no_worker_dispatch",
    "no_task_creation",
    "no_run_creation",
    "no_executor_start",
    "no_automatic_commit",
    "no_push",
    "no_pr",
    "no_merge",
]

FAILURE_STATES = [
    "source_message_missing",
    "source_message_is_not_p21_sandbox_write_execution",
    "source_task_missing",
    "source_task_not_bound_to_p21_execution",
    "user_confirmation_required",
    "source_execution_not_planned_or_simulated",
    "source_execution_not_no_write",
    "operation_intent_missing",
    "controlled_sandbox_write_not_enabled_in_design_lock",
    "real_write_not_allowed_in_design_lock",
]


@dataclass(frozen=True, slots=True)
class ConfirmedSandboxWriteDesignLock:
    """P21-B design-lock result and optional persisted message."""

    result: ProjectDirectorSandboxWriteDesignLockResult
    message: ProjectDirectorMessage | None


class ProjectDirectorSandboxWriteDesignLockService:
    """Lock future controlled sandbox write design requirements without writes."""

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

    def confirm_design_lock(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        design_lock_mode: SandboxWriteDesignLockMode = "dry_run",
    ) -> ConfirmedSandboxWriteDesignLock:
        """Build and, when locked, persist one design-lock message."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("sandbox write design lock repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        source_message = self._message_repository.get_by_id(source_message_id)

        result = self.build_design_lock_from_sources(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            design_lock_mode=design_lock_mode,
        )
        if result.design_lock_status == "blocked":
            return ConfirmedSandboxWriteDesignLock(result=result, message=None)

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已生成 P21-B controlled sandbox write 设计锁定结果。"
                    "这只是 controlled sandbox write 设计锁定，不是文件写入，"
                    "不是 worktree 创建，不是 patch 应用，不是 Git 写入；"
                    "AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_write_design_lock",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL,
                suggested_actions=[self._design_lock_action(result)],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.LOW,
                forbidden_actions_detected=list(FORBIDDEN_RUNTIME_ACTIONS),
            )
        )
        self._message_repository.commit()
        return ConfirmedSandboxWriteDesignLock(result=result, message=message)

    def build_design_lock_from_sources(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        design_lock_mode: SandboxWriteDesignLockMode = "dry_run",
    ) -> ProjectDirectorSandboxWriteDesignLockResult:
        """Build a design-lock result without reading files or generating diffs."""

        blocked_reasons: list[str] = []
        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        if source_message is None:
            blocked_reasons.append("source_message_missing")

        p21_action: dict[str, Any] | None = None
        source_execution_status: str | None = None
        source_execution_mode: str | None = None
        source_execution_message_bound = False
        source_operation_intent_preserved = False

        if source_message is not None:
            if source_message.session_id != session_id:
                blocked_reasons.append("source_message_not_in_session")
            if (
                source_message.source_detail
                != P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL
            ):
                blocked_reasons.append(
                    "source_message_is_not_p21_sandbox_write_execution"
                )
            p21_action = self._first_p21_execution_action(source_message)
            if p21_action is None:
                blocked_reasons.append("p21_sandbox_write_execution_record_missing")

        if source_task is not None and not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_is_not_p12_safe_dry_run")

        if source_task is not None and source_message is not None:
            if not self._source_message_binds_task(source_message, source_task):
                blocked_reasons.append("source_task_not_bound_to_p21_execution")
            else:
                source_execution_message_bound = (
                    source_message.session_id == session_id
                    and source_message.source_detail
                    == P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL
                )

        if p21_action is not None:
            source_execution_status = self._as_optional_str(
                p21_action.get("execution_status")
            )
            source_execution_mode = self._as_optional_str(
                p21_action.get("execution_mode")
            )
            source_operation_intent_preserved = (
                self._operation_intent_preserved(
                    p21_action.get("operation_results")
                )
            )

            if source_execution_status not in ("planned", "simulated"):
                blocked_reasons.append("source_execution_not_planned_or_simulated")
            if p21_action.get("no_write_execution") is not True:
                blocked_reasons.append("source_execution_not_no_write")
            if p21_action.get("controlled_sandbox_write_enabled") is not False:
                blocked_reasons.append(
                    "controlled_sandbox_write_not_enabled_in_design_lock"
                )
            if self._any_runtime_write_flag_enabled(p21_action):
                blocked_reasons.append("real_write_not_allowed_in_design_lock")
            if not source_operation_intent_preserved:
                blocked_reasons.append("operation_intent_missing")

        blocked_reasons = self._dedupe(blocked_reasons)
        locked = not blocked_reasons
        return ProjectDirectorSandboxWriteDesignLockResult(
            design_lock_status="locked" if locked else "blocked",
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            design_lock_mode=design_lock_mode,
            source_execution_status=source_execution_status,
            source_execution_mode=source_execution_mode,
            source_execution_message_bound=source_execution_message_bound,
            source_operation_intent_preserved=source_operation_intent_preserved,
            controlled_sandbox_write_design_locked=locked,
            required_preconditions=list(REQUIRED_PRECONDITIONS),
            allowed_future_write_scope=list(ALLOWED_FUTURE_WRITE_SCOPE),
            forbidden_runtime_actions=list(FORBIDDEN_RUNTIME_ACTIONS),
            failure_states=list(FAILURE_STATES),
            design_lock_summary=self._design_lock_summary(locked=locked),
            recommended_next_step=(
                "Mimocode should add targeted P21-B tests/smoke evidence next; "
                "this design lock does not enable controlled sandbox writes."
            ),
            blocked_reasons=blocked_reasons,
            risks=[
                "design lock must not be interpreted as write enablement",
                "future writes still require isolated sandbox/worktree design",
                "product runtime Git writes remain forbidden",
            ],
            unknowns=[
                "rollback snapshot design is not implemented by this step",
                "real diff generation remains out of scope",
                "readonly reviewer handoff after a real diff remains future work",
            ],
        )

    @staticmethod
    def _is_safe_dry_run_task(task: Task) -> bool:
        criteria = set(task.acceptance_criteria)
        return (
            task.source_draft_id is not None
            and task.source_draft_id.startswith("p12-")
            and "SAFE DRY-RUN TASK DISPATCH ONLY" in task.input_summary
            and "safe_dry_run_task=true" in criteria
            and "worker_simulate_required=true" in criteria
            and "product_runtime_git_write_allowed=false" in criteria
            and "native_executor_started=false" in criteria
            and "codex_started=false" in criteria
            and "claude_code_started=false" in criteria
        )

    @staticmethod
    def _source_message_binds_task(
        source_message: ProjectDirectorMessage,
        source_task: Task,
    ) -> bool:
        if source_message.related_task_id == source_task.id:
            return True

        for action in source_message.suggested_actions:
            if not isinstance(action, dict):
                continue
            if action.get("type") != P21_SANDBOX_WRITE_EXECUTION_ACTION_TYPE:
                continue
            if action.get("source_task_id") == str(source_task.id):
                return True

        return False

    @staticmethod
    def _first_p21_execution_action(
        source_message: ProjectDirectorMessage,
    ) -> dict[str, Any] | None:
        if not source_message.suggested_actions:
            return None
        first_action = source_message.suggested_actions[0]
        if not isinstance(first_action, dict):
            return None
        if first_action.get("type") != P21_SANDBOX_WRITE_EXECUTION_ACTION_TYPE:
            return None
        return first_action

    @staticmethod
    def _operation_intent_preserved(value: Any) -> bool:
        if not isinstance(value, list) or not value:
            return False
        for item in value:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            operation = item.get("operation")
            if not isinstance(path, str) or not path.strip():
                continue
            if operation in ("create", "update", "p20_preflight_accepted_path"):
                return True
        return False

    @staticmethod
    def _any_runtime_write_flag_enabled(action: dict[str, Any]) -> bool:
        runtime_write_flags = (
            "sandbox_write_allowed",
            "product_runtime_git_write_allowed",
            "main_worktree_write_allowed",
            "worktree_write_allowed",
            "file_write_allowed",
            "actual_patch_applied",
            "real_code_modified",
            "git_write_performed",
            "native_executor_started",
            "codex_started",
            "claude_code_started",
            "worker_started",
            "task_created",
            "run_created",
            "worktree_created",
            "worktree_cleaned_up",
            "rollback_snapshot_created",
            "cleanup_required",
        )
        return any(action.get(flag) is True for flag in runtime_write_flags)

    @staticmethod
    def _design_lock_summary(*, locked: bool) -> str:
        if not locked:
            return (
                "P21-B controlled sandbox write design lock was blocked before "
                "any file read, diff generation, worktree, executor, Worker, "
                "Task, Run, or Git write side effect."
            )
        return (
            "P21-B controlled sandbox write design lock is recorded for review "
            "only. It preserves required preconditions and future scope while "
            "leaving all write, executor, Worker, Task, Run, worktree, rollback, "
            "and Git permissions disabled."
        )

    @staticmethod
    def _design_lock_action(
        result: ProjectDirectorSandboxWriteDesignLockResult,
    ) -> dict[str, Any]:
        return {
            "type": "p21_b_sandbox_write_design_lock_record",
            "design_lock_status": result.design_lock_status,
            "source_task_id": (
                str(result.source_task_id)
                if result.source_task_id is not None
                else None
            ),
            "source_message_id": (
                str(result.source_message_id)
                if result.source_message_id is not None
                else None
            ),
            "design_lock_mode": result.design_lock_mode,
            "source_execution_status": result.source_execution_status,
            "source_execution_mode": result.source_execution_mode,
            "source_execution_message_bound": result.source_execution_message_bound,
            "source_operation_intent_preserved": (
                result.source_operation_intent_preserved
            ),
            "controlled_sandbox_write_design_locked": (
                result.controlled_sandbox_write_design_locked
            ),
            "controlled_sandbox_write_enabled": False,
            "sandbox_write_allowed": False,
            "product_runtime_git_write_allowed": False,
            "main_worktree_write_allowed": False,
            "worktree_write_allowed": False,
            "file_write_allowed": False,
            "actual_patch_applied": False,
            "real_code_modified": False,
            "git_write_performed": False,
            "native_executor_started": False,
            "codex_started": False,
            "claude_code_started": False,
            "worker_started": False,
            "task_created": False,
            "run_created": False,
            "worktree_created": False,
            "worktree_cleaned_up": False,
            "rollback_snapshot_created": False,
            "cleanup_required": False,
            "required_preconditions": list(result.required_preconditions),
            "allowed_future_write_scope": list(result.allowed_future_write_scope),
            "forbidden_runtime_actions": list(result.forbidden_runtime_actions),
            "failure_states": list(result.failure_states),
            "design_lock_summary": result.design_lock_summary,
            "recommended_next_step": result.recommended_next_step,
            "ai_project_director_total_loop": "Partial",
            "blocked_reasons": list(result.blocked_reasons),
            "risks": list(result.risks),
            "unknowns": list(result.unknowns),
        }

    @staticmethod
    def _as_optional_str(value: Any) -> str | None:
        return value if isinstance(value, str) else None

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            result.append(value)
            seen.add(value)
        return result


__all__ = (
    "ConfirmedSandboxWriteDesignLock",
    "P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL",
    "ProjectDirectorSandboxWriteDesignLockService",
)
