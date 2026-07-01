"""Controlled sandbox candidate business file write service for P21-C."""

from __future__ import annotations

import json
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
from app.domain.project_director_sandbox_candidate_file_write import (
    CandidateSandboxBlockedFile,
    CandidateSandboxFileWrite,
    CandidateSandboxWrittenFile,
    ProjectDirectorSandboxCandidateFileWriteResult,
    SandboxCandidateFileWriteMode,
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
from app.services.project_director_sandbox_workspace_creation_service import (
    P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
    P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_workspace_guard_service import (
    ProjectDirectorSandboxWorkspaceGuardService,
)
from app.services.project_director_sandbox_workspace_manifest_write_service import (
    INTERNAL_MANIFEST_DIR_NAME,
    INTERNAL_MANIFEST_FILE_NAME,
    P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE,
    P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL,
)


P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL = (
    "p21_c_sandbox_candidate_files_written"
)
P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE = (
    "p21_c_sandbox_candidate_files_write_record"
)

MAX_CANDIDATE_FILES = 20
MAX_CANDIDATE_FILE_CONTENT_BYTES = 200 * 1024
MAX_CANDIDATE_FILES_TOTAL_CONTENT_BYTES = 1024 * 1024

REQUIRED_PRECONDITIONS = [
    "p21_c_workspace_manifest_write_required",
    "p21_c_operation_manifest_guard_required",
    "internal_manifest_required",
    "workspace_path_required",
    "backend_runtime_workspace_root_required",
    "root_strict_subdirectory_check_required",
    "workspace_directory_required",
    "user_confirmation_required",
    "candidate_files_only_mode_required",
    "candidate_files_required",
    "candidate_path_policy_required",
    "allowed_operation_path_match_required",
    "no_target_file_content_read_required",
    "no_real_diff_required",
    "no_git_worktree_required",
    "cleanup_future_step_required",
    "readonly_reviewer_required_after_real_diff",
]

ALLOWED_FUTURE_CANDIDATE_WRITE_SCOPE = [
    "current step may only write requested candidate files inside sandbox workspace",
    "future real diff generation must be separate",
    "future readonly reviewer must happen after real diff",
    "future patch apply must be separate and user-confirmed",
    "future cleanup must be separate",
    "product runtime Git operations remain forbidden",
]

FORBIDDEN_CANDIDATE_WRITE_ACTIONS = [
    "no_main_worktree_write",
    "no_product_runtime_git_write",
    "no_target_file_content_read_in_candidate_write",
    "no_real_diff_generation_in_candidate_write",
    "no_patch_apply_in_candidate_write",
    "no_git_worktree_creation_in_candidate_write",
    "no_worker_dispatch",
    "no_task_creation",
    "no_run_creation",
    "no_executor_start",
    "no_automatic_commit",
    "no_push",
    "no_pr",
    "no_merge",
    "no_cleanup_in_candidate_write",
    "no_write_outside_sandbox_workspace",
    "no_write_under_internal_ai_project_director_dir",
    "no_write_paths_not_declared_by_operation_manifest",
]

SOURCE_MANIFEST_WRITE_FALSE_FLAGS = (
    "business_file_written",
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

SOURCE_OPERATION_MANIFEST_FALSE_FLAGS = (
    "workspace_created",
    "workspace_written",
    "file_written",
    "controlled_sandbox_write_enabled",
    "sandbox_write_allowed",
    "product_runtime_git_write_allowed",
    "main_worktree_write_allowed",
    "worktree_write_allowed",
    "file_write_allowed",
    "actual_patch_applied",
    "real_code_modified",
    "real_diff_generated",
    "patch_applied",
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
    "target_file_content_read",
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
class ConfirmedSandboxCandidateFileWrite:
    """P21-C candidate file write result and optional persisted message."""

    result: ProjectDirectorSandboxCandidateFileWriteResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class _PreparedCandidateFile:
    request: CandidateSandboxFileWrite
    target_path: Path
    content_size_bytes: int


class ProjectDirectorSandboxCandidateFileWriteService:
    """Write only candidate files declared by the operation manifest."""

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

    def confirm_candidate_files_write(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        candidate_files: list[CandidateSandboxFileWrite],
        write_mode: SandboxCandidateFileWriteMode = "candidate_files_only",
    ) -> ConfirmedSandboxCandidateFileWrite:
        """Validate P21-C-D/B sources, write candidates, and persist a message."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("sandbox candidate file write repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        source_message = self._message_repository.get_by_id(source_message_id)

        result = self.build_candidate_files_write_from_sources(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            candidate_files=candidate_files,
            write_mode=write_mode,
        )
        if result.candidate_write_status == "blocked":
            return ConfirmedSandboxCandidateFileWrite(result=result, message=None)

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已在 P21-C sandbox workspace 内写入候选业务文件。"
                    "本轮只在 sandbox workspace 内写入候选业务文件，"
                    "没有写主项目文件，没有读取 target file content，"
                    "没有生成 real diff，没有应用 patch，没有创建 git worktree，"
                    "没有执行 Git 写入，没有调用 Worker / Codex / Claude；"
                    "AI Project Director 总闭环仍为 Partial。"
                    "后续必须单独生成 real diff，再交给 readonly reviewer 审查，"
                    "不能直接合入。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_files_write",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL,
                suggested_actions=[self._candidate_files_write_action(result)],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=list(FORBIDDEN_CANDIDATE_WRITE_ACTIONS),
            )
        )
        self._message_repository.commit()
        return ConfirmedSandboxCandidateFileWrite(result=result, message=message)

    def build_candidate_files_write_from_sources(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        candidate_files: list[CandidateSandboxFileWrite],
        write_mode: SandboxCandidateFileWriteMode = "candidate_files_only",
    ) -> ProjectDirectorSandboxCandidateFileWriteResult:
        """Validate the full P21-C-D -> P21-C-C -> P21-C-B chain and write files."""

        blocked_reasons: list[str] = []
        candidate_blocked_files: list[CandidateSandboxBlockedFile] = []
        prepared_files: list[_PreparedCandidateFile] = []

        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        elif not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_not_safe_dry_run")
        if source_message is None:
            blocked_reasons.append("source_message_missing")
        if write_mode != "candidate_files_only":
            blocked_reasons.append("real_write_not_allowed_beyond_candidate_files")

        source_action = self._manifest_write_action(
            source_message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        source_manifest_write_status = self._as_optional_str(
            source_action.get("manifest_write_status") if source_action else None
        )
        source_manifest_write_message_bound = (
            source_action is not None
            and source_action.get("source_task_id") == str(source_task_id)
            and source_message is not None
            and source_message.session_id == session_id
            and source_message.source_detail
            == P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL
        )
        if source_action is not None:
            if source_manifest_write_status not in ("written", "overwritten"):
                blocked_reasons.append("source_manifest_write_not_written_or_overwritten")
            if not source_manifest_write_message_bound:
                blocked_reasons.append(
                    "source_task_not_bound_to_workspace_manifest_write"
                )
            if source_action.get("manifest_file_written") is not True:
                blocked_reasons.append("source_manifest_write_not_written_or_overwritten")
            if not self._manifest_write_action_is_no_write_except_manifest(
                source_action
            ):
                blocked_reasons.append("source_manifest_write_not_no_write_except_manifest")
            if source_action.get("ai_project_director_total_loop") != "Partial":
                blocked_reasons.append("source_manifest_write_not_no_write_except_manifest")

        workspace_path_text = self._as_optional_str(
            source_action.get("workspace_path") if source_action else None
        )
        workspace_root = self._resolved_workspace_root(blocked_reasons)
        workspace_root_text = workspace_root.as_posix() if workspace_root else None
        workspace_path = self._resolved_workspace_path(
            workspace_path_text,
            blocked_reasons,
        )
        workspace_path_text_resolved = workspace_path.as_posix() if workspace_path else None
        workspace_path_within_root = (
            workspace_root is not None
            and workspace_path is not None
            and self._is_strict_child_of(workspace_path, workspace_root)
        )
        if not workspace_path_text:
            blocked_reasons.append("workspace_path_missing")
        if not workspace_path_within_root:
            if workspace_root is not None and workspace_path == workspace_root:
                blocked_reasons.append("workspace_path_must_be_workspace_subdirectory")
            else:
                blocked_reasons.append("workspace_path_not_within_root")
        if workspace_path is not None:
            try:
                if not workspace_path.exists():
                    blocked_reasons.append("workspace_path_missing_on_disk")
                elif not workspace_path.is_dir():
                    blocked_reasons.append("workspace_path_is_not_directory")
            except OSError:
                blocked_reasons.append("workspace_path_is_not_directory")

        internal_manifest_file_path = (
            (workspace_path / INTERNAL_MANIFEST_DIR_NAME / INTERNAL_MANIFEST_FILE_NAME)
            .resolve(strict=False)
            if workspace_path is not None
            else None
        )
        internal_manifest_file_text = (
            internal_manifest_file_path.as_posix()
            if internal_manifest_file_path is not None
            else None
        )
        manifest_payload = self._read_internal_manifest(
            internal_manifest_file_path,
            workspace_path=workspace_path,
            blocked_reasons=blocked_reasons,
        )
        internal_manifest_verified = self._internal_manifest_verified(
            manifest_payload,
            workspace_path=workspace_path,
            internal_manifest_file_path=internal_manifest_file_path,
            blocked_reasons=blocked_reasons,
        )

        source_workspace_creation_message_id = self._uuid_from_action(
            source_action,
            "source_message_id",
        )
        workspace_creation_message = self._get_message(source_workspace_creation_message_id)
        workspace_creation_action = self._workspace_creation_action(
            workspace_creation_message=workspace_creation_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )

        source_operation_manifest_message_id = self._uuid_from_action(
            workspace_creation_action,
            "source_message_id",
        )
        operation_manifest_message = self._get_message(source_operation_manifest_message_id)
        operation_manifest_action = self._operation_manifest_action(
            operation_manifest_message=operation_manifest_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        allowed_operation_paths = self._allowed_operation_paths(
            operation_manifest_action,
            blocked_reasons=blocked_reasons,
        )
        allowed_operations_by_path = self._allowed_operations_by_path(
            operation_manifest_action
        )

        requested_count = len(candidate_files)
        if requested_count == 0:
            blocked_reasons.append("candidate_files_required")
        if requested_count > MAX_CANDIDATE_FILES:
            blocked_reasons.append("candidate_files_too_many")

        total_content_size = 0
        seen_relative_paths: set[str] = set()
        for candidate in candidate_files:
            file_reasons: list[str] = []
            content_size = self._content_size(candidate.content, file_reasons)
            total_content_size += content_size
            target_path = self._candidate_target_path(
                candidate.relative_path,
                workspace_path=workspace_path,
                allowed_operation_paths=allowed_operation_paths,
                allowed_operations_by_path=allowed_operations_by_path,
                requested_operation=candidate.operation,
                file_reasons=file_reasons,
            )
            if candidate.relative_path in seen_relative_paths:
                file_reasons.append("candidate_file_path_not_allowed")
            seen_relative_paths.add(candidate.relative_path)
            if content_size > MAX_CANDIDATE_FILE_CONTENT_BYTES:
                file_reasons.append("candidate_file_content_too_large")
            if file_reasons:
                candidate_blocked_files.append(
                    CandidateSandboxBlockedFile(
                        relative_path=candidate.relative_path,
                        operation=candidate.operation,
                        blocked_reasons=self._dedupe(file_reasons),
                    )
                )
                blocked_reasons.extend(file_reasons)
                continue
            if target_path is not None:
                prepared_files.append(
                    _PreparedCandidateFile(
                        request=candidate,
                        target_path=target_path,
                        content_size_bytes=content_size,
                    )
                )

        if total_content_size > MAX_CANDIDATE_FILES_TOTAL_CONTENT_BYTES:
            blocked_reasons.append("candidate_files_total_content_too_large")

        if not blocked_reasons:
            for prepared_file in prepared_files:
                self._candidate_file_write_preflight(
                    prepared_file.target_path,
                    candidate_blocked_files=candidate_blocked_files,
                    relative_path=prepared_file.request.relative_path,
                    operation=prepared_file.request.operation,
                    blocked_reasons=blocked_reasons,
                )

        source_manifest_write_verified = (
            source_action is not None
            and source_manifest_write_status in ("written", "overwritten")
            and source_manifest_write_message_bound
            and source_action.get("manifest_file_written") is True
            and self._manifest_write_action_is_no_write_except_manifest(source_action)
            and source_action.get("ai_project_director_total_loop") == "Partial"
            and workspace_path_within_root
            and internal_manifest_verified
            and operation_manifest_action is not None
            and bool(allowed_operation_paths)
        )

        candidate_written_files: list[CandidateSandboxWrittenFile] = []
        blocked_reasons = self._dedupe(blocked_reasons)
        if not blocked_reasons:
            try:
                for prepared_file in prepared_files:
                    prepared_file.target_path.parent.mkdir(parents=True, exist_ok=True)
                    prepared_file.target_path.write_text(
                        prepared_file.request.content,
                        encoding="utf-8",
                    )
                    candidate_written_files.append(
                        CandidateSandboxWrittenFile(
                            relative_path=prepared_file.request.relative_path,
                            workspace_file_path=prepared_file.target_path.as_posix(),
                            operation=prepared_file.request.operation,
                            content_encoding=prepared_file.request.content_encoding,
                            content_size_bytes=prepared_file.content_size_bytes,
                        )
                    )
            except OSError:
                blocked_reasons.append("candidate_file_write_failed")
                candidate_written_files = []

        blocked_reasons = self._dedupe(blocked_reasons)
        candidate_write_status = "written" if not blocked_reasons else "blocked"
        candidate_business_files_written = (
            candidate_write_status == "written" and bool(candidate_written_files)
        )
        candidate_files_written_count = (
            len(candidate_written_files) if candidate_write_status == "written" else 0
        )
        candidate_files_blocked_count = (
            len(candidate_blocked_files)
            if candidate_blocked_files
            else (requested_count if candidate_write_status == "blocked" else 0)
        )
        cleanup_required = bool(
            workspace_creation_action is not None
            and workspace_creation_action.get("cleanup_required") is True
        )

        return ProjectDirectorSandboxCandidateFileWriteResult(
            candidate_write_status=candidate_write_status,
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            write_mode=write_mode,
            source_manifest_write_status=source_manifest_write_status,
            source_manifest_write_message_bound=source_manifest_write_message_bound,
            source_manifest_write_verified=source_manifest_write_verified,
            source_workspace_creation_message_id=source_workspace_creation_message_id,
            source_operation_manifest_message_id=source_operation_manifest_message_id,
            workspace_path=workspace_path_text_resolved,
            workspace_path_within_root=workspace_path_within_root,
            workspace_root=workspace_root_text,
            internal_manifest_file_path=internal_manifest_file_text,
            internal_manifest_verified=internal_manifest_verified,
            candidate_files_requested_count=requested_count,
            candidate_files_written_count=candidate_files_written_count,
            candidate_files_blocked_count=candidate_files_blocked_count,
            candidate_written_files=candidate_written_files,
            candidate_blocked_files=candidate_blocked_files,
            candidate_business_files_written=candidate_business_files_written,
            business_file_written=candidate_business_files_written,
            cleanup_required=cleanup_required,
            cleanup_hint=self._cleanup_hint(cleanup_required=cleanup_required),
            required_preconditions=list(REQUIRED_PRECONDITIONS),
            allowed_future_candidate_write_scope=list(
                ALLOWED_FUTURE_CANDIDATE_WRITE_SCOPE
            ),
            forbidden_candidate_write_actions=list(FORBIDDEN_CANDIDATE_WRITE_ACTIONS),
            blocked_reasons=blocked_reasons,
            risks=[
                "candidate business file writes are sandbox-only and not main project writes",
                "candidate writes must be reviewed through a separate real diff step",
                "product runtime Git writes remain forbidden",
            ],
            unknowns=[
                "real diff generation remains future work",
                "readonly reviewer handoff remains future work",
                "patch application and cleanup remain future work",
            ],
            candidate_write_summary=self._candidate_write_summary(
                candidate_write_status=candidate_write_status,
            ),
            recommended_next_step=(
                "Generate a separate real diff from the sandbox candidate files, "
                "then send that diff to a readonly reviewer before any patch, "
                "cleanup, executor, Worker, Task, Run, or product runtime Git step."
            ),
        )

    def _manifest_write_action(
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
            != P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL
        ):
            blocked_reasons.append(
                "source_message_is_not_p21_c_workspace_manifest_written"
            )
        action = self._first_action(
            source_message,
            expected_type=P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("p21_c_workspace_manifest_write_record_missing")
        elif action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append(
                "source_task_not_bound_to_workspace_manifest_write"
            )
        return action

    def _workspace_creation_action(
        self,
        *,
        workspace_creation_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if workspace_creation_message is None:
            blocked_reasons.append("source_workspace_creation_message_missing")
            return None
        if (
            workspace_creation_message.session_id != session_id
            or workspace_creation_message.source_detail
            != P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_workspace_creation_message_missing")
        action = self._first_action(
            workspace_creation_message,
            expected_type=P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("source_workspace_creation_message_missing")
            return None
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_workspace_creation_message_missing")
        return action

    def _operation_manifest_action(
        self,
        *,
        operation_manifest_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if operation_manifest_message is None:
            blocked_reasons.append("source_operation_manifest_message_missing")
            return None
        if (
            operation_manifest_message.session_id != session_id
            or operation_manifest_message.source_detail
            != P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_operation_manifest_invalid")
        action = self._first_action(
            operation_manifest_message,
            expected_type=P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("source_operation_manifest_invalid")
            return None
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_operation_manifest_invalid")
        if action.get("manifest_status") != "manifested":
            blocked_reasons.append("source_operation_manifest_invalid")
        if action.get("operation_manifest_created") is not True:
            blocked_reasons.append("source_operation_manifest_invalid")
        allowed_count = action.get("manifest_allowed_operations_count")
        if not isinstance(allowed_count, int) or allowed_count <= 0:
            blocked_reasons.append("operation_manifest_allowed_paths_missing")
        if not isinstance(action.get("allowed_operation_paths"), list) or not action.get(
            "allowed_operation_paths"
        ):
            blocked_reasons.append("operation_manifest_allowed_paths_missing")
        if not self._operation_manifest_action_is_no_write(action):
            blocked_reasons.append("source_operation_manifest_invalid")
        if action.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("source_operation_manifest_invalid")
        return action

    def _read_internal_manifest(
        self,
        internal_manifest_file_path: Path | None,
        *,
        workspace_path: Path | None,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if internal_manifest_file_path is None or workspace_path is None:
            blocked_reasons.append("internal_manifest_missing")
            return None
        expected_path = (
            workspace_path / INTERNAL_MANIFEST_DIR_NAME / INTERNAL_MANIFEST_FILE_NAME
        ).resolve(strict=False)
        if internal_manifest_file_path != expected_path:
            blocked_reasons.append("internal_manifest_path_mismatch")
            return None
        try:
            if not internal_manifest_file_path.exists():
                blocked_reasons.append("internal_manifest_missing")
                return None
            if not internal_manifest_file_path.is_file():
                blocked_reasons.append("internal_manifest_missing")
                return None
            raw_value = internal_manifest_file_path.read_text(encoding="utf-8")
        except OSError:
            blocked_reasons.append("internal_manifest_missing")
            return None
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError:
            blocked_reasons.append("internal_manifest_invalid_json")
            return None
        if not isinstance(payload, dict):
            blocked_reasons.append("internal_manifest_invalid_json")
            return None
        return payload

    def _internal_manifest_verified(
        self,
        payload: dict[str, Any] | None,
        *,
        workspace_path: Path | None,
        internal_manifest_file_path: Path | None,
        blocked_reasons: list[str],
    ) -> bool:
        if payload is None or workspace_path is None or internal_manifest_file_path is None:
            return False
        expected_path = (
            workspace_path / INTERNAL_MANIFEST_DIR_NAME / INTERNAL_MANIFEST_FILE_NAME
        ).resolve(strict=False)
        if payload.get("schema_version") != "p21-c-d.v1":
            blocked_reasons.append("internal_manifest_schema_invalid")
        if payload.get("internal_manifest_only") is not True:
            blocked_reasons.append("internal_manifest_schema_invalid")
        if payload.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("internal_manifest_schema_invalid")
        if payload.get("manifest_file_path") != expected_path.as_posix():
            blocked_reasons.append("internal_manifest_path_mismatch")
        return (
            payload.get("schema_version") == "p21-c-d.v1"
            and payload.get("internal_manifest_only") is True
            and payload.get("ai_project_director_total_loop") == "Partial"
            and payload.get("manifest_file_path") == expected_path.as_posix()
            and internal_manifest_file_path == expected_path
        )

    def _candidate_target_path(
        self,
        relative_path: str,
        *,
        workspace_path: Path | None,
        allowed_operation_paths: set[str],
        allowed_operations_by_path: dict[str, set[str]],
        requested_operation: str,
        file_reasons: list[str],
    ) -> Path | None:
        normalized_path = relative_path.strip() if isinstance(relative_path, str) else ""
        if not normalized_path:
            file_reasons.append("candidate_file_path_missing")
            return None
        if not self._candidate_path_is_allowed(normalized_path):
            file_reasons.append("candidate_file_path_not_allowed")
            return None
        if normalized_path not in allowed_operation_paths:
            file_reasons.append("candidate_file_path_not_declared_by_manifest")
        if requested_operation not in allowed_operations_by_path.get(normalized_path, set()):
            file_reasons.append("candidate_file_operation_not_allowed")
        if workspace_path is None:
            file_reasons.append("candidate_file_path_escapes_workspace")
            return None
        try:
            target_path = (workspace_path / normalized_path).resolve(strict=False)
        except OSError:
            file_reasons.append("candidate_file_path_escapes_workspace")
            return None
        if not self._is_relative_to(target_path, workspace_path):
            file_reasons.append("candidate_file_path_escapes_workspace")
        internal_dir_path = (workspace_path / INTERNAL_MANIFEST_DIR_NAME).resolve(
            strict=False
        )
        if target_path == internal_dir_path or internal_dir_path in target_path.parents:
            file_reasons.append("candidate_file_path_targets_internal_dir")
        return target_path

    @staticmethod
    def _candidate_path_is_allowed(path: str) -> bool:
        if Path(path).is_absolute() or PureWindowsPath(path).drive:
            return False
        path_parts = Path(path).parts
        if ".." in path_parts:
            return False
        if any(fragment in path for fragment in FORBIDDEN_PATH_FRAGMENTS):
            return False
        lowered = path.lower()
        if lowered.startswith("file://"):
            return False
        return True

    @staticmethod
    def _candidate_file_write_preflight(
        target_path: Path,
        *,
        candidate_blocked_files: list[CandidateSandboxBlockedFile],
        relative_path: str,
        operation: str,
        blocked_reasons: list[str],
    ) -> None:
        file_reasons: list[str] = []
        try:
            if target_path.parent.exists() and not target_path.parent.is_dir():
                file_reasons.append("candidate_file_write_failed")
            if target_path.exists() and target_path.is_dir():
                file_reasons.append("candidate_file_write_failed")
        except OSError:
            file_reasons.append("candidate_file_write_failed")
        if not file_reasons:
            return
        candidate_blocked_files.append(
            CandidateSandboxBlockedFile(
                relative_path=relative_path,
                operation=operation,
                blocked_reasons=file_reasons,
            )
        )
        blocked_reasons.extend(file_reasons)

    @staticmethod
    def _content_size(content: str, file_reasons: list[str]) -> int:
        try:
            return len(content.encode("utf-8"))
        except UnicodeEncodeError:
            file_reasons.append("candidate_file_content_too_large")
            return MAX_CANDIDATE_FILE_CONTENT_BYTES + 1

    @staticmethod
    def _allowed_operation_paths(
        action: dict[str, Any] | None,
        *,
        blocked_reasons: list[str],
    ) -> set[str]:
        if action is None:
            return set()
        raw_paths = action.get("allowed_operation_paths")
        if not isinstance(raw_paths, list):
            blocked_reasons.append("operation_manifest_allowed_paths_missing")
            return set()
        allowed_paths = {
            path.strip()
            for path in raw_paths
            if isinstance(path, str) and path.strip()
        }
        if not allowed_paths:
            blocked_reasons.append("operation_manifest_allowed_paths_missing")
        return allowed_paths

    @staticmethod
    def _allowed_operations_by_path(action: dict[str, Any] | None) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        if action is None:
            return result
        raw_operations = action.get("manifest_operations")
        if not isinstance(raw_operations, list):
            return result
        for item in raw_operations:
            if not isinstance(item, dict):
                continue
            if item.get("operation_manifest_allowed") is not True:
                continue
            path = item.get("path")
            operation = item.get("operation")
            if not isinstance(path, str) or not path.strip():
                continue
            if operation not in ("create", "update"):
                continue
            result.setdefault(path.strip(), set()).add(operation)
        return result

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
    def _manifest_write_action_is_no_write_except_manifest(
        action: dict[str, Any],
    ) -> bool:
        return all(action.get(flag) is False for flag in SOURCE_MANIFEST_WRITE_FALSE_FLAGS)

    @staticmethod
    def _operation_manifest_action_is_no_write(action: dict[str, Any]) -> bool:
        return all(action.get(flag) is False for flag in SOURCE_OPERATION_MANIFEST_FALSE_FLAGS)

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        return path == root or root in path.parents

    @staticmethod
    def _is_strict_child_of(path: Path, root: Path) -> bool:
        return root in path.parents

    @staticmethod
    def _as_optional_str(value: Any) -> str | None:
        return value if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _cleanup_hint(*, cleanup_required: bool) -> str:
        if cleanup_required:
            return (
                "cleanup_required=true is inherited from sandbox workspace creation; "
                "no cleanup was performed in candidate file write."
            )
        return (
            "cleanup_required=false because the source workspace did not require "
            "cleanup; no cleanup was performed in candidate file write."
        )

    @staticmethod
    def _candidate_write_summary(*, candidate_write_status: str) -> str:
        if candidate_write_status == "written":
            return (
                "P21-C sandbox candidate business file write wrote only requested "
                "candidate files inside the sandbox workspace. It did not write main "
                "project files, read target content, generate diffs, apply patches, "
                "create worktrees, dispatch Workers, create Tasks/Runs, clean up "
                "directories, or perform Git writes."
            )
        return (
            "P21-C sandbox candidate business file write was blocked before candidate "
            "file write, main project write, target content read, diff generation, "
            "patch application, worktree, executor, Worker, Task, Run, cleanup, or "
            "Git side effect."
        )

    @staticmethod
    def _candidate_files_write_action(
        result: ProjectDirectorSandboxCandidateFileWriteResult,
    ) -> dict[str, Any]:
        return {
            "type": P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
            "candidate_write_status": result.candidate_write_status,
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
            "internal_manifest_file_path": result.internal_manifest_file_path,
            "candidate_files_written_count": result.candidate_files_written_count,
            "candidate_written_files": [
                item.model_dump(mode="json") for item in result.candidate_written_files
            ],
            "candidate_business_files_written": (
                result.candidate_business_files_written
            ),
            "business_file_written": result.business_file_written,
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
    "ConfirmedSandboxCandidateFileWrite",
    "P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE",
    "P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL",
    "ProjectDirectorSandboxCandidateFileWriteService",
)
