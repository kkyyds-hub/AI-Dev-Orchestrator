"""Sandbox operation manifest guard service for Project Director P21-C."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any
from uuid import UUID

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_operation_manifest_guard import (
    ProjectDirectorSandboxOperationManifestGuardResult,
    SandboxOperationManifestEntry,
    SandboxOperationManifestGuardMode,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_workspace_guard_service import (
    P21_C_SANDBOX_WORKSPACE_GUARD_ACTION_TYPE,
    P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL,
    ProjectDirectorSandboxWorkspaceGuardService,
)
from app.services.project_director_sandbox_write_design_lock_service import (
    P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_write_execution_service import (
    P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
)


P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL = (
    "p21_c_sandbox_operation_manifest_guard"
)
P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE = (
    "p21_c_sandbox_operation_manifest_guard_record"
)
P21_B_SANDBOX_WRITE_DESIGN_LOCK_ACTION_TYPE = (
    "p21_b_sandbox_write_design_lock_record"
)
P21_SANDBOX_WRITE_EXECUTION_ACTION_TYPE = "p21_sandbox_write_execution_record"

REQUIRED_PRECONDITIONS = [
    "p21_c_workspace_guard_required",
    "p21_b_design_lock_required",
    "p21_a_execution_result_required",
    "operation_intent_required",
    "workspace_path_preview_required",
    "operation_path_policy_required",
    "root_containment_check_required",
    "user_confirmation_required",
    "controlled_sandbox_write_separate_enablement_required",
    "actual_file_write_future_step_required",
    "readonly_reviewer_required_after_real_diff",
]

ALLOWED_FUTURE_MANIFEST_SCOPE = [
    "future manifest may only include create/update operations",
    "future manifest paths must be relative",
    "future manifest paths must stay under workspace path preview",
    "future file writes still require separate enablement",
    "future real diff generation remains separate",
    "future product runtime Git operations remain forbidden",
]

FORBIDDEN_MANIFEST_ACTIONS = [
    "no_workspace_creation_in_manifest_guard",
    "no_file_write_in_manifest_guard",
    "no_target_file_content_read_in_manifest_guard",
    "no_real_diff_generation_in_manifest_guard",
    "no_patch_apply_in_manifest_guard",
    "no_worktree_creation_in_manifest_guard",
    "no_worker_dispatch",
    "no_task_creation",
    "no_run_creation",
    "no_executor_start",
    "no_product_runtime_git_write",
    "no_automatic_commit",
    "no_push",
    "no_pr",
    "no_merge",
]

NO_WRITE_FLAGS = (
    "controlled_sandbox_write_enabled",
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

FORBIDDEN_PATH_FRAGMENTS = (
    "\\",
    "~",
    "://",
    ";",
    "|",
    "&",
    "$(",
    "`",
)


@dataclass(frozen=True, slots=True)
class ConfirmedSandboxOperationManifestGuard:
    """P21-C manifest guard result and optional persisted message."""

    result: ProjectDirectorSandboxOperationManifestGuardResult
    message: ProjectDirectorMessage | None


class ProjectDirectorSandboxOperationManifestGuardService:
    """Build a readonly operation manifest preview without filesystem effects."""

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

    def confirm_operation_manifest_guard(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        manifest_mode: SandboxOperationManifestGuardMode = "dry_run",
    ) -> ConfirmedSandboxOperationManifestGuard:
        """Build and, when manifested, persist one operation manifest message."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("sandbox operation manifest guard repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        source_message = self._message_repository.get_by_id(source_message_id)

        result = self.build_operation_manifest_guard_from_sources(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            manifest_mode=manifest_mode,
        )
        if result.manifest_status == "blocked":
            return ConfirmedSandboxOperationManifestGuard(result=result, message=None)

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已记录 P21-C sandbox operation manifest guard。"
                    "这只是 sandbox operation manifest guard，不是目录创建，"
                    "不是文件写入，不是 target file content read，不是 real diff，"
                    "不是 patch apply，不是 worktree 创建，不是 Git 写入；"
                    "AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_operation_manifest_guard",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
                suggested_actions=[self._manifest_guard_action(result)],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.LOW,
                forbidden_actions_detected=list(FORBIDDEN_MANIFEST_ACTIONS),
            )
        )
        self._message_repository.commit()
        return ConfirmedSandboxOperationManifestGuard(result=result, message=message)

    def build_operation_manifest_guard_from_sources(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        manifest_mode: SandboxOperationManifestGuardMode = "dry_run",
    ) -> ProjectDirectorSandboxOperationManifestGuardResult:
        """Build a manifest preview by tracing P21-C-A -> P21-B -> P21-A."""

        blocked_reasons: list[str] = []
        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        elif not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_not_safe_dry_run")
        if source_message is None:
            blocked_reasons.append("source_message_missing")

        workspace_action = self._workspace_guard_action(
            source_message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        source_workspace_guard_status = self._as_optional_str(
            workspace_action.get("guard_status") if workspace_action else None
        )
        source_workspace_guard_message_bound = (
            workspace_action is not None
            and workspace_action.get("source_task_id") == str(source_task_id)
            and source_message is not None
            and source_message.session_id == session_id
            and source_message.source_detail == P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL
        )
        source_workspace_guard_verified = (
            workspace_action is not None
            and source_workspace_guard_status == "guarded"
            and source_workspace_guard_message_bound
            and workspace_action.get("sandbox_workspace_guarded") is True
            and workspace_action.get("workspace_path_within_root") is True
            and self._workspace_action_is_no_write(workspace_action)
            and workspace_action.get("ai_project_director_total_loop") == "Partial"
        )

        workspace_path_preview = self._as_optional_str(
            workspace_action.get("workspace_path_preview") if workspace_action else None
        )
        workspace_path_within_root = (
            workspace_action.get("workspace_path_within_root") is True
            if workspace_action
            else False
        )
        if workspace_action is not None:
            if source_workspace_guard_status != "guarded":
                blocked_reasons.append("source_workspace_guard_not_guarded")
            if not source_workspace_guard_message_bound:
                blocked_reasons.append("source_task_not_bound_to_workspace_guard")
            if workspace_action.get("sandbox_workspace_guarded") is not True:
                blocked_reasons.append("source_workspace_guard_not_guarded")
            if not self._workspace_action_is_no_write(workspace_action):
                blocked_reasons.append("source_workspace_guard_not_no_write")
            if self._any_runtime_write_flag_enabled(workspace_action):
                blocked_reasons.append("real_write_not_allowed_in_manifest_guard")
            if workspace_action.get("ai_project_director_total_loop") != "Partial":
                blocked_reasons.append("source_workspace_guard_not_no_write")
            if not workspace_path_preview:
                blocked_reasons.append("workspace_path_preview_missing")
            if not workspace_path_within_root:
                blocked_reasons.append("workspace_path_not_within_root")

        source_design_lock_message_id = self._uuid_from_action(
            workspace_action,
            "source_message_id",
        )
        design_lock_message = self._get_message(source_design_lock_message_id)
        design_lock_action = self._design_lock_action(
            design_lock_message=design_lock_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )

        source_execution_message_id = self._uuid_from_action(
            design_lock_action,
            "source_message_id",
        )
        execution_message = self._get_message(source_execution_message_id)
        execution_action = self._execution_action(
            execution_message=execution_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )

        operation_results = (
            execution_action.get("operation_results") if execution_action else None
        )
        operations = self._manifest_operations(
            operation_results,
            workspace_path_preview=workspace_path_preview,
            source_execution_status=self._as_optional_str(
                execution_action.get("execution_status") if execution_action else None
            ),
        )
        if execution_action is not None and not operations:
            blocked_reasons.append("operation_results_missing")

        allowed_operation_paths = [
            operation.path
            for operation in operations
            if operation.operation_manifest_allowed
        ]
        blocked_operation_paths = [
            operation.path
            for operation in operations
            if not operation.operation_manifest_allowed and operation.path
        ]
        operation_block_reasons = self._operation_block_reasons(operations)
        if operations and not allowed_operation_paths:
            blocked_reasons.extend(operation_block_reasons)
            blocked_reasons.append("all_operations_blocked")

        blocked_reasons = self._dedupe(blocked_reasons)
        manifested = not blocked_reasons and bool(allowed_operation_paths)

        return ProjectDirectorSandboxOperationManifestGuardResult(
            manifest_status="manifested" if manifested else "blocked",
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            manifest_mode=manifest_mode,
            source_workspace_guard_status=source_workspace_guard_status,
            source_workspace_guard_message_bound=source_workspace_guard_message_bound,
            source_workspace_guard_verified=source_workspace_guard_verified,
            source_design_lock_message_id=source_design_lock_message_id,
            source_execution_message_id=source_execution_message_id,
            workspace_path_preview=workspace_path_preview,
            workspace_path_within_root=workspace_path_within_root,
            operation_manifest_created=manifested,
            manifest_operations_count=len(operations),
            manifest_allowed_operations_count=len(allowed_operation_paths),
            manifest_blocked_operations_count=(
                len(operations) - len(allowed_operation_paths)
            ),
            manifest_operations=operations,
            allowed_operation_paths=allowed_operation_paths,
            blocked_operation_paths=blocked_operation_paths,
            required_preconditions=list(REQUIRED_PRECONDITIONS),
            allowed_future_manifest_scope=list(ALLOWED_FUTURE_MANIFEST_SCOPE),
            forbidden_manifest_actions=list(FORBIDDEN_MANIFEST_ACTIONS),
            blocked_reasons=blocked_reasons,
            risks=[
                "operation manifest guard must not be interpreted as file write approval",
                "future file writes still require separate controlled enablement",
                "product runtime Git writes remain forbidden",
            ],
            unknowns=[
                "actual workspace creation remains future work",
                "real diff generation remains future work",
                "readonly reviewer handoff after a real diff remains future work",
            ],
            manifest_summary=self._manifest_summary(manifested=manifested),
            recommended_next_step=(
                "Continue with the next implementation-only P21-C slice, then run "
                "one Mimocode batch covering P21-C-A and P21-C-B before any actual "
                "workspace creation or file write."
            ),
        )

    def _workspace_guard_action(
        self,
        *,
        source_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if source_message is None:
            return None
        if (
            source_message.session_id != session_id
            or source_message.source_detail != P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_message_is_not_p21_c_workspace_guard")
        action = self._first_action(
            source_message,
            expected_type=P21_C_SANDBOX_WORKSPACE_GUARD_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("p21_c_workspace_guard_record_missing")
        elif action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_task_not_bound_to_workspace_guard")
        return action

    def _design_lock_action(
        self,
        *,
        design_lock_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if design_lock_message is None:
            blocked_reasons.append("source_design_lock_message_missing")
            return None
        if (
            design_lock_message.session_id != session_id
            or design_lock_message.source_detail
            != P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_design_lock_message_missing")
        action = self._first_action(
            design_lock_message,
            expected_type=P21_B_SANDBOX_WRITE_DESIGN_LOCK_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("source_design_lock_message_missing")
            return None
        if action.get("design_lock_status") != "locked":
            blocked_reasons.append("source_design_lock_not_locked")
        if action.get("controlled_sandbox_write_design_locked") is not True:
            blocked_reasons.append("source_design_lock_not_locked")
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_design_lock_message_missing")
        if not self._design_lock_action_is_no_write(action):
            blocked_reasons.append("source_design_lock_not_no_write")
        if self._any_runtime_write_flag_enabled(action):
            blocked_reasons.append("real_write_not_allowed_in_manifest_guard")
        return action

    def _execution_action(
        self,
        *,
        execution_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if execution_message is None:
            blocked_reasons.append("source_execution_message_missing")
            return None
        if (
            execution_message.session_id != session_id
            or execution_message.source_detail != P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_execution_message_missing")
        action = self._first_action(
            execution_message,
            expected_type=P21_SANDBOX_WRITE_EXECUTION_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("source_execution_message_missing")
            return None
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_execution_message_missing")
        if action.get("execution_status") not in ("planned", "simulated"):
            blocked_reasons.append("source_execution_not_planned_or_simulated")
        if action.get("execution_mode") not in ("dry_run", "fake_write"):
            blocked_reasons.append("source_execution_not_planned_or_simulated")
        if action.get("no_write_execution") is not True:
            blocked_reasons.append("source_execution_not_no_write")
        if not self._execution_action_is_no_write(action):
            blocked_reasons.append("source_execution_not_no_write")
        if self._any_runtime_write_flag_enabled(action):
            blocked_reasons.append("real_write_not_allowed_in_manifest_guard")
        if action.get("ai_project_director_total_loop") not in (None, "Partial"):
            blocked_reasons.append("source_execution_not_no_write")
        if not isinstance(action.get("operation_results"), list) or not action.get(
            "operation_results"
        ):
            blocked_reasons.append("operation_results_missing")
        return action

    def _manifest_operations(
        self,
        operation_results: Any,
        *,
        workspace_path_preview: str | None,
        source_execution_status: str | None,
    ) -> list[SandboxOperationManifestEntry]:
        if not isinstance(operation_results, list):
            return []
        workspace_path = self._path_from_text(workspace_path_preview)
        operations: list[SandboxOperationManifestEntry] = []
        for index, item in enumerate(operation_results, start=1):
            if not isinstance(item, dict):
                continue
            operations.append(
                self._manifest_operation(
                    item,
                    index=index,
                    workspace_path=workspace_path,
                    source_execution_status=source_execution_status,
                )
            )
        return operations

    def _manifest_operation(
        self,
        item: dict[str, Any],
        *,
        index: int,
        workspace_path: Path | None,
        source_execution_status: str | None,
    ) -> SandboxOperationManifestEntry:
        blocked_reasons: list[str] = []
        path = self._as_optional_str(item.get("path")) or ""
        operation = self._as_optional_str(item.get("operation")) or ""
        operation_id = self._as_optional_str(item.get("operation_id")) or f"p21-c-b-{index}"

        if operation not in ("create", "update"):
            blocked_reasons.append("operation_intent_not_create_or_update")
        if not path.strip():
            blocked_reasons.append("operation_path_missing")
        elif not self._operation_path_is_relative(path):
            blocked_reasons.append("operation_path_not_relative")
        elif self._operation_path_not_allowed(path):
            blocked_reasons.append("operation_path_not_allowed")
        if item.get("source_preflight_path_policy_allowed") is not True:
            blocked_reasons.append("operation_path_not_allowed")

        workspace_target_path_preview = ""
        path_within_workspace = False
        if workspace_path is not None and path.strip():
            try:
                target_path = (workspace_path / path).resolve(strict=False)
                workspace_target_path_preview = target_path.as_posix()
                path_within_workspace = self._is_relative_to(target_path, workspace_path)
            except OSError:
                path_within_workspace = False
            if not path_within_workspace:
                blocked_reasons.append("operation_path_escapes_workspace")
        elif path.strip():
            blocked_reasons.append("workspace_path_preview_missing")

        blocked_reasons = self._dedupe(blocked_reasons)
        return SandboxOperationManifestEntry(
            operation_id=operation_id,
            path=path,
            operation=operation,
            workspace_target_path_preview=workspace_target_path_preview,
            source_execution_status=source_execution_status,
            source_preflight_path_policy_allowed=self._as_optional_bool(
                item.get("source_preflight_path_policy_allowed")
            ),
            path_within_workspace=path_within_workspace,
            operation_manifest_allowed=not blocked_reasons,
            blocked_reasons=blocked_reasons,
        )

    def _get_message(self, message_id: UUID | None) -> ProjectDirectorMessage | None:
        if message_id is None or self._message_repository is None:
            return None
        return self._message_repository.get_by_id(message_id)

    @staticmethod
    def _is_safe_dry_run_task(task: Task) -> bool:
        return ProjectDirectorSandboxWorkspaceGuardService._is_safe_dry_run_task(task)

    @staticmethod
    def _first_action(
        source_message: ProjectDirectorMessage,
        *,
        expected_type: str,
    ) -> dict[str, Any] | None:
        if not source_message.suggested_actions:
            return None
        first_action = source_message.suggested_actions[0]
        if not isinstance(first_action, dict):
            return None
        if first_action.get("type") != expected_type:
            return None
        return first_action

    @staticmethod
    def _uuid_from_action(action: dict[str, Any] | None, key: str) -> UUID | None:
        if action is None:
            return None
        value = action.get(key)
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return UUID(value)
        except ValueError:
            return None

    @staticmethod
    def _workspace_action_is_no_write(action: dict[str, Any]) -> bool:
        expected_false_flags = (
            "workspace_created",
            "workspace_written",
            "controlled_sandbox_write_enabled",
            "sandbox_write_allowed",
            "file_write_allowed",
            "worktree_write_allowed",
            "product_runtime_git_write_allowed",
        )
        return all(action.get(flag) is False for flag in expected_false_flags)

    @staticmethod
    def _design_lock_action_is_no_write(action: dict[str, Any]) -> bool:
        expected_false_flags = (
            "controlled_sandbox_write_enabled",
            "sandbox_write_allowed",
            "file_write_allowed",
            "worktree_write_allowed",
            "product_runtime_git_write_allowed",
        )
        return all(action.get(flag) is False for flag in expected_false_flags)

    @staticmethod
    def _execution_action_is_no_write(action: dict[str, Any]) -> bool:
        expected_false_flags = (
            "controlled_sandbox_write_enabled",
            "sandbox_write_allowed",
            "file_write_allowed",
            "worktree_write_allowed",
            "product_runtime_git_write_allowed",
        )
        return all(action.get(flag) is False for flag in expected_false_flags)

    @staticmethod
    def _any_runtime_write_flag_enabled(action: dict[str, Any]) -> bool:
        return any(action.get(flag) is True for flag in NO_WRITE_FLAGS)

    @staticmethod
    def _operation_path_is_relative(path: str) -> bool:
        if Path(path).is_absolute() or PureWindowsPath(path).drive:
            return False
        return True

    @staticmethod
    def _operation_path_not_allowed(path: str) -> bool:
        if ".." in Path(path).parts:
            return True
        if any(fragment in path for fragment in FORBIDDEN_PATH_FRAGMENTS):
            return True
        lowered = path.lower()
        if lowered.startswith("file://"):
            return True
        return False

    @staticmethod
    def _path_from_text(value: str | None) -> Path | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return Path(value).resolve(strict=False)
        except OSError:
            return None

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        return path == root or root in path.parents

    @staticmethod
    def _operation_block_reasons(
        operations: list[SandboxOperationManifestEntry],
    ) -> list[str]:
        reasons: list[str] = []
        for operation in operations:
            if operation.operation_manifest_allowed:
                continue
            reasons.extend(operation.blocked_reasons)
        return reasons

    @staticmethod
    def _manifest_summary(*, manifested: bool) -> str:
        if not manifested:
            return (
                "P21-C sandbox operation manifest guard was blocked before "
                "directory creation, target file content read, file write, real "
                "diff generation, patch application, worktree, executor, Worker, "
                "Task, Run, rollback, or Git side effect."
            )
        return (
            "P21-C sandbox operation manifest guard recorded a readonly manifest "
            "preview from P21-A operation results under the guarded workspace path. "
            "It does not create directories, read target files, write files, "
            "generate diffs, apply patches, create worktrees, start executors, "
            "dispatch Workers, create Tasks/Runs, create rollback snapshots, or "
            "perform Git writes."
        )

    @staticmethod
    def _manifest_guard_action(
        result: ProjectDirectorSandboxOperationManifestGuardResult,
    ) -> dict[str, Any]:
        return {
            "type": P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE,
            "manifest_status": result.manifest_status,
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
            "source_design_lock_message_id": (
                str(result.source_design_lock_message_id)
                if result.source_design_lock_message_id is not None
                else None
            ),
            "source_execution_message_id": (
                str(result.source_execution_message_id)
                if result.source_execution_message_id is not None
                else None
            ),
            "workspace_path_preview": result.workspace_path_preview,
            "workspace_path_within_root": result.workspace_path_within_root,
            "operation_manifest_created": result.operation_manifest_created,
            "manifest_operations_count": result.manifest_operations_count,
            "manifest_allowed_operations_count": (
                result.manifest_allowed_operations_count
            ),
            "manifest_blocked_operations_count": (
                result.manifest_blocked_operations_count
            ),
            "manifest_operations": [
                operation.model_dump(mode="json")
                for operation in result.manifest_operations
            ],
            "allowed_operation_paths": list(result.allowed_operation_paths),
            "blocked_operation_paths": list(result.blocked_operation_paths),
            "workspace_created": False,
            "workspace_written": False,
            "file_written": False,
            "controlled_sandbox_write_enabled": False,
            "sandbox_write_allowed": False,
            "product_runtime_git_write_allowed": False,
            "main_worktree_write_allowed": False,
            "worktree_write_allowed": False,
            "file_write_allowed": False,
            "actual_patch_applied": False,
            "real_code_modified": False,
            "real_diff_generated": False,
            "patch_applied": False,
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
            "target_file_content_read": False,
            "required_preconditions": list(result.required_preconditions),
            "allowed_future_manifest_scope": list(
                result.allowed_future_manifest_scope
            ),
            "forbidden_manifest_actions": list(result.forbidden_manifest_actions),
            "blocked_reasons": list(result.blocked_reasons),
            "risks": list(result.risks),
            "unknowns": list(result.unknowns),
            "manifest_summary": result.manifest_summary,
            "recommended_next_step": result.recommended_next_step,
            "ai_project_director_total_loop": "Partial",
        }

    @staticmethod
    def _as_optional_str(value: Any) -> str | None:
        return value if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _as_optional_bool(value: Any) -> bool | None:
        return value if isinstance(value, bool) else None

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
    "ConfirmedSandboxOperationManifestGuard",
    "P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL",
    "ProjectDirectorSandboxOperationManifestGuardService",
)
