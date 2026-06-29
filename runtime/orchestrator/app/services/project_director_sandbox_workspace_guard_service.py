"""Sandbox workspace root guard service for Project Director P21-C."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_workspace_guard import (
    ProjectDirectorSandboxWorkspaceGuardResult,
    SandboxWorkspaceGuardMode,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_write_design_lock_service import (
    P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL,
    ProjectDirectorSandboxWriteDesignLockService,
)


P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL = "p21_c_sandbox_workspace_guard"
P21_B_SANDBOX_WRITE_DESIGN_LOCK_ACTION_TYPE = (
    "p21_b_sandbox_write_design_lock_record"
)
P21_C_SANDBOX_WORKSPACE_GUARD_ACTION_TYPE = (
    "p21_c_sandbox_workspace_guard_record"
)
SANDBOX_WORKSPACE_ROOT_POLICY = (
    "workspace root is fixed by backend runtime data configuration under "
    "project-director/sandbox-workspaces; requests may only provide a workspace "
    "name, never an absolute path"
)
WORKSPACE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
FORBIDDEN_WORKSPACE_NAME_FRAGMENTS = (
    "/",
    "\\",
    "..",
    "~",
    "://",
    ";",
    "|",
    "&",
    "$(",
    "`",
    ":",
)

REQUIRED_PRECONDITIONS = [
    "p21_b_design_lock_required",
    "source_task_message_binding_required",
    "sandbox_workspace_root_required",
    "workspace_name_policy_required",
    "root_containment_check_required",
    "user_confirmation_required",
    "controlled_sandbox_write_separate_enablement_required",
    "actual_workspace_creation_future_step_required",
    "readonly_reviewer_required_after_real_diff",
]

ALLOWED_FUTURE_WORKSPACE_SCOPE = [
    "future workspace may only live under sandbox workspace root",
    "future workspace name must be normalized",
    "future workspace path must pass root containment check",
    "future file writes may only target paths approved by P20 accepted_operations",
    "future worktree creation must remain separate from design lock and workspace guard",
    "future product runtime Git operations remain forbidden",
]

FORBIDDEN_WORKSPACE_ACTIONS = [
    "no_workspace_creation_in_guard",
    "no_workspace_write_in_guard",
    "no_main_worktree_write",
    "no_target_file_content_read_in_guard",
    "no_real_diff_generation_in_guard",
    "no_patch_apply_in_guard",
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


@dataclass(frozen=True, slots=True)
class ConfirmedSandboxWorkspaceGuard:
    """P21-C workspace guard result and optional persisted message."""

    result: ProjectDirectorSandboxWorkspaceGuardResult
    message: ProjectDirectorMessage | None


class ProjectDirectorSandboxWorkspaceGuardService:
    """Preview and guard a future sandbox workspace root without writes."""

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

    def confirm_workspace_guard(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        guard_mode: SandboxWorkspaceGuardMode = "dry_run",
        requested_workspace_name: str | None = None,
    ) -> ConfirmedSandboxWorkspaceGuard:
        """Build and, when guarded, persist one workspace guard message."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("sandbox workspace guard repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        source_message = self._message_repository.get_by_id(source_message_id)

        result = self.build_workspace_guard_from_sources(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            guard_mode=guard_mode,
            requested_workspace_name=requested_workspace_name,
        )
        if result.guard_status == "blocked":
            return ConfirmedSandboxWorkspaceGuard(result=result, message=None)

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已记录 P21-C sandbox workspace root guard。"
                    "这只是 sandbox workspace root guard，不是目录创建，"
                    "不是文件写入，不是 worktree 创建，不是 patch 应用，"
                    "不是 Git 写入；AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_workspace_guard",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL,
                suggested_actions=[self._workspace_guard_action(result)],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.LOW,
                forbidden_actions_detected=list(FORBIDDEN_WORKSPACE_ACTIONS),
            )
        )
        self._message_repository.commit()
        return ConfirmedSandboxWorkspaceGuard(result=result, message=message)

    def build_workspace_guard_from_sources(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        guard_mode: SandboxWorkspaceGuardMode = "dry_run",
        requested_workspace_name: str | None = None,
    ) -> ProjectDirectorSandboxWorkspaceGuardResult:
        """Build a workspace guard result without creating directories."""

        blocked_reasons: list[str] = []
        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        if source_message is None:
            blocked_reasons.append("source_message_missing")

        source_design_lock_status: str | None = None
        source_design_lock_message_bound = False
        source_design_lock_verified = False
        design_lock_action: dict[str, Any] | None = None

        if source_message is not None:
            if source_message.session_id != session_id:
                blocked_reasons.append("source_message_is_not_p21_b_design_lock")
            if (
                source_message.source_detail
                != P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL
            ):
                blocked_reasons.append("source_message_is_not_p21_b_design_lock")
            design_lock_action = self._first_design_lock_action(source_message)
            if design_lock_action is None:
                blocked_reasons.append("p21_b_design_lock_record_missing")

        if source_task is not None and not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_not_safe_dry_run")

        if design_lock_action is not None:
            source_design_lock_status = self._as_optional_str(
                design_lock_action.get("design_lock_status")
            )
            if source_design_lock_status != "locked":
                blocked_reasons.append("source_design_lock_not_locked")
            if design_lock_action.get("source_task_id") != str(source_task_id):
                blocked_reasons.append("source_task_not_bound_to_design_lock")
            else:
                source_design_lock_message_bound = (
                    source_message is not None
                    and source_message.session_id == session_id
                    and source_message.source_detail
                    == P21_B_SANDBOX_WRITE_DESIGN_LOCK_SOURCE_DETAIL
                )
            if (
                design_lock_action.get("controlled_sandbox_write_design_locked")
                is not True
            ):
                blocked_reasons.append("source_design_lock_not_locked")
            if not self._design_lock_action_is_no_write(design_lock_action):
                blocked_reasons.append("source_design_lock_not_no_write")
            if self._any_runtime_write_flag_enabled(design_lock_action):
                blocked_reasons.append("real_write_not_allowed_in_workspace_guard")
            if design_lock_action.get("ai_project_director_total_loop") != "Partial":
                blocked_reasons.append("source_design_lock_not_no_write")

            source_design_lock_verified = (
                source_design_lock_status == "locked"
                and source_design_lock_message_bound
                and design_lock_action.get(
                    "controlled_sandbox_write_design_locked"
                )
                is True
                and self._design_lock_action_is_no_write(design_lock_action)
                and design_lock_action.get("ai_project_director_total_loop")
                == "Partial"
            )

        workspace_root: Path | None = None
        workspace_root_text: str | None = None
        try:
            workspace_root = self._workspace_root().resolve(strict=False)
            workspace_root_text = workspace_root.as_posix()
        except OSError:
            blocked_reasons.append("sandbox_workspace_root_unavailable")

        normalized_workspace_name = self._normalize_workspace_name(
            requested_workspace_name=requested_workspace_name,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        workspace_path_preview: str | None = None
        workspace_path_within_root = False
        if workspace_root is not None and normalized_workspace_name is not None:
            try:
                workspace_path = (
                    workspace_root / normalized_workspace_name
                ).resolve(strict=False)
                workspace_path_preview = workspace_path.as_posix()
                workspace_path_within_root = self._is_relative_to(
                    workspace_path,
                    workspace_root,
                )
            except OSError:
                workspace_path_within_root = False
            if not workspace_path_within_root:
                blocked_reasons.append("workspace_path_escapes_root")

        blocked_reasons = self._dedupe(blocked_reasons)
        guarded = not blocked_reasons
        return ProjectDirectorSandboxWorkspaceGuardResult(
            guard_status="guarded" if guarded else "blocked",
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            guard_mode=guard_mode,
            source_design_lock_status=source_design_lock_status,
            source_design_lock_message_bound=source_design_lock_message_bound,
            source_design_lock_verified=source_design_lock_verified,
            sandbox_workspace_guarded=guarded,
            sandbox_workspace_root=workspace_root_text,
            sandbox_workspace_root_policy=SANDBOX_WORKSPACE_ROOT_POLICY,
            requested_workspace_name=requested_workspace_name,
            normalized_workspace_name=normalized_workspace_name,
            workspace_path_preview=workspace_path_preview,
            workspace_path_within_root=workspace_path_within_root,
            required_preconditions=list(REQUIRED_PRECONDITIONS),
            allowed_future_workspace_scope=list(ALLOWED_FUTURE_WORKSPACE_SCOPE),
            forbidden_workspace_actions=list(FORBIDDEN_WORKSPACE_ACTIONS),
            blocked_reasons=blocked_reasons,
            risks=[
                "workspace guard must not be interpreted as workspace creation",
                "future writes still require isolated workspace creation logic",
                "product runtime Git writes remain forbidden",
            ],
            unknowns=[
                "actual workspace creation remains future work",
                "rollback snapshot creation remains future work",
                "readonly reviewer handoff after a real diff remains future work",
            ],
            guard_summary=self._guard_summary(guarded=guarded),
            recommended_next_step=(
                "Add Mimocode contract/API/smoke tests for P21-C workspace guard "
                "before implementing any workspace creation or controlled sandbox write."
            ),
        )

    @staticmethod
    def _workspace_root() -> Path:
        return settings.runtime_data_dir / "project-director" / "sandbox-workspaces"

    @staticmethod
    def _is_safe_dry_run_task(task: Task) -> bool:
        return ProjectDirectorSandboxWriteDesignLockService._is_safe_dry_run_task(
            task
        )

    @staticmethod
    def _first_design_lock_action(
        source_message: ProjectDirectorMessage,
    ) -> dict[str, Any] | None:
        if not source_message.suggested_actions:
            return None
        first_action = source_message.suggested_actions[0]
        if not isinstance(first_action, dict):
            return None
        if first_action.get("type") != P21_B_SANDBOX_WRITE_DESIGN_LOCK_ACTION_TYPE:
            return None
        return first_action

    @staticmethod
    def _normalize_workspace_name(
        *,
        requested_workspace_name: str | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> str | None:
        if requested_workspace_name is None:
            return f"pd-{str(session_id)[:8]}-{str(source_task_id)[:8]}"

        normalized = requested_workspace_name.strip()
        if not normalized:
            blocked_reasons.append("workspace_name_required")
            return None

        if ProjectDirectorSandboxWorkspaceGuardService._workspace_name_not_allowed(
            normalized
        ):
            blocked_reasons.append("workspace_name_not_allowed")
            return None

        return normalized

    @staticmethod
    def _workspace_name_not_allowed(value: str) -> bool:
        lowered = value.lower()
        if lowered.startswith("file://"):
            return True
        if any(fragment in value for fragment in FORBIDDEN_WORKSPACE_NAME_FRAGMENTS):
            return True
        if Path(value).is_absolute():
            return True
        if PureWindowsPath(value).drive:
            return True
        return WORKSPACE_NAME_PATTERN.fullmatch(value) is None

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
    def _any_runtime_write_flag_enabled(action: dict[str, Any]) -> bool:
        runtime_write_flags = (
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
        return any(action.get(flag) is True for flag in runtime_write_flags)

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        return path == root or root in path.parents

    @staticmethod
    def _guard_summary(*, guarded: bool) -> str:
        if not guarded:
            return (
                "P21-C sandbox workspace root guard was blocked before any "
                "directory creation, file write, patch application, worktree, "
                "executor, Worker, Task, Run, rollback, or Git side effect."
            )
        return (
            "P21-C sandbox workspace root guard recorded a backend-controlled "
            "workspace root and validated a path preview under that root while "
            "leaving all directory, write, worktree, executor, Worker, Task, "
            "Run, rollback, and Git permissions disabled."
        )

    @staticmethod
    def _workspace_guard_action(
        result: ProjectDirectorSandboxWorkspaceGuardResult,
    ) -> dict[str, Any]:
        return {
            "type": P21_C_SANDBOX_WORKSPACE_GUARD_ACTION_TYPE,
            "guard_status": result.guard_status,
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
            "guard_mode": result.guard_mode,
            "source_design_lock_status": result.source_design_lock_status,
            "source_design_lock_message_bound": (
                result.source_design_lock_message_bound
            ),
            "source_design_lock_verified": result.source_design_lock_verified,
            "sandbox_workspace_guarded": result.sandbox_workspace_guarded,
            "sandbox_workspace_root": result.sandbox_workspace_root,
            "sandbox_workspace_root_policy": result.sandbox_workspace_root_policy,
            "requested_workspace_name": result.requested_workspace_name,
            "normalized_workspace_name": result.normalized_workspace_name,
            "workspace_path_preview": result.workspace_path_preview,
            "workspace_path_within_root": result.workspace_path_within_root,
            "workspace_created": False,
            "workspace_written": False,
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
            "allowed_future_workspace_scope": list(
                result.allowed_future_workspace_scope
            ),
            "forbidden_workspace_actions": list(result.forbidden_workspace_actions),
            "blocked_reasons": list(result.blocked_reasons),
            "risks": list(result.risks),
            "unknowns": list(result.unknowns),
            "guard_summary": result.guard_summary,
            "recommended_next_step": result.recommended_next_step,
            "ai_project_director_total_loop": "Partial",
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
    "ConfirmedSandboxWorkspaceGuard",
    "P21_C_SANDBOX_WORKSPACE_GUARD_SOURCE_DETAIL",
    "ProjectDirectorSandboxWorkspaceGuardService",
)
