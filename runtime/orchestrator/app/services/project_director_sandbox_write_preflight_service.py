"""Policy-only sandbox write preflight service for Project Director P20."""

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
from app.domain.project_director_sandbox_write_policy import (
    check_sandbox_path_policy,
)
from app.domain.project_director_sandbox_write_preflight import (
    ProjectDirectorAcceptedSandboxWriteOperation,
    ProjectDirectorFileOperationPlan,
    ProjectDirectorSandboxWritePreflightResult,
    SandboxWritePreflightMode,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_programmer_no_write_execution_service import (
    P17_PROGRAMMER_NO_WRITE_EXECUTION_SOURCE_DETAIL,
)


P20_SANDBOX_WRITE_PREFLIGHT_SOURCE_DETAIL = "p20_sandbox_write_preflight"


@dataclass(frozen=True, slots=True)
class ConfirmedSandboxWritePreflight:
    """Policy-only preflight result and optional bound session message."""

    result: ProjectDirectorSandboxWritePreflightResult
    message: ProjectDirectorMessage | None


class ProjectDirectorSandboxWritePreflightService:
    """Validate proposed sandbox file operations without writing files."""

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

    def confirm_preflight(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        preflight_mode: SandboxWritePreflightMode = "dry_run",
        allowed_path_prefixes: list[str] | None = None,
        allow_frontend: bool = False,
        allow_lockfile: bool = False,
        allow_binary: bool = False,
        file_operations: list[ProjectDirectorFileOperationPlan] | None = None,
    ) -> ConfirmedSandboxWritePreflight:
        """Record a passed no-write preflight result message."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("sandbox write preflight repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        if source_task is None:
            raise ValueError(f"Task {source_task_id} not found")

        source_message = self._message_repository.get_by_id(source_message_id)
        if source_message is None:
            raise ValueError(f"Project Director message {source_message_id} not found")

        result = self.build_preflight_from_sources(
            session_id=session_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            preflight_mode=preflight_mode,
            allowed_path_prefixes=allowed_path_prefixes,
            allow_frontend=allow_frontend,
            allow_lockfile=allow_lockfile,
            allow_binary=allow_binary,
            file_operations=file_operations or [],
        )
        if result.blocked_reasons:
            raise ValueError(";".join(result.blocked_reasons))

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已生成 P20 sandbox write policy-only preflight。该结果"
                    "不代表文件已写入，不应用 patch，不创建 worktree，不授权产品运行时 "
                    "Git 写；AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_write_preflight",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P20_SANDBOX_WRITE_PREFLIGHT_SOURCE_DETAIL,
                suggested_actions=[
                    self._preflight_action(
                        result,
                        source_message_id=source_message_id,
                    )
                ],
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
                    "no_git_approval_from_preflight",
                ],
            )
        )
        self._message_repository.commit()

        result = result.model_copy(update={"preflight_message_bound": True})
        return ConfirmedSandboxWritePreflight(result=result, message=message)

    def build_preflight_from_sources(
        self,
        *,
        session_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        preflight_mode: SandboxWritePreflightMode = "dry_run",
        allowed_path_prefixes: list[str] | None = None,
        allow_frontend: bool = False,
        allow_lockfile: bool = False,
        allow_binary: bool = False,
        file_operations: list[ProjectDirectorFileOperationPlan] | None = None,
    ) -> ProjectDirectorSandboxWritePreflightResult:
        """Build a no-write preflight result without persisting side effects."""

        operations = file_operations or []
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
            if (
                source_message.source_detail
                != P17_PROGRAMMER_NO_WRITE_EXECUTION_SOURCE_DETAIL
            ):
                blocked_reasons.append(
                    "source_message_is_not_p17_programmer_no_write_execution"
                )

        if source_task is not None and not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_is_not_p12_safe_dry_run")

        if source_task is not None and source_message is not None:
            if not self._source_message_binds_task(source_message, source_task):
                blocked_reasons.append("source_task_not_bound_to_p17_execution")

        if preflight_mode == "controlled_sandbox_write":
            blocked_reasons.append("controlled_sandbox_write_not_enabled_in_api")

        if not operations:
            blocked_reasons.append("file_operations_required")

        prefix_policy = allowed_path_prefixes or None
        path_policy_results = [
            check_sandbox_path_policy(
                operation.path,
                allowed_path_prefixes=prefix_policy,
                allow_frontend=allow_frontend,
                allow_lockfile=allow_lockfile,
                allow_binary=allow_binary,
                operation=operation.operation,
            )
            for operation in operations
        ]
        if any(not policy.allowed for policy in path_policy_results):
            blocked_reasons.append("path_policy_failed")

        accepted_operation_paths = [
            policy.normalized_path or policy.path
            for policy in path_policy_results
            if policy.allowed
        ]
        accepted_operations = [
            ProjectDirectorAcceptedSandboxWriteOperation(
                path=policy.normalized_path or policy.path,
                operation=operation.operation,
            )
            for operation, policy in zip(operations, path_policy_results, strict=False)
            if policy.allowed
        ]
        blocked_operation_paths = [
            policy.normalized_path or policy.path
            for policy in path_policy_results
            if not policy.allowed
        ]
        blocked_reasons = self._dedupe(blocked_reasons)
        return ProjectDirectorSandboxWritePreflightResult(
            preflight_status="blocked" if blocked_reasons else "passed",
            session_id=session_id,
            source_task_id=source_task.id if source_task is not None else None,
            source_message_id=(
                source_message.id if source_message is not None else None
            ),
            preflight_mode=preflight_mode,
            checked_operations_count=len(operations),
            allowed_operations_count=len(accepted_operation_paths),
            blocked_operations_count=len(blocked_operation_paths),
            path_policy_results=path_policy_results,
            accepted_operations=accepted_operations,
            accepted_operation_paths=accepted_operation_paths,
            blocked_operation_paths=blocked_operation_paths,
            blocked_reasons=blocked_reasons,
            risks=[
                "preflight must not be treated as file write approval",
                "patch previews remain preview-only and are not applyable patches",
                "product runtime Git writes remain forbidden",
            ],
            unknowns=[
                "controlled sandbox write is not enabled by this API",
                "future worktree write implementation remains out of scope",
            ],
            recommended_next_step=(
                "Add targeted P20 contract/API/smoke evidence before enabling "
                "any controlled sandbox write path."
            ),
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
            if action.get("type") != "p17_programmer_no_write_execution_record":
                continue
            if action.get("source_task_id") == str(source_task.id):
                return True

        return False

    @staticmethod
    def _preflight_action(
        result: ProjectDirectorSandboxWritePreflightResult,
        *,
        source_message_id: UUID,
    ) -> dict[str, Any]:
        return {
            "type": "p20_sandbox_write_preflight_record",
            "source_task_id": (
                str(result.source_task_id)
                if result.source_task_id is not None
                else None
            ),
            "source_message_id": str(source_message_id),
            "preflight_mode": result.preflight_mode,
            "preflight_status": result.preflight_status,
            "policy_only_preflight": True,
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
            "preflight_message_bound": True,
            "checked_operations_count": result.checked_operations_count,
            "allowed_operations_count": result.allowed_operations_count,
            "blocked_operations_count": result.blocked_operations_count,
            "accepted_operation_paths": list(result.accepted_operation_paths),
            "accepted_operations": [
                operation.model_dump(mode="json")
                for operation in result.accepted_operations
            ],
            "blocked_operation_paths": list(result.blocked_operation_paths),
            "path_policy_results": [
                policy.model_dump(mode="json")
                for policy in result.path_policy_results
            ],
            "recommended_next_step": result.recommended_next_step,
            "ai_project_director_total_loop": "Partial",
            "blocked_reasons": list(result.blocked_reasons),
            "risks": list(result.risks),
            "unknowns": list(result.unknowns),
        }

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
    "ConfirmedSandboxWritePreflight",
    "P20_SANDBOX_WRITE_PREFLIGHT_SOURCE_DETAIL",
    "ProjectDirectorSandboxWritePreflightService",
)
