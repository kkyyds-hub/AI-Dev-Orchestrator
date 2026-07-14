"""Readonly real diff generation service for Project Director P21-C-F."""

from __future__ import annotations

import difflib
import hashlib
import json
import subprocess
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
from app.domain.project_director_sandbox_candidate_diff import (
    CandidateSandboxDiffBlockedFile,
    CandidateSandboxDiffEntry,
    P21_C_SANDBOX_CANDIDATE_DIFF_BASE_CONTENT_SOURCE_EXACT_GIT_COMMIT_OBJECT,
    P21_C_SANDBOX_CANDIDATE_DIFF_BASE_EVIDENCE_SCHEMA_VERSION,
    ProjectDirectorSandboxCandidateDiffResult,
    SandboxCandidateDiffMode,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_file_write_service import (
    P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL,
)
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


P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL = (
    "p21_c_sandbox_candidate_diff_generated"
)
P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE = (
    "p21_c_sandbox_candidate_diff_generate_record"
)

REQUIRED_PRECONDITIONS = [
    "p21_c_candidate_files_write_required",
    "p21_c_operation_manifest_guard_required",
    "internal_manifest_required",
    "workspace_path_required",
    "backend_runtime_workspace_root_required",
    "root_strict_subdirectory_check_required",
    "workspace_directory_required",
    "user_confirmation_required",
    "readonly_unified_diff_mode_required",
    "candidate_files_required",
    "candidate_file_content_read_required",
    "target_file_content_read_required",
    "allowed_operation_path_match_required",
    "no_patch_apply_required",
    "no_git_worktree_required",
    "readonly_reviewer_required_after_real_diff",
    "cleanup_future_step_required",
]

ALLOWED_FUTURE_DIFF_SCOPE = [
    "current step may only generate readonly unified diff in memory",
    "future readonly reviewer must review this diff",
    "future patch apply must be separate and user-confirmed",
    "future cleanup must be separate",
    "product runtime Git operations remain forbidden",
]

FORBIDDEN_DIFF_ACTIONS = [
    "no_main_project_file_write",
    "no_sandbox_file_write",
    "no_manifest_file_write",
    "no_patch_apply_in_diff_generation",
    "no_git_worktree_creation_in_diff_generation",
    "no_product_runtime_git_write",
    "no_worker_dispatch",
    "no_task_creation",
    "no_run_creation",
    "no_executor_start",
    "no_automatic_commit",
    "no_push",
    "no_pr",
    "no_merge",
    "no_cleanup_in_diff_generation",
]

SOURCE_CANDIDATE_WRITE_FALSE_FLAGS = (
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
class ConfirmedSandboxCandidateDiff:
    """P21-C-F readonly diff generation result and optional persisted message."""

    result: ProjectDirectorSandboxCandidateDiffResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class _PreparedCandidateDiffFile:
    relative_path: str
    operation: str
    candidate_file_path: Path
    target_file_path: Path


@dataclass(frozen=True, slots=True)
class _BaseSnapshotFingerprintEntry:
    relative_path: str
    operation: str
    base_file_existed: bool
    base_content_sha256: str | None
    candidate_content_sha256: str


class ProjectDirectorSandboxCandidateDiffService:
    """Generate readonly unified diffs from sandbox candidate files."""

    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        session_repository: ProjectDirectorSessionRepository | None = None,
        message_repository: ProjectDirectorMessageRepository | None = None,
        task_repository: TaskRepository | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository

    def confirm_candidate_diff_generation(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        diff_mode: SandboxCandidateDiffMode = "readonly_unified_diff",
        max_diff_bytes: int = 200_000,
    ) -> ConfirmedSandboxCandidateDiff:
        """Validate P21-C-E sources, generate a readonly diff, and persist message."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("sandbox candidate diff repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        source_message = self._message_repository.get_by_id(source_message_id)

        result = self.build_candidate_diff_from_sources(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            diff_mode=diff_mode,
            max_diff_bytes=max_diff_bytes,
        )
        if result.diff_generation_status == "blocked":
            return ConfirmedSandboxCandidateDiff(result=result, message=None)

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已只读读取 exact base commit object 与 sandbox candidate 文件，"
                    "并在内存中生成 P21-C-F readonly real diff。"
                    "本轮没有写主项目文件，没有写 sandbox 文件，没有写 manifest 文件，"
                    "没有应用 patch，没有创建 git worktree，没有执行 Git 写入，"
                    "没有调用 Worker / Codex / Claude；"
                    "后续必须交 readonly reviewer 审查。"
                    "AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_diff_generate",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
                suggested_actions=[self._candidate_diff_action(result)],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=list(FORBIDDEN_DIFF_ACTIONS),
            )
        )
        self._message_repository.commit()
        return ConfirmedSandboxCandidateDiff(result=result, message=message)

    def build_candidate_diff_from_sources(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        diff_mode: SandboxCandidateDiffMode = "readonly_unified_diff",
        max_diff_bytes: int = 200_000,
    ) -> ProjectDirectorSandboxCandidateDiffResult:
        """Validate the P21-C-E -> D -> C -> B chain and generate readonly diff."""

        blocked_reasons: list[str] = []
        blocked_files: list[CandidateSandboxDiffBlockedFile] = []
        prepared_files: list[_PreparedCandidateDiffFile] = []

        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        elif not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_not_safe_dry_run")
        if source_message is None:
            blocked_reasons.append("source_message_missing")
        if diff_mode != "readonly_unified_diff":
            blocked_reasons.append("real_write_not_allowed_in_diff_generation")
        if max_diff_bytes <= 0:
            blocked_reasons.append("diff_too_large")

        source_action = self._candidate_write_action(
            source_message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        source_candidate_write_status = self._as_optional_str(
            source_action.get("candidate_write_status") if source_action else None
        )
        source_candidate_write_message_bound = (
            source_action is not None
            and source_action.get("source_task_id") == str(source_task_id)
            and source_message is not None
            and source_message.session_id == session_id
            and source_message.source_detail
            == P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL
        )
        if source_action is not None:
            if source_candidate_write_status != "written":
                blocked_reasons.append("source_candidate_write_not_written")
            if not source_candidate_write_message_bound:
                blocked_reasons.append("source_task_not_bound_to_candidate_files_write")
            written_count = source_action.get("candidate_files_written_count")
            if not isinstance(written_count, int) or written_count <= 0:
                blocked_reasons.append("candidate_written_files_missing")
            if not isinstance(source_action.get("candidate_written_files"), list):
                blocked_reasons.append("candidate_written_files_missing")
            if source_action.get("candidate_business_files_written") is not True:
                blocked_reasons.append("source_candidate_write_not_written")
            if source_action.get("business_file_written") is not True:
                blocked_reasons.append("source_candidate_write_not_written")
            if not self._candidate_write_action_is_no_diff_or_patch(source_action):
                blocked_reasons.append("source_candidate_write_not_no_diff_or_patch")
            if source_action.get("ai_project_director_total_loop") != "Partial":
                blocked_reasons.append("source_candidate_write_not_no_diff_or_patch")

        source_workspace_manifest_write_message_id = self._uuid_from_action(
            source_action,
            "source_message_id",
        )
        workspace_manifest_message = self._get_message(
            source_workspace_manifest_write_message_id
        )
        workspace_manifest_action = self._workspace_manifest_action(
            workspace_manifest_message=workspace_manifest_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
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
            workspace_manifest_action,
            "source_message_id",
        )
        workspace_creation_message = self._get_message(
            source_workspace_creation_message_id
        )
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
        operation_manifest_message = self._get_message(
            source_operation_manifest_message_id
        )
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

        repo_root = self._resolved_repo_root(blocked_reasons)
        repo_root_text = repo_root.as_posix() if repo_root is not None else None
        exact_base_commit_sha = None
        ordered_scope_paths = tuple(sorted(allowed_operation_paths))
        if not blocked_reasons and repo_root is not None:
            exact_base_commit_sha = self._read_repository_head(
                repo_root,
                blocked_reasons=blocked_reasons,
            )

        raw_candidate_files = (
            source_action.get("candidate_written_files") if source_action else None
        )
        if not isinstance(raw_candidate_files, list) or not raw_candidate_files:
            blocked_reasons.append("candidate_written_files_missing")
            raw_candidate_files = []

        for raw_candidate in raw_candidate_files:
            file_reasons: list[str] = []
            relative_path = self._candidate_relative_path(raw_candidate)
            operation = self._candidate_operation(raw_candidate)
            candidate_file_path = self._candidate_file_path(
                raw_candidate,
                workspace_path=workspace_path,
                relative_path=relative_path,
                file_reasons=file_reasons,
            )
            target_file_path = self._target_file_path(
                relative_path,
                repo_root=repo_root,
                file_reasons=file_reasons,
            )

            if relative_path not in allowed_operation_paths:
                file_reasons.append("candidate_file_path_not_declared_by_manifest")
            if operation not in allowed_operations_by_path.get(relative_path, set()):
                file_reasons.append("candidate_file_operation_not_allowed")
            if candidate_file_path is not None:
                self._candidate_file_preflight(
                    candidate_file_path,
                    workspace_path=workspace_path,
                    file_reasons=file_reasons,
                )

            if file_reasons:
                blocked_files.append(
                    CandidateSandboxDiffBlockedFile(
                        relative_path=relative_path,
                        operation=operation,
                        blocked_reasons=self._dedupe(file_reasons),
                    )
                )
                blocked_reasons.extend(file_reasons)
                continue
            if candidate_file_path is not None and target_file_path is not None:
                prepared_files.append(
                    _PreparedCandidateDiffFile(
                        relative_path=relative_path,
                        operation=operation,
                        candidate_file_path=candidate_file_path,
                        target_file_path=target_file_path,
                    )
                )

        source_candidate_write_verified = (
            source_action is not None
            and source_candidate_write_status == "written"
            and source_candidate_write_message_bound
            and source_action.get("candidate_business_files_written") is True
            and source_action.get("business_file_written") is True
            and self._candidate_write_action_is_no_diff_or_patch(source_action)
            and source_action.get("ai_project_director_total_loop") == "Partial"
            and workspace_manifest_action is not None
            and workspace_path_within_root
            and internal_manifest_verified
            and operation_manifest_action is not None
            and bool(allowed_operation_paths)
        )

        diff_entries: list[CandidateSandboxDiffEntry] = []
        base_snapshot_entries: list[_BaseSnapshotFingerprintEntry] = []
        unified_diff_text = ""
        target_file_content_read = False
        candidate_file_content_read = False
        blocked_reasons = self._dedupe(blocked_reasons)
        if not blocked_reasons:
            for prepared_file in prepared_files:
                candidate_content = self._read_text_file(
                    prepared_file.candidate_file_path,
                    blocked_reason="candidate_file_not_utf8",
                    blocked_reasons=blocked_reasons,
                )
                if candidate_content is None:
                    blocked_files.append(
                        CandidateSandboxDiffBlockedFile(
                            relative_path=prepared_file.relative_path,
                            operation=prepared_file.operation,
                            blocked_reasons=["candidate_file_not_utf8"],
                        )
                    )
                    continue
                candidate_file_content_read = True
                candidate_content_sha256 = self._sha256_utf8(candidate_content)

                if prepared_file.operation == "update":
                    target_lookup_error: str | None = None
                    try:
                        target_object_type = self._git_object_type(
                            repo_root=repo_root,
                            base_commit_sha=exact_base_commit_sha,
                            relative_path=prepared_file.relative_path,
                        )
                    except (OSError, subprocess.SubprocessError):
                        target_object_type = None
                        target_lookup_error = "base_snapshot_read_failed"
                        blocked_reasons.append(target_lookup_error)
                    if target_object_type != "blob":
                        blocked_reason = target_lookup_error or (
                            "target_file_missing_for_update"
                            if target_object_type is None
                            else "target_file_not_file_in_base_commit"
                        )
                        blocked_files.append(
                            CandidateSandboxDiffBlockedFile(
                                relative_path=prepared_file.relative_path,
                                operation=prepared_file.operation,
                                blocked_reasons=[blocked_reason],
                            )
                        )
                        blocked_reasons.append(blocked_reason)
                        continue
                    target_read_error: str | None = None
                    try:
                        target_content = self._read_git_blob_text(
                            repo_root=repo_root,
                            base_commit_sha=exact_base_commit_sha,
                            relative_path=prepared_file.relative_path,
                        )
                    except UnicodeDecodeError:
                        target_content = None
                        target_read_error = "target_file_not_utf8"
                        blocked_reasons.append(target_read_error)
                    except (OSError, subprocess.SubprocessError):
                        target_content = None
                        target_read_error = "base_snapshot_read_failed"
                        blocked_reasons.append(target_read_error)
                    if target_content is None:
                        blocked_files.append(
                            CandidateSandboxDiffBlockedFile(
                                relative_path=prepared_file.relative_path,
                                operation=prepared_file.operation,
                                blocked_reasons=[
                                    target_read_error or "base_snapshot_read_failed"
                                ],
                            )
                        )
                        continue
                    target_file_content_read = True
                    target_existed = True
                    target_content_sha256 = self._sha256_utf8(target_content)
                else:
                    target_lookup_error = None
                    try:
                        target_object_type = self._git_object_type(
                            repo_root=repo_root,
                            base_commit_sha=exact_base_commit_sha,
                            relative_path=prepared_file.relative_path,
                        )
                    except (OSError, subprocess.SubprocessError):
                        target_object_type = None
                        target_lookup_error = "base_snapshot_read_failed"
                        blocked_reasons.append(target_lookup_error)
                    if target_lookup_error is not None:
                        blocked_files.append(
                            CandidateSandboxDiffBlockedFile(
                                relative_path=prepared_file.relative_path,
                                operation=prepared_file.operation,
                                blocked_reasons=[target_lookup_error],
                            )
                        )
                        continue
                    if target_object_type is not None:
                        blocked_files.append(
                            CandidateSandboxDiffBlockedFile(
                                relative_path=prepared_file.relative_path,
                                operation=prepared_file.operation,
                                blocked_reasons=["target_file_already_exists_for_create"],
                            )
                        )
                        blocked_reasons.append("target_file_already_exists_for_create")
                        continue
                    target_content = ""
                    target_existed = False
                    target_content_sha256 = None

                base_snapshot_entries.append(
                    _BaseSnapshotFingerprintEntry(
                        relative_path=prepared_file.relative_path,
                        operation=prepared_file.operation,
                        base_file_existed=target_existed,
                        base_content_sha256=target_content_sha256,
                        candidate_content_sha256=candidate_content_sha256,
                    )
                )

                unified_diff = self._unified_diff(
                    relative_path=prepared_file.relative_path,
                    old_content=target_content,
                    new_content=candidate_content,
                )
                diff_size = len(unified_diff.encode("utf-8"))
                diff_entries.append(
                    CandidateSandboxDiffEntry(
                        relative_path=prepared_file.relative_path,
                        operation=prepared_file.operation,
                        target_file_path=prepared_file.target_file_path.as_posix(),
                        candidate_file_path=prepared_file.candidate_file_path.as_posix(),
                        target_file_existed=target_existed,
                        candidate_file_existed=True,
                        target_file_content_read=prepared_file.operation == "update",
                        candidate_file_content_read=True,
                        unified_diff=unified_diff,
                        diff_bytes=diff_size,
                    )
                )

            blocked_reasons = self._dedupe(blocked_reasons)
            if not blocked_reasons:
                unified_diff_text = "".join(entry.unified_diff for entry in diff_entries)
                total_diff_bytes = len(unified_diff_text.encode("utf-8"))
                if total_diff_bytes > max_diff_bytes:
                    blocked_reasons.append("diff_too_large")
                    diff_entries = []
                    unified_diff_text = ""
                    base_snapshot_entries = []
            if not blocked_reasons:
                current_head = self._read_repository_head(
                    repo_root,
                    blocked_reasons=blocked_reasons,
                )
                if (
                    current_head is not None
                    and exact_base_commit_sha is not None
                    and current_head != exact_base_commit_sha
                ):
                    blocked_reasons.append("base_commit_changed_during_diff_generation")

        blocked_reasons = self._dedupe(blocked_reasons)
        diff_generation_status = "generated" if not blocked_reasons else "blocked"
        generated = diff_generation_status == "generated"
        base_evidence_schema_version = (
            P21_C_SANDBOX_CANDIDATE_DIFF_BASE_EVIDENCE_SCHEMA_VERSION
            if generated
            else None
        )
        base_snapshot_fingerprint = (
            self._base_snapshot_fingerprint(
                session_id=session_id,
                source_task_id=source_task_id,
                source_candidate_write_message_id=source_message_id,
                source_workspace_creation_message_id=source_workspace_creation_message_id,
                source_workspace_manifest_write_message_id=(
                    source_workspace_manifest_write_message_id
                ),
                source_operation_manifest_message_id=(
                    source_operation_manifest_message_id
                ),
                canonical_repo_root=repo_root_text,
                exact_base_commit_sha=exact_base_commit_sha,
                ordered_scope_paths=ordered_scope_paths,
                base_snapshot_entries=base_snapshot_entries,
                diff_mode=diff_mode,
            )
            if generated
            else None
        )
        diff_bytes = (
            len(unified_diff_text.encode("utf-8"))
            if diff_generation_status == "generated"
            else 0
        )
        diff_file_count = len(diff_entries) if diff_generation_status == "generated" else 0
        candidate_files_diffed_count = (
            len(diff_entries) if diff_generation_status == "generated" else 0
        )
        candidate_files_blocked_count = (
            len(blocked_files)
            if blocked_files
            else (
                len(raw_candidate_files)
                if diff_generation_status == "blocked"
                else 0
            )
        )
        cleanup_required = bool(
            workspace_creation_action is not None
            and workspace_creation_action.get("cleanup_required") is True
        )

        return ProjectDirectorSandboxCandidateDiffResult(
            diff_generation_status=diff_generation_status,
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            diff_mode=diff_mode,
            source_candidate_write_status=source_candidate_write_status,
            source_candidate_write_message_bound=source_candidate_write_message_bound,
            source_candidate_write_verified=source_candidate_write_verified,
            source_workspace_manifest_write_message_id=(
                source_workspace_manifest_write_message_id
            ),
            source_workspace_creation_message_id=source_workspace_creation_message_id,
            source_operation_manifest_message_id=(
                source_operation_manifest_message_id
            ),
            workspace_path=workspace_path_text_resolved,
            workspace_path_within_root=workspace_path_within_root,
            workspace_root=workspace_root_text,
            internal_manifest_file_path=internal_manifest_file_text,
            internal_manifest_verified=internal_manifest_verified,
            repo_root=repo_root_text,
            base_evidence_schema_version=base_evidence_schema_version,
            base_commit_sha=exact_base_commit_sha if generated else None,
            base_snapshot_fingerprint=base_snapshot_fingerprint,
            base_content_source=(
                P21_C_SANDBOX_CANDIDATE_DIFF_BASE_CONTENT_SOURCE_EXACT_GIT_COMMIT_OBJECT
                if generated
                else None
            ),
            readonly_base_snapshot_verified=generated,
            target_file_content_read=target_file_content_read,
            candidate_file_content_read=candidate_file_content_read and generated,
            readonly_real_diff_generated=generated,
            real_diff_generated=generated,
            diff_bytes=diff_bytes,
            diff_file_count=diff_file_count,
            diff_entries=diff_entries if generated else [],
            unified_diff_text=unified_diff_text if generated else "",
            candidate_files_considered_count=len(raw_candidate_files),
            candidate_files_diffed_count=candidate_files_diffed_count,
            candidate_files_blocked_count=candidate_files_blocked_count,
            candidate_diff_blocked_files=blocked_files,
            cleanup_required=cleanup_required,
            cleanup_hint=self._cleanup_hint(cleanup_required=cleanup_required),
            required_preconditions=list(REQUIRED_PRECONDITIONS),
            allowed_future_diff_scope=list(ALLOWED_FUTURE_DIFF_SCOPE),
            forbidden_diff_actions=list(FORBIDDEN_DIFF_ACTIONS),
            blocked_reasons=blocked_reasons,
            risks=[
                "readonly real diff is generated in memory and must be reviewed separately",
                "target file content was read only for diff generation",
                "product runtime Git writes remain forbidden",
            ],
            unknowns=[
                "readonly reviewer handoff remains future work",
                "patch application remains future work",
                "cleanup remains future work",
            ],
            diff_generation_summary=self._diff_generation_summary(
                diff_generation_status=diff_generation_status
            ),
            recommended_next_step=(
                "Send the readonly real diff to a readonly reviewer before any patch, "
                "cleanup, executor, Worker, Task, Run, or product runtime Git step."
            ),
        )

    def _candidate_write_action(
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
            != P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL
        ):
            blocked_reasons.append(
                "source_message_is_not_p21_c_candidate_files_written"
            )
        action = self._first_action(
            source_message,
            expected_type=P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("p21_c_candidate_files_write_record_missing")
            return None
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_task_not_bound_to_candidate_files_write")
        return action

    def _workspace_manifest_action(
        self,
        *,
        workspace_manifest_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if workspace_manifest_message is None:
            blocked_reasons.append("source_workspace_manifest_write_message_missing")
            return None
        if (
            workspace_manifest_message.session_id != session_id
            or workspace_manifest_message.source_detail
            != P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_workspace_manifest_write_message_missing")
        action = self._first_action(
            workspace_manifest_message,
            expected_type=P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("source_workspace_manifest_write_message_missing")
            return None
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_workspace_manifest_write_message_missing")
        if action.get("manifest_file_written") is not True:
            blocked_reasons.append("source_workspace_manifest_write_message_missing")
        if not self._manifest_write_action_is_no_write_except_manifest(action):
            blocked_reasons.append("source_workspace_manifest_write_message_missing")
        if action.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("source_workspace_manifest_write_message_missing")
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
        if not isinstance(action.get("manifest_operations"), list) or not action.get(
            "manifest_operations"
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

    def _candidate_file_path(
        self,
        raw_candidate: Any,
        *,
        workspace_path: Path | None,
        relative_path: str,
        file_reasons: list[str],
    ) -> Path | None:
        if not isinstance(raw_candidate, dict):
            file_reasons.append("candidate_written_files_missing")
            return None
        raw_path = raw_candidate.get("workspace_file_path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            file_reasons.append("candidate_file_missing_on_disk")
            return None
        try:
            candidate_file_path = Path(raw_path).resolve(strict=False)
        except OSError:
            file_reasons.append("candidate_file_not_within_workspace")
            return None
        if workspace_path is None or not self._is_relative_to(
            candidate_file_path,
            workspace_path,
        ):
            file_reasons.append("candidate_file_not_within_workspace")
        internal_dir_path = (
            (workspace_path / INTERNAL_MANIFEST_DIR_NAME).resolve(strict=False)
            if workspace_path is not None
            else None
        )
        if (
            internal_dir_path is not None
            and (
                candidate_file_path == internal_dir_path
                or internal_dir_path in candidate_file_path.parents
            )
        ):
            file_reasons.append("candidate_file_targets_internal_dir")
        if workspace_path is not None and self._candidate_path_is_allowed(relative_path):
            expected_path = (workspace_path / relative_path).resolve(strict=False)
            if candidate_file_path != expected_path:
                file_reasons.append("candidate_file_not_within_workspace")
        return candidate_file_path

    def _target_file_path(
        self,
        relative_path: str,
        *,
        repo_root: Path | None,
        file_reasons: list[str],
    ) -> Path | None:
        if not self._candidate_path_is_allowed(relative_path):
            file_reasons.append("target_file_path_escapes_repo_root")
            return None
        if repo_root is None:
            return None
        try:
            target_file_path = (repo_root / relative_path).resolve(strict=False)
        except OSError:
            file_reasons.append("target_file_path_escapes_repo_root")
            return None
        if not self._is_strict_child_of(target_file_path, repo_root):
            file_reasons.append("target_file_path_escapes_repo_root")
        return target_file_path

    @staticmethod
    def _candidate_relative_path(raw_candidate: Any) -> str:
        if not isinstance(raw_candidate, dict):
            return ""
        value = raw_candidate.get("relative_path")
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _candidate_operation(raw_candidate: Any) -> str:
        if not isinstance(raw_candidate, dict):
            return ""
        value = raw_candidate.get("operation")
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _candidate_file_preflight(
        candidate_file_path: Path,
        *,
        workspace_path: Path | None,
        file_reasons: list[str],
    ) -> None:
        if workspace_path is None:
            file_reasons.append("candidate_file_not_within_workspace")
            return
        try:
            if not candidate_file_path.exists():
                file_reasons.append("candidate_file_missing_on_disk")
            elif not candidate_file_path.is_file():
                file_reasons.append("candidate_file_is_not_file")
        except OSError:
            file_reasons.append("candidate_file_missing_on_disk")

    @staticmethod
    def _read_text_file(
        path: Path,
        *,
        blocked_reason: str,
        blocked_reasons: list[str],
    ) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            blocked_reasons.append(blocked_reason)
            return None
        except OSError:
            blocked_reasons.append(blocked_reason)
            return None

    @staticmethod
    def _read_repository_head(
        repo_root: Path,
        *,
        blocked_reasons: list[str],
    ) -> str | None:
        try:
            completed = subprocess.run(
                ("git", "rev-parse", "--verify", "HEAD"),
                cwd=repo_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            blocked_reasons.append("base_commit_unavailable")
            return None
        value = completed.stdout.strip()
        if completed.returncode != 0 or not ProjectDirectorSandboxCandidateDiffService._is_lower_hex(
            value,
            length=40,
        ):
            blocked_reasons.append("base_commit_unavailable")
            return None
        return value

    @staticmethod
    def _git_object_type(
        *,
        repo_root: Path,
        base_commit_sha: str,
        relative_path: str,
    ) -> str | None:
        completed = subprocess.run(
            ("git", "cat-file", "-t", f"{base_commit_sha}:{relative_path}"),
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if completed.returncode != 0:
            return None
        value = completed.stdout.strip()
        return value or None

    @staticmethod
    def _read_git_blob_text(
        *,
        repo_root: Path,
        base_commit_sha: str,
        relative_path: str,
    ) -> str:
        completed = subprocess.run(
            ("git", "cat-file", "blob", f"{base_commit_sha}:{relative_path}"),
            cwd=repo_root,
            check=False,
            capture_output=True,
            timeout=5,
        )
        if completed.returncode != 0:
            raise OSError("git cat-file blob failed")
        return completed.stdout.decode("utf-8")

    @staticmethod
    def _sha256_utf8(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @classmethod
    def _base_snapshot_fingerprint(
        cls,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_candidate_write_message_id: UUID,
        source_workspace_creation_message_id: UUID | None,
        source_workspace_manifest_write_message_id: UUID | None,
        source_operation_manifest_message_id: UUID | None,
        canonical_repo_root: str | None,
        exact_base_commit_sha: str | None,
        ordered_scope_paths: tuple[str, ...],
        base_snapshot_entries: list[_BaseSnapshotFingerprintEntry],
        diff_mode: SandboxCandidateDiffMode,
    ) -> str:
        payload = {
            "schema_version": (
                P21_C_SANDBOX_CANDIDATE_DIFF_BASE_EVIDENCE_SCHEMA_VERSION
            ),
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "source_candidate_write_message_id": str(
                source_candidate_write_message_id
            ),
            "source_workspace_creation_message_id": (
                str(source_workspace_creation_message_id)
                if source_workspace_creation_message_id is not None
                else None
            ),
            "source_workspace_manifest_write_message_id": (
                str(source_workspace_manifest_write_message_id)
                if source_workspace_manifest_write_message_id is not None
                else None
            ),
            "source_operation_manifest_message_id": (
                str(source_operation_manifest_message_id)
                if source_operation_manifest_message_id is not None
                else None
            ),
            "canonical_repo_root": canonical_repo_root,
            "exact_base_commit_sha": exact_base_commit_sha,
            "ordered_scope_paths": list(ordered_scope_paths),
            "diff_identity": {
                "diff_mode": diff_mode,
                "entries": [
                    {
                        "relative_path": entry.relative_path,
                        "operation": entry.operation,
                        "candidate_content_sha256": entry.candidate_content_sha256,
                    }
                    for entry in sorted(
                        base_snapshot_entries,
                        key=lambda item: (item.relative_path, item.operation),
                    )
                ],
            },
            "base_snapshot_entries": [
                {
                    "relative_path": entry.relative_path,
                    "operation": entry.operation,
                    "base_file_existed": entry.base_file_existed,
                    "base_content_sha256": entry.base_content_sha256,
                }
                for entry in sorted(
                    base_snapshot_entries,
                    key=lambda item: (item.relative_path, item.operation),
                )
            ],
        }
        return hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _is_lower_hex(value: str, *, length: int) -> bool:
        return (
            isinstance(value, str)
            and len(value) == length
            and all(char in "0123456789abcdef" for char in value)
        )

    @staticmethod
    def _unified_diff(
        *,
        relative_path: str,
        old_content: str,
        new_content: str,
    ) -> str:
        diff_lines = difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
            lineterm="",
        )
        diff_text = "\n".join(diff_lines)
        return f"{diff_text}\n" if diff_text else ""

    @staticmethod
    def _candidate_path_is_allowed(path: str) -> bool:
        if not path:
            return False
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

    def _resolved_repo_root(self, blocked_reasons: list[str]) -> Path | None:
        repo_root = self._repo_root or Path(__file__).resolve().parents[4]
        try:
            resolved_repo_root = repo_root.resolve(strict=False)
        except OSError:
            blocked_reasons.append("repo_root_unavailable")
            return None
        if not resolved_repo_root.exists() or not resolved_repo_root.is_dir():
            blocked_reasons.append("repo_root_unavailable")
            return None
        return resolved_repo_root

    @staticmethod
    def _candidate_write_action_is_no_diff_or_patch(action: dict[str, Any]) -> bool:
        return all(action.get(flag) is False for flag in SOURCE_CANDIDATE_WRITE_FALSE_FLAGS)

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
                "no cleanup was performed in readonly diff generation."
            )
        return (
            "cleanup_required=false because the source workspace did not require "
            "cleanup; no cleanup was performed in readonly diff generation."
        )

    @staticmethod
    def _diff_generation_summary(*, diff_generation_status: str) -> str:
        if diff_generation_status == "generated":
            return (
                "P21-C-F generated a readonly unified diff in memory from sandbox "
                "candidate files and target project files. It did not write files, "
                "apply patches, create worktrees, dispatch Workers, create Tasks/Runs, "
                "clean up directories, or perform Git writes."
            )
        return (
            "P21-C-F readonly diff generation was blocked before message creation, "
            "file write, patch application, worktree, executor, Worker, Task, Run, "
            "cleanup, or Git side effect."
        )

    @staticmethod
    def _candidate_diff_action(
        result: ProjectDirectorSandboxCandidateDiffResult,
    ) -> dict[str, Any]:
        return {
            "type": P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
            "diff_generation_status": result.diff_generation_status,
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
            "repo_root": result.repo_root,
            "base_evidence_schema_version": result.base_evidence_schema_version,
            "base_commit_sha": result.base_commit_sha,
            "base_snapshot_fingerprint": result.base_snapshot_fingerprint,
            "base_content_source": result.base_content_source,
            "readonly_base_snapshot_verified": (
                result.readonly_base_snapshot_verified
            ),
            "target_file_content_read": result.target_file_content_read,
            "candidate_file_content_read": result.candidate_file_content_read,
            "readonly_real_diff_generated": result.readonly_real_diff_generated,
            "real_diff_generated": result.real_diff_generated,
            "diff_file_count": result.diff_file_count,
            "diff_bytes": result.diff_bytes,
            "diff_entries": [
                item.model_dump(mode="json") for item in result.diff_entries
            ],
            "unified_diff_text": result.unified_diff_text,
            "main_project_file_written": False,
            "sandbox_file_written": False,
            "manifest_file_written": False,
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
    "ConfirmedSandboxCandidateDiff",
    "P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE",
    "P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL",
    "ProjectDirectorSandboxCandidateDiffService",
)
