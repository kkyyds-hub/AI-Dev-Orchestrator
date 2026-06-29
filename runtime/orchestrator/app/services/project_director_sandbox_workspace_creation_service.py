"""Controlled sandbox workspace creation service for Project Director P21-C."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_workspace_creation import (
    ProjectDirectorSandboxWorkspaceCreationResult,
    SandboxWorkspaceCreateMode,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_operation_manifest_guard_service import (
    P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE,
    P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_workspace_guard_service import (
    ProjectDirectorSandboxWorkspaceGuardService,
)


P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL = (
    "p21_c_sandbox_workspace_created"
)
P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE = (
    "p21_c_sandbox_workspace_create_record"
)

REQUIRED_PRECONDITIONS = [
    "p21_c_operation_manifest_guard_required",
    "workspace_path_preview_required",
    "backend_runtime_workspace_root_required",
    "root_containment_check_required",
    "user_confirmation_required",
    "mkdir_only_mode_required",
    "no_file_write_required",
    "no_manifest_file_write_required",
    "no_target_file_content_read_required",
    "no_git_worktree_required",
    "cleanup_future_step_required",
    "readonly_reviewer_required_after_real_diff",
]

ALLOWED_FUTURE_CREATION_SCOPE = [
    "current step may only create a sandbox workspace directory",
    "future manifest/evidence file write must be separate",
    "future candidate file write must be separate",
    "future real diff generation must be separate",
    "future cleanup must be separate",
    "product runtime Git operations remain forbidden",
]

FORBIDDEN_CREATION_ACTIONS = [
    "no_business_file_write_in_workspace_create",
    "no_manifest_file_write_in_workspace_create",
    "no_target_file_content_read_in_workspace_create",
    "no_real_diff_generation_in_workspace_create",
    "no_patch_apply_in_workspace_create",
    "no_git_worktree_creation_in_workspace_create",
    "no_main_worktree_write",
    "no_worker_dispatch",
    "no_task_creation",
    "no_run_creation",
    "no_executor_start",
    "no_product_runtime_git_write",
    "no_automatic_commit",
    "no_push",
    "no_pr",
    "no_merge",
    "no_cleanup_in_workspace_create",
]

SOURCE_NO_WRITE_FLAGS = (
    "workspace_created",
    "workspace_written",
    "file_written",
    "target_file_content_read",
    "real_diff_generated",
    "patch_applied",
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
)


@dataclass(frozen=True, slots=True)
class ConfirmedSandboxWorkspaceCreation:
    """P21-C workspace creation result and optional persisted message."""

    result: ProjectDirectorSandboxWorkspaceCreationResult
    message: ProjectDirectorMessage | None


class ProjectDirectorSandboxWorkspaceCreationService:
    """Create only the guarded sandbox workspace directory."""

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

    def confirm_workspace_creation(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        create_mode: SandboxWorkspaceCreateMode = "mkdir_only",
    ) -> ConfirmedSandboxWorkspaceCreation:
        """Build, execute mkdir-only creation, and persist a success message."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("sandbox workspace creation repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        source_message = self._message_repository.get_by_id(source_message_id)

        result = self.build_workspace_creation_from_sources(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            create_mode=create_mode,
        )
        if result.creation_status == "blocked":
            return ConfirmedSandboxWorkspaceCreation(result=result, message=None)

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已创建或确认存在 P21-C 隔离 sandbox workspace 目录。"
                    "本轮只创建隔离 sandbox workspace 目录，没有写业务文件，"
                    "没有写 manifest 文件，没有读取 target file content，"
                    "没有生成 real diff，没有应用 patch，没有创建 git worktree，"
                    "没有执行 Git 写入；AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_workspace_create",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
                suggested_actions=[self._workspace_creation_action(result)],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.MEDIUM,
                forbidden_actions_detected=list(FORBIDDEN_CREATION_ACTIONS),
            )
        )
        self._message_repository.commit()
        return ConfirmedSandboxWorkspaceCreation(result=result, message=message)

    def build_workspace_creation_from_sources(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        create_mode: SandboxWorkspaceCreateMode = "mkdir_only",
    ) -> ProjectDirectorSandboxWorkspaceCreationResult:
        """Validate the P21-C-B manifest guard and create only its workspace dir."""

        blocked_reasons: list[str] = []
        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        elif not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_not_safe_dry_run")
        if source_message is None:
            blocked_reasons.append("source_message_missing")
        if create_mode != "mkdir_only":
            blocked_reasons.append("real_write_not_allowed_beyond_workspace_mkdir")

        manifest_action = self._manifest_guard_action(
            source_message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        source_manifest_status = self._as_optional_str(
            manifest_action.get("manifest_status") if manifest_action else None
        )
        source_manifest_message_bound = (
            manifest_action is not None
            and manifest_action.get("source_task_id") == str(source_task_id)
            and source_message is not None
            and source_message.session_id == session_id
            and source_message.source_detail
            == P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL
        )
        workspace_path_preview = self._as_optional_str(
            manifest_action.get("workspace_path_preview") if manifest_action else None
        )
        workspace_root = self._resolved_workspace_root(blocked_reasons)
        workspace_root_text = workspace_root.as_posix() if workspace_root else None
        workspace_path = self._resolved_workspace_path(
            workspace_path_preview,
            blocked_reasons,
        )
        workspace_path_text = workspace_path.as_posix() if workspace_path else None
        workspace_path_within_root = (
            workspace_root is not None
            and workspace_path is not None
            and self._is_relative_to(workspace_path, workspace_root)
        )

        if manifest_action is not None:
            if source_manifest_status != "manifested":
                blocked_reasons.append("source_manifest_not_manifested")
            if not source_manifest_message_bound:
                blocked_reasons.append("source_task_not_bound_to_manifest_guard")
            if manifest_action.get("operation_manifest_created") is not True:
                blocked_reasons.append("source_manifest_not_manifested")
            if manifest_action.get("workspace_path_within_root") is not True:
                blocked_reasons.append("workspace_path_not_within_root")
            allowed_count = manifest_action.get("manifest_allowed_operations_count")
            if not isinstance(allowed_count, int) or allowed_count <= 0:
                blocked_reasons.append("source_manifest_not_manifested")
            if not self._manifest_action_is_no_write(manifest_action):
                blocked_reasons.append("source_manifest_not_no_write")
            if manifest_action.get("ai_project_director_total_loop") != "Partial":
                blocked_reasons.append("source_manifest_not_no_write")

        if not workspace_path_preview:
            blocked_reasons.append("workspace_path_preview_missing")
        if not workspace_path_within_root:
            blocked_reasons.append("workspace_path_not_within_root")

        source_manifest_verified = (
            manifest_action is not None
            and source_manifest_status == "manifested"
            and source_manifest_message_bound
            and manifest_action.get("operation_manifest_created") is True
            and manifest_action.get("workspace_path_within_root") is True
            and isinstance(
                manifest_action.get("manifest_allowed_operations_count"),
                int,
            )
            and manifest_action.get("manifest_allowed_operations_count") > 0
            and self._manifest_action_is_no_write(manifest_action)
            and manifest_action.get("ai_project_director_total_loop") == "Partial"
            and workspace_path_within_root
        )

        workspace_created = False
        workspace_already_existed = False
        if not blocked_reasons and workspace_path is not None:
            try:
                if workspace_path.exists():
                    if not workspace_path.is_dir():
                        blocked_reasons.append("workspace_path_is_not_directory")
                    else:
                        workspace_already_existed = True
                else:
                    workspace_path.mkdir(parents=True, exist_ok=False)
                    workspace_created = True
            except OSError:
                blocked_reasons.append("mkdir_failed")

        blocked_reasons = self._dedupe(blocked_reasons)
        creation_status = "blocked"
        if not blocked_reasons:
            creation_status = "created" if workspace_created else "already_exists"
        cleanup_required = creation_status == "created"
        cleanup_hint = self._cleanup_hint(
            creation_status=creation_status,
            workspace_path=workspace_path_text,
        )

        return ProjectDirectorSandboxWorkspaceCreationResult(
            creation_status=creation_status,
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            create_mode=create_mode,
            source_manifest_status=source_manifest_status,
            source_manifest_message_bound=source_manifest_message_bound,
            source_manifest_verified=source_manifest_verified,
            workspace_path=workspace_path_text,
            workspace_path_within_root=workspace_path_within_root,
            workspace_root=workspace_root_text,
            workspace_created=workspace_created,
            workspace_already_existed=workspace_already_existed,
            cleanup_required=cleanup_required,
            cleanup_hint=cleanup_hint,
            required_preconditions=list(REQUIRED_PRECONDITIONS),
            allowed_future_creation_scope=list(ALLOWED_FUTURE_CREATION_SCOPE),
            forbidden_creation_actions=list(FORBIDDEN_CREATION_ACTIONS),
            blocked_reasons=blocked_reasons,
            risks=[
                "workspace directory creation must not be interpreted as file write approval",
                "future candidate file writes still require a separate controlled step",
                "product runtime Git writes remain forbidden",
            ],
            unknowns=[
                "manifest/evidence file write remains future work",
                "candidate file write remains future work",
                "cleanup execution remains future work",
            ],
            creation_summary=self._creation_summary(
                creation_status=creation_status,
            ),
            recommended_next_step=(
                "Mimocode should add targeted P21-C-C API/smoke evidence before "
                "any manifest file write, candidate file write, real diff, patch, "
                "worktree, cleanup, or product runtime Git step."
            ),
        )

    def _manifest_guard_action(
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
            or source_message.source_detail
            != P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL
        ):
            blocked_reasons.append(
                "source_message_is_not_p21_c_operation_manifest_guard"
            )
        action = self._first_action(
            source_message,
            expected_type=P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("p21_c_operation_manifest_guard_record_missing")
        elif action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_task_not_bound_to_manifest_guard")
        return action

    @staticmethod
    def _workspace_root() -> Path:
        return settings.runtime_data_dir / "project-director" / "sandbox-workspaces"

    def _resolved_workspace_root(self, blocked_reasons: list[str]) -> Path | None:
        try:
            return self._workspace_root().resolve(strict=False)
        except OSError:
            blocked_reasons.append("workspace_root_unavailable")
            return None

    @staticmethod
    def _resolved_workspace_path(
        value: str | None,
        blocked_reasons: list[str],
    ) -> Path | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return Path(value).resolve(strict=False)
        except OSError:
            blocked_reasons.append("workspace_path_not_within_root")
            return None

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
    def _manifest_action_is_no_write(action: dict[str, Any]) -> bool:
        return all(action.get(flag) is False for flag in SOURCE_NO_WRITE_FLAGS)

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        return path == root or root in path.parents

    @staticmethod
    def _as_optional_str(value: Any) -> str | None:
        return value if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _cleanup_hint(
        *,
        creation_status: str,
        workspace_path: str | None,
    ) -> str:
        if creation_status == "created":
            return (
                "cleanup_required=true because this step created the sandbox "
                f"workspace directory at {workspace_path}; cleanup must be a future step."
            )
        if creation_status == "already_exists":
            return (
                "cleanup_required=false because the sandbox workspace directory "
                "already existed and was not modified or cleaned."
            )
        return "no cleanup was performed because workspace creation was blocked."

    @staticmethod
    def _creation_summary(*, creation_status: str) -> str:
        if creation_status == "created":
            return (
                "P21-C sandbox workspace creation created only the isolated "
                "workspace directory after rechecking the backend runtime root and "
                "manifest guard source. It did not write files, read target content, "
                "generate diffs, apply patches, create worktrees, dispatch Workers, "
                "create Tasks/Runs, clean up directories, or perform Git writes."
            )
        if creation_status == "already_exists":
            return (
                "P21-C sandbox workspace creation confirmed the guarded workspace "
                "directory already exists under the backend runtime root. It did "
                "not clear, delete, write files, read target content, generate "
                "diffs, apply patches, create worktrees, dispatch Workers, create "
                "Tasks/Runs, clean up directories, or perform Git writes."
            )
        return (
            "P21-C sandbox workspace creation was blocked before directory "
            "creation, file write, manifest file write, target content read, "
            "diff generation, patch application, worktree, executor, Worker, "
            "Task, Run, cleanup, or Git side effect."
        )

    @staticmethod
    def _workspace_creation_action(
        result: ProjectDirectorSandboxWorkspaceCreationResult,
    ) -> dict[str, Any]:
        return {
            "type": P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
            "creation_status": result.creation_status,
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
            "workspace_path": result.workspace_path,
            "workspace_path_within_root": result.workspace_path_within_root,
            "workspace_created": result.workspace_created,
            "workspace_already_existed": result.workspace_already_existed,
            "workspace_written": False,
            "file_written": False,
            "manifest_file_written": False,
            "target_file_content_read": False,
            "real_diff_generated": False,
            "patch_applied": False,
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
            "cleanup_required": result.cleanup_required,
            "cleanup_hint": result.cleanup_hint,
            "ai_project_director_total_loop": "Partial",
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
    "ConfirmedSandboxWorkspaceCreation",
    "P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE",
    "P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL",
    "ProjectDirectorSandboxWorkspaceCreationService",
)
