"""Controlled workspace evidence manifest write service for Project Director P21-C."""

from __future__ import annotations

import json
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
from app.domain.project_director_sandbox_workspace_manifest_write import (
    ProjectDirectorSandboxWorkspaceManifestWriteResult,
    SandboxWorkspaceManifestWriteMode,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_workspace_creation_service import (
    P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
    P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_workspace_guard_service import (
    ProjectDirectorSandboxWorkspaceGuardService,
)


P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL = (
    "p21_c_sandbox_workspace_manifest_written"
)
P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE = (
    "p21_c_sandbox_workspace_manifest_write_record"
)
INTERNAL_MANIFEST_DIR_NAME = ".ai-project-director"
INTERNAL_MANIFEST_FILE_NAME = "workspace-manifest.json"

REQUIRED_PRECONDITIONS = [
    "p21_c_workspace_creation_required",
    "workspace_path_required",
    "backend_runtime_workspace_root_required",
    "root_containment_check_required",
    "workspace_directory_required",
    "user_confirmation_required",
    "internal_manifest_only_mode_required",
    "no_business_file_write_required",
    "no_target_file_content_read_required",
    "no_real_diff_required",
    "no_git_worktree_required",
    "cleanup_future_step_required",
    "readonly_reviewer_required_after_real_diff",
]

ALLOWED_FUTURE_MANIFEST_WRITE_SCOPE = [
    "current step may only write internal evidence manifest",
    "future candidate file write must be separate",
    "future real diff generation must be separate",
    "future readonly reviewer must happen after real diff",
    "future cleanup must be separate",
    "product runtime Git operations remain forbidden",
]

FORBIDDEN_MANIFEST_WRITE_ACTIONS = [
    "no_business_file_write_in_manifest_step",
    "no_target_file_content_read_in_manifest_step",
    "no_real_diff_generation_in_manifest_step",
    "no_patch_apply_in_manifest_step",
    "no_git_worktree_creation_in_manifest_step",
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
    "no_cleanup_in_manifest_write",
]

SOURCE_NO_WRITE_FLAGS = (
    "workspace_written",
    "file_written",
    "manifest_file_written",
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

ALLOWED_NEXT_STEPS = [
    "candidate_file_write_in_sandbox",
    "real_diff_generation_after_candidate_write",
    "readonly_reviewer_after_real_diff",
    "cleanup_future_step",
]

MANIFEST_FORBIDDEN_ACTIONS = [
    "no_business_file_write_in_manifest_step",
    "no_target_file_content_read_in_manifest_step",
    "no_real_diff_generation_in_manifest_step",
    "no_patch_apply_in_manifest_step",
    "no_worktree_creation_in_manifest_step",
    "no_product_runtime_git_write",
    "no_worker_dispatch",
    "no_task_creation",
    "no_run_creation",
    "no_executor_start",
]


@dataclass(frozen=True, slots=True)
class ConfirmedSandboxWorkspaceManifestWrite:
    """P21-C workspace manifest write result and optional persisted message."""

    result: ProjectDirectorSandboxWorkspaceManifestWriteResult
    message: ProjectDirectorMessage | None


class ProjectDirectorSandboxWorkspaceManifestWriteService:
    """Write only the fixed internal evidence manifest inside a sandbox workspace."""

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

    def confirm_workspace_manifest_write(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        write_mode: SandboxWorkspaceManifestWriteMode = "internal_manifest_only",
    ) -> ConfirmedSandboxWorkspaceManifestWrite:
        """Validate the P21-C-C source and write the internal manifest."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("sandbox workspace manifest write repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        source_message = self._message_repository.get_by_id(source_message_id)

        result = self.build_workspace_manifest_write_from_sources(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            write_mode=write_mode,
        )
        if result.manifest_write_status == "blocked":
            return ConfirmedSandboxWorkspaceManifestWrite(result=result, message=None)

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已写入 P21-C sandbox workspace 内部 evidence manifest 文件。"
                    "本轮只写入 sandbox workspace 内部 evidence manifest 文件，"
                    "没有写业务文件，没有读取 target file content，没有生成 real diff，"
                    "没有应用 patch，没有创建 git worktree，没有执行 Git 写入，"
                    "没有调用 Worker / Codex / Claude；"
                    "AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_workspace_manifest_write",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL,
                suggested_actions=[self._workspace_manifest_write_action(result)],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.MEDIUM,
                forbidden_actions_detected=list(FORBIDDEN_MANIFEST_WRITE_ACTIONS),
            )
        )
        self._message_repository.commit()
        return ConfirmedSandboxWorkspaceManifestWrite(result=result, message=message)

    def build_workspace_manifest_write_from_sources(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        write_mode: SandboxWorkspaceManifestWriteMode = "internal_manifest_only",
    ) -> ProjectDirectorSandboxWorkspaceManifestWriteResult:
        """Validate source workspace creation and write the fixed manifest file."""

        blocked_reasons: list[str] = []
        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        elif not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_not_safe_dry_run")
        if source_message is None:
            blocked_reasons.append("source_message_missing")
        if write_mode != "internal_manifest_only":
            blocked_reasons.append("real_write_not_allowed_beyond_internal_manifest")

        source_action = self._workspace_creation_action(
            source_message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        source_workspace_creation_status = self._as_optional_str(
            source_action.get("creation_status") if source_action else None
        )
        source_workspace_creation_message_bound = (
            source_action is not None
            and source_action.get("source_task_id") == str(source_task_id)
            and source_message is not None
            and source_message.session_id == session_id
            and source_message.source_detail
            == P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL
        )

        workspace_path_text = self._as_optional_str(
            source_action.get("workspace_path") if source_action else None
        )
        workspace_root = self._resolved_workspace_root(blocked_reasons)
        workspace_root_text = workspace_root.as_posix() if workspace_root else None
        workspace_path = self._resolved_workspace_path(
            workspace_path_text,
            blocked_reasons,
        )
        workspace_path_resolved_text = (
            workspace_path.as_posix() if workspace_path else None
        )
        workspace_path_within_root = (
            workspace_root is not None
            and workspace_path is not None
            and self._is_relative_to(workspace_path, workspace_root)
        )

        if source_action is not None:
            if source_workspace_creation_status not in ("created", "already_exists"):
                blocked_reasons.append(
                    "source_workspace_creation_not_created_or_existing"
                )
            if not source_workspace_creation_message_bound:
                blocked_reasons.append("source_task_not_bound_to_workspace_creation")
            if source_action.get("workspace_path_within_root") is not True:
                blocked_reasons.append("workspace_path_not_within_root")
            if not (
                source_action.get("workspace_created") is True
                or source_action.get("workspace_already_existed") is True
            ):
                blocked_reasons.append(
                    "source_workspace_creation_not_created_or_existing"
                )
            if not self._workspace_creation_action_is_no_write(source_action):
                blocked_reasons.append("source_workspace_creation_not_no_write")
            if source_action.get("ai_project_director_total_loop") != "Partial":
                blocked_reasons.append("source_workspace_creation_not_no_write")

        if not workspace_path_text:
            blocked_reasons.append("workspace_path_missing")
        if not workspace_path_within_root:
            blocked_reasons.append("workspace_path_not_within_root")
        if workspace_path is not None:
            try:
                if not workspace_path.exists():
                    blocked_reasons.append("workspace_path_missing_on_disk")
                elif not workspace_path.is_dir():
                    blocked_reasons.append("workspace_path_is_not_directory")
            except OSError:
                blocked_reasons.append("workspace_path_is_not_directory")

        manifest_dir_path: Path | None = None
        manifest_file_path: Path | None = None
        manifest_dir_text: str | None = None
        manifest_file_text: str | None = None
        if workspace_path is not None:
            try:
                manifest_dir_path = (
                    workspace_path / INTERNAL_MANIFEST_DIR_NAME
                ).resolve(strict=False)
                manifest_file_path = (
                    manifest_dir_path / INTERNAL_MANIFEST_FILE_NAME
                ).resolve(strict=False)
                manifest_dir_text = manifest_dir_path.as_posix()
                manifest_file_text = manifest_file_path.as_posix()
            except OSError:
                blocked_reasons.append("manifest_file_path_not_within_workspace")

        manifest_path_within_workspace = (
            workspace_path is not None
            and manifest_dir_path is not None
            and manifest_file_path is not None
            and self._is_relative_to(manifest_dir_path, workspace_path)
            and self._is_relative_to(manifest_file_path, workspace_path)
        )
        if not manifest_path_within_workspace:
            blocked_reasons.append("manifest_file_path_not_within_workspace")

        source_workspace_creation_verified = (
            source_action is not None
            and source_workspace_creation_status in ("created", "already_exists")
            and source_workspace_creation_message_bound
            and source_action.get("workspace_path_within_root") is True
            and (
                source_action.get("workspace_created") is True
                or source_action.get("workspace_already_existed") is True
            )
            and self._workspace_creation_action_is_no_write(source_action)
            and source_action.get("ai_project_director_total_loop") == "Partial"
            and workspace_path_within_root
            and "workspace_path_missing_on_disk" not in blocked_reasons
            and "workspace_path_is_not_directory" not in blocked_reasons
        )

        manifest_dir_created = False
        manifest_file_written = False
        manifest_file_overwritten = False
        if (
            not blocked_reasons
            and workspace_path is not None
            and manifest_dir_path is not None
            and manifest_file_path is not None
        ):
            write_failure_reason = "manifest_dir_create_failed"
            try:
                if manifest_dir_path.exists() and not manifest_dir_path.is_dir():
                    blocked_reasons.append("manifest_dir_create_failed")
                else:
                    manifest_dir_created = not manifest_dir_path.exists()
                    manifest_dir_path.mkdir(parents=True, exist_ok=True)
                    manifest_file_overwritten = manifest_file_path.exists()
                    manifest_payload = self._manifest_payload(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        source_message_id=source_message_id,
                        workspace_path=workspace_path.as_posix(),
                        workspace_root=workspace_root_text or "",
                        source_workspace_creation_status=(
                            source_workspace_creation_status or ""
                        ),
                        manifest_file_path=manifest_file_path.as_posix(),
                    )
                    write_failure_reason = "manifest_file_write_failed"
                    manifest_file_path.write_text(
                        json.dumps(
                            manifest_payload,
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    manifest_file_written = True
            except OSError:
                blocked_reasons.append(write_failure_reason)

        blocked_reasons = self._dedupe(blocked_reasons)
        manifest_write_status = "blocked"
        if not blocked_reasons:
            manifest_write_status = (
                "overwritten" if manifest_file_overwritten else "written"
            )
        cleanup_required = bool(
            source_action is not None and source_action.get("cleanup_required") is True
        )
        cleanup_hint = self._cleanup_hint(
            cleanup_required=cleanup_required,
            manifest_file_path=manifest_file_text,
        )

        return ProjectDirectorSandboxWorkspaceManifestWriteResult(
            manifest_write_status=manifest_write_status,
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            write_mode=write_mode,
            source_workspace_creation_status=source_workspace_creation_status,
            source_workspace_creation_message_bound=(
                source_workspace_creation_message_bound
            ),
            source_workspace_creation_verified=source_workspace_creation_verified,
            workspace_path=workspace_path_resolved_text,
            workspace_path_within_root=workspace_path_within_root,
            workspace_root=workspace_root_text,
            manifest_dir_path=manifest_dir_text,
            manifest_file_path=manifest_file_text,
            manifest_dir_created=manifest_dir_created,
            manifest_file_written=manifest_file_written,
            manifest_file_overwritten=manifest_file_overwritten,
            cleanup_required=cleanup_required,
            cleanup_hint=cleanup_hint,
            required_preconditions=list(REQUIRED_PRECONDITIONS),
            allowed_future_manifest_write_scope=list(
                ALLOWED_FUTURE_MANIFEST_WRITE_SCOPE
            ),
            forbidden_manifest_write_actions=list(FORBIDDEN_MANIFEST_WRITE_ACTIONS),
            blocked_reasons=blocked_reasons,
            risks=[
                "internal manifest write must not be interpreted as business file write approval",
                "future candidate file writes still require a separate controlled step",
                "product runtime Git writes remain forbidden",
            ],
            unknowns=[
                "candidate file write remains future work",
                "real diff generation remains future work",
                "readonly reviewer handoff after a real diff remains future work",
            ],
            manifest_write_summary=self._manifest_write_summary(
                manifest_write_status=manifest_write_status,
            ),
            recommended_next_step=(
                "Mimocode should add targeted P21-C-D API/smoke evidence before "
                "any candidate business file write, target content read, real diff, "
                "patch, worktree, cleanup, executor, Worker, Task, Run, or product "
                "runtime Git step."
            ),
        )

    def _workspace_creation_action(
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
            != P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_message_is_not_p21_c_workspace_created")
        action = self._first_action(
            source_message,
            expected_type=P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("p21_c_workspace_create_record_missing")
        elif action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_task_not_bound_to_workspace_creation")
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
    def _workspace_creation_action_is_no_write(action: dict[str, Any]) -> bool:
        return all(action.get(flag) is False for flag in SOURCE_NO_WRITE_FLAGS)

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        return path == root or root in path.parents

    @staticmethod
    def _as_optional_str(value: Any) -> str | None:
        return value if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _manifest_payload(
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        workspace_path: str,
        workspace_root: str,
        source_workspace_creation_status: str,
        manifest_file_path: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": "p21-c-d.v1",
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "source_message_id": str(source_message_id),
            "workspace_path": workspace_path,
            "workspace_root": workspace_root,
            "source_workspace_creation_status": source_workspace_creation_status,
            "manifest_file_path": manifest_file_path,
            "internal_manifest_only": True,
            "business_file_write_allowed": False,
            "target_file_content_read": False,
            "real_diff_generated": False,
            "patch_applied": False,
            "worktree_created": False,
            "git_write_performed": False,
            "worker_started": False,
            "task_created": False,
            "run_created": False,
            "ai_project_director_total_loop": "Partial",
            "allowed_next_steps": list(ALLOWED_NEXT_STEPS),
            "forbidden_actions": list(MANIFEST_FORBIDDEN_ACTIONS),
        }

    @staticmethod
    def _cleanup_hint(
        *,
        cleanup_required: bool,
        manifest_file_path: str | None,
    ) -> str:
        if cleanup_required:
            return (
                "cleanup_required=true is inherited from the sandbox workspace "
                f"creation source; no cleanup was performed for {manifest_file_path}."
            )
        return (
            "cleanup_required=false because the source workspace did not require "
            "cleanup; no cleanup was performed in manifest write."
        )

    @staticmethod
    def _manifest_write_summary(*, manifest_write_status: str) -> str:
        if manifest_write_status == "written":
            return (
                "P21-C sandbox workspace evidence manifest write created only the "
                "fixed internal workspace-manifest.json file under the sandbox "
                "workspace. It did not write business files, read target content, "
                "generate diffs, apply patches, create worktrees, dispatch Workers, "
                "create Tasks/Runs, clean up directories, or perform Git writes."
            )
        if manifest_write_status == "overwritten":
            return (
                "P21-C sandbox workspace evidence manifest write overwrote only the "
                "fixed internal workspace-manifest.json file under the sandbox "
                "workspace with deterministic JSON. It did not append uncontrolled "
                "content, write business files, read target content, generate diffs, "
                "apply patches, create worktrees, dispatch Workers, create Tasks/Runs, "
                "clean up directories, or perform Git writes."
            )
        return (
            "P21-C sandbox workspace evidence manifest write was blocked before "
            "manifest file write, business file write, target content read, diff "
            "generation, patch application, worktree, executor, Worker, Task, Run, "
            "cleanup, or Git side effect."
        )

    @staticmethod
    def _workspace_manifest_write_action(
        result: ProjectDirectorSandboxWorkspaceManifestWriteResult,
    ) -> dict[str, Any]:
        return {
            "type": P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE,
            "manifest_write_status": result.manifest_write_status,
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
            "manifest_file_path": result.manifest_file_path,
            "manifest_file_written": result.manifest_file_written,
            "manifest_file_overwritten": result.manifest_file_overwritten,
            "business_file_written": False,
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
    "ConfirmedSandboxWorkspaceManifestWrite",
    "P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE",
    "P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL",
    "ProjectDirectorSandboxWorkspaceManifestWriteService",
)
