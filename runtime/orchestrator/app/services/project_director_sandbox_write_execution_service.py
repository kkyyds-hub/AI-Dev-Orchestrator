"""Dry-run/fake-write sandbox write execution service for Project Director P21-A."""

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
from app.domain.project_director_sandbox_write_execution import (
    ProjectDirectorSandboxWriteExecutionResult,
    ProjectDirectorSandboxWriteOperationResult,
    SandboxWriteExecutionMode,
    SandboxWriteOperationExecutionStatus,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_write_preflight_service import (
    P20_SANDBOX_WRITE_PREFLIGHT_SOURCE_DETAIL,
)


P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL = "p21_sandbox_write_execution"
P20_SANDBOX_WRITE_PREFLIGHT_ACTION_TYPE = "p20_sandbox_write_preflight_record"


@dataclass(frozen=True, slots=True)
class ConfirmedSandboxWriteExecution:
    """P21-A execution result and its persisted Project Director message."""

    result: ProjectDirectorSandboxWriteExecutionResult
    message: ProjectDirectorMessage | None


class ProjectDirectorSandboxWriteExecutionService:
    """Create P21-A sandbox write execution results without writing files."""

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

    def confirm_execution(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        execution_mode: SandboxWriteExecutionMode = "dry_run",
    ) -> ConfirmedSandboxWriteExecution:
        """Persist one no-write P21-A execution result message."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("sandbox write execution repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        if source_task is None:
            raise ValueError(f"Task {source_task_id} not found")

        source_message = self._message_repository.get_by_id(source_message_id)
        if source_message is None:
            raise ValueError(f"Project Director message {source_message_id} not found")

        result = self.build_execution_from_sources(
            session_id=session_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            execution_mode=execution_mode,
        )
        if result.blocked_reasons:
            raise ValueError(";".join(result.blocked_reasons))

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已生成 P21 sandbox write execution dry-run/fake-write "
                    "result。该结果不代表文件已写入，不创建 worktree，不应用 "
                    "patch，不授权产品运行时 Git 写；AI Project Director "
                    "总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_write_execution",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
                suggested_actions=[self._execution_action(result)],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.LOW,
                forbidden_actions_detected=[
                    "no_product_runtime_git_write",
                    "no_main_worktree_write",
                    "no_worktree_write",
                    "no_file_write",
                    "no_patch_apply",
                    "no_executor_start",
                    "no_worker_dispatch",
                    "no_task_creation",
                    "no_run_creation",
                    "no_worktree_creation",
                    "no_git_approval_from_execution",
                ],
            )
        )
        self._message_repository.commit()

        result = result.model_copy(update={"execution_message_bound": True})
        return ConfirmedSandboxWriteExecution(result=result, message=message)

    def build_execution_from_sources(
        self,
        *,
        session_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        execution_mode: SandboxWriteExecutionMode = "dry_run",
    ) -> ProjectDirectorSandboxWriteExecutionResult:
        """Build a no-write execution result from one P20 preflight message."""

        blocked_reasons: list[str] = []
        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        if source_message is None:
            blocked_reasons.append("source_message_missing")

        source_preflight_status: str | None = None
        source_preflight_message_bound = False
        policy_only_source_verified = False
        accepted_operation_paths: list[str] = []
        accepted_operation_intents: list[dict[str, str]] = []
        blocked_operation_paths: list[str] = []
        checked_operations_count = 0
        source_blocked_operations_count = 0
        p20_action: dict[str, Any] | None = None

        if source_message is not None:
            if source_message.session_id != session_id:
                blocked_reasons.append("source_message_not_in_session")
            if (
                source_message.source_detail
                != P20_SANDBOX_WRITE_PREFLIGHT_SOURCE_DETAIL
            ):
                blocked_reasons.append(
                    "source_message_is_not_p20_sandbox_write_preflight"
                )
            p20_action = self._first_p20_preflight_action(source_message)
            if p20_action is None:
                blocked_reasons.append("p20_preflight_record_missing")

        if source_task is not None and not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_is_not_p12_safe_dry_run")

        if source_task is not None and source_message is not None:
            if not self._source_message_binds_task(source_message, source_task):
                blocked_reasons.append("source_task_not_bound_to_p20_preflight")
            else:
                source_preflight_message_bound = (
                    source_message.session_id == session_id
                    and source_message.source_detail
                    == P20_SANDBOX_WRITE_PREFLIGHT_SOURCE_DETAIL
                )

        if execution_mode == "controlled_sandbox_write":
            blocked_reasons.append("controlled_sandbox_write_not_enabled_in_api")

        if p20_action is not None:
            source_preflight_status = self._as_optional_str(
                p20_action.get("preflight_status")
            )
            checked_operations_count = self._as_int(
                p20_action.get("checked_operations_count")
            )
            source_blocked_operations_count = self._as_int(
                p20_action.get("blocked_operations_count")
            )
            accepted_operation_paths = self._as_string_list(
                p20_action.get("accepted_operation_paths")
            )
            accepted_operation_intents = self._accepted_operation_intents(
                p20_action.get("accepted_operations"),
                fallback_paths=accepted_operation_paths,
            )
            blocked_operation_paths = self._as_string_list(
                p20_action.get("blocked_operation_paths")
            )

            if source_preflight_status != "passed":
                blocked_reasons.append("source_preflight_not_passed")
            if p20_action.get("policy_only_preflight") is not True:
                blocked_reasons.append("source_preflight_not_policy_only")
            if self._as_string_list(p20_action.get("blocked_reasons")):
                blocked_reasons.append("source_preflight_has_blocked_reasons")
            if checked_operations_count <= 0:
                blocked_reasons.append("source_preflight_has_no_checked_operations")
            if source_blocked_operations_count != 0:
                blocked_reasons.append("source_preflight_has_blocked_operations")
            if not accepted_operation_paths:
                blocked_reasons.append("accepted_operation_paths_required")

            policy_only_source_verified = (
                source_preflight_status == "passed"
                and p20_action.get("policy_only_preflight") is True
                and source_preflight_message_bound
                and not self._as_string_list(p20_action.get("blocked_reasons"))
                and checked_operations_count > 0
                and source_blocked_operations_count == 0
                and bool(accepted_operation_paths)
            )

        blocked_reasons = self._dedupe(blocked_reasons)
        execution_status = self._execution_status(
            blocked=bool(blocked_reasons),
            execution_mode=execution_mode,
        )
        operation_status = self._operation_status(
            blocked=bool(blocked_reasons),
            execution_mode=execution_mode,
        )
        operation_results = self._operation_results(
            accepted_operation_intents,
            execution_status=operation_status,
            execution_mode=execution_mode,
        )

        simulated_operations_count = (
            len(operation_results)
            if execution_mode == "fake_write" and not blocked_reasons
            else 0
        )
        blocked_operations_count = (
            source_blocked_operations_count
            if source_blocked_operations_count > 0
            else len(operation_results)
            if blocked_reasons
            else 0
        )

        return ProjectDirectorSandboxWriteExecutionResult(
            execution_status=execution_status,
            session_id=session_id,
            source_task_id=source_task.id if source_task is not None else None,
            source_message_id=(
                source_message.id if source_message is not None else None
            ),
            execution_mode=execution_mode,
            source_preflight_status=source_preflight_status,
            source_preflight_message_bound=source_preflight_message_bound,
            policy_only_source_verified=policy_only_source_verified,
            dry_run_only=execution_mode == "dry_run",
            fake_write_only=execution_mode == "fake_write",
            checked_operations_count=checked_operations_count,
            simulated_operations_count=simulated_operations_count,
            blocked_operations_count=blocked_operations_count,
            operation_results=operation_results,
            accepted_operation_paths=accepted_operation_paths,
            blocked_operation_paths=blocked_operation_paths,
            execution_summary=self._execution_summary(
                execution_status=execution_status,
                execution_mode=execution_mode,
            ),
            recommended_next_step=(
                "Add targeted P21-A contract/API/smoke evidence before any "
                "controlled sandbox write implementation is considered."
            ),
            blocked_reasons=blocked_reasons,
            risks=[
                "P21-A result must not be treated as file write approval",
                "fake_write is simulated only and does not modify target files",
                "product runtime Git writes remain forbidden",
            ],
            unknowns=[
                "controlled sandbox write is not enabled by this API",
                "rollback snapshot was not created because no file was written",
                "future worktree write execution remains out of scope",
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
            if action.get("type") != P20_SANDBOX_WRITE_PREFLIGHT_ACTION_TYPE:
                continue
            if action.get("source_task_id") == str(source_task.id):
                return True

        return False

    @staticmethod
    def _first_p20_preflight_action(
        source_message: ProjectDirectorMessage,
    ) -> dict[str, Any] | None:
        if not source_message.suggested_actions:
            return None
        first_action = source_message.suggested_actions[0]
        if not isinstance(first_action, dict):
            return None
        if first_action.get("type") != P20_SANDBOX_WRITE_PREFLIGHT_ACTION_TYPE:
            return None
        return first_action

    @staticmethod
    def _operation_results(
        operation_intents: list[dict[str, str]],
        *,
        execution_status: SandboxWriteOperationExecutionStatus,
        execution_mode: SandboxWriteExecutionMode,
    ) -> list[ProjectDirectorSandboxWriteOperationResult]:
        notes_by_mode = {
            "dry_run": "planned only; no file written and no patch applied",
            "fake_write": "simulated only; no file written and no patch applied",
            "controlled_sandbox_write": (
                "blocked because controlled sandbox write is not enabled in P21-A"
            ),
        }
        return [
            ProjectDirectorSandboxWriteOperationResult(
                operation_id=f"p21-a-{index}",
                path=operation_intent["path"],
                operation=operation_intent["operation"],
                source_preflight_operation_type="p20_preflight_accepted_path",
                execution_status=execution_status,
                source_preflight_path_policy_allowed=True,
                notes=[
                    notes_by_mode[execution_mode],
                    "rollback snapshot not created because no file was written",
                ],
            )
            for index, operation_intent in enumerate(operation_intents, start=1)
        ]

    @staticmethod
    def _execution_status(
        *,
        blocked: bool,
        execution_mode: SandboxWriteExecutionMode,
    ) -> str:
        if blocked:
            return "blocked"
        if execution_mode == "fake_write":
            return "simulated"
        return "planned"

    @staticmethod
    def _operation_status(
        *,
        blocked: bool,
        execution_mode: SandboxWriteExecutionMode,
    ) -> SandboxWriteOperationExecutionStatus:
        if blocked:
            return "blocked"
        if execution_mode == "fake_write":
            return "simulated"
        return "planned"

    @staticmethod
    def _execution_summary(
        *,
        execution_status: str,
        execution_mode: SandboxWriteExecutionMode,
    ) -> str:
        if execution_status == "blocked":
            return (
                "P21-A sandbox write execution was blocked before any file, "
                "worktree, patch, executor, Worker, Task, Run, or Git write."
            )
        if execution_mode == "fake_write":
            return (
                "P21-A fake-write execution result was simulated only; no file "
                "was written, no worktree was created, and no patch was applied."
            )
        return (
            "P21-A dry-run execution result was planned only; no file was written, "
            "no worktree was created, and no patch was applied."
        )

    @staticmethod
    def _execution_action(
        result: ProjectDirectorSandboxWriteExecutionResult,
    ) -> dict[str, Any]:
        return {
            "type": "p21_sandbox_write_execution_record",
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
            "execution_mode": result.execution_mode,
            "execution_status": result.execution_status,
            "source_preflight_status": result.source_preflight_status,
            "source_preflight_message_bound": result.source_preflight_message_bound,
            "policy_only_source_verified": result.policy_only_source_verified,
            "sandbox_write_execution": True,
            "no_write_execution": True,
            "dry_run_only": result.dry_run_only,
            "fake_write_only": result.fake_write_only,
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
            "execution_message_bound": True,
            "checked_operations_count": result.checked_operations_count,
            "simulated_operations_count": result.simulated_operations_count,
            "blocked_operations_count": result.blocked_operations_count,
            "operation_results": [
                operation.model_dump(mode="json")
                for operation in result.operation_results
            ],
            "accepted_operation_paths": list(result.accepted_operation_paths),
            "blocked_operation_paths": list(result.blocked_operation_paths),
            "execution_summary": result.execution_summary,
            "recommended_next_step": result.recommended_next_step,
            "ai_project_director_total_loop": "Partial",
            "blocked_reasons": list(result.blocked_reasons),
            "risks": list(result.risks),
            "unknowns": list(result.unknowns),
        }

    @staticmethod
    def _as_int(value: Any) -> int:
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return value
        return 0

    @staticmethod
    def _as_optional_str(value: Any) -> str | None:
        return value if isinstance(value, str) else None

    @staticmethod
    def _as_string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item.strip()]

    @classmethod
    def _accepted_operation_intents(
        cls,
        value: Any,
        *,
        fallback_paths: list[str],
    ) -> list[dict[str, str]]:
        structured: list[dict[str, str]] = []
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                path = item.get("path")
                operation = item.get("operation")
                if (
                    isinstance(path, str)
                    and path.strip()
                    and operation in ("create", "update")
                ):
                    structured.append(
                        {"path": path.strip(), "operation": str(operation)}
                    )
        if structured:
            return structured

        return [
            {"path": path, "operation": "p20_preflight_accepted_path"}
            for path in fallback_paths
        ]

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
    "ConfirmedSandboxWriteExecution",
    "P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL",
    "ProjectDirectorSandboxWriteExecutionService",
)
