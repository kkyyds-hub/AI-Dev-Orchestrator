"""Sandbox candidate business file write result for Project Director P21-C."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel


SandboxCandidateFileWriteMode = Literal["candidate_files_only"]
SandboxCandidateFileWriteStatus = Literal["written", "blocked"]
SandboxCandidateFileOperation = Literal["create", "update"]
SandboxCandidateFileContentEncoding = Literal["utf-8"]


class CandidateSandboxFileWrite(DomainModel):
    """One requested sandbox candidate file write."""

    relative_path: str = Field(min_length=1, max_length=2_000)
    content: str
    operation: SandboxCandidateFileOperation
    content_encoding: SandboxCandidateFileContentEncoding = "utf-8"


class CandidateSandboxWrittenFile(DomainModel):
    """One candidate file written inside the sandbox workspace."""

    relative_path: str = Field(min_length=1, max_length=2_000)
    workspace_file_path: str = Field(min_length=1, max_length=2_000)
    operation: SandboxCandidateFileOperation
    content_encoding: SandboxCandidateFileContentEncoding = "utf-8"
    content_size_bytes: int = Field(ge=0)


class CandidateSandboxBlockedFile(DomainModel):
    """One requested candidate file rejected before write."""

    relative_path: str = Field(default="", max_length=2_000)
    operation: str = Field(default="", max_length=40)
    blocked_reasons: list[str] = Field(default_factory=list)


class ProjectDirectorSandboxCandidateFileWriteResult(DomainModel):
    """P21-C result for writing candidate business files inside a sandbox."""

    candidate_write_status: SandboxCandidateFileWriteStatus
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    write_mode: SandboxCandidateFileWriteMode = "candidate_files_only"
    source_manifest_write_status: str | None = Field(default=None, max_length=120)
    source_manifest_write_message_bound: bool = False
    source_manifest_write_verified: bool = False
    source_workspace_creation_message_id: UUID | None = None
    source_operation_manifest_message_id: UUID | None = None
    workspace_path: str | None = Field(default=None, max_length=2_000)
    workspace_path_within_root: bool = False
    workspace_root: str | None = Field(default=None, max_length=2_000)
    internal_manifest_file_path: str | None = Field(default=None, max_length=2_000)
    internal_manifest_verified: bool = False
    candidate_files_requested_count: int = Field(default=0, ge=0)
    candidate_files_written_count: int = Field(default=0, ge=0)
    candidate_files_blocked_count: int = Field(default=0, ge=0)
    candidate_written_files: list[CandidateSandboxWrittenFile] = Field(
        default_factory=list
    )
    candidate_blocked_files: list[CandidateSandboxBlockedFile] = Field(
        default_factory=list
    )
    candidate_business_files_written: bool = False
    business_file_written: bool = False
    manifest_file_written: bool = False
    target_file_content_read: bool = False
    real_diff_generated: bool = False
    patch_applied: bool = False
    controlled_sandbox_write_enabled: bool = False
    sandbox_write_allowed: bool = False
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    worktree_created: bool = False
    worktree_cleaned_up: bool = False
    rollback_snapshot_created: bool = False
    cleanup_required: bool = False
    cleanup_hint: str = Field(default="", max_length=1_000)
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_candidate_write_scope: list[str] = Field(default_factory=list)
    forbidden_candidate_write_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    candidate_write_summary: str = Field(min_length=1, max_length=2_000)
    recommended_next_step: str = Field(min_length=1, max_length=1_000)
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
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
        mode="after",
    )
    @classmethod
    def reject_forbidden_side_effect_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError(
                "P21-C candidate file write may only write requested sandbox files"
            )
        return value


__all__ = (
    "CandidateSandboxBlockedFile",
    "CandidateSandboxFileWrite",
    "CandidateSandboxWrittenFile",
    "ProjectDirectorSandboxCandidateFileWriteResult",
    "SandboxCandidateFileContentEncoding",
    "SandboxCandidateFileOperation",
    "SandboxCandidateFileWriteMode",
    "SandboxCandidateFileWriteStatus",
)
