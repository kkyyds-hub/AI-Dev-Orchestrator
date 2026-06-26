"""Dry-run/fake-write sandbox execution result domain for Project Director P21-A."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel


SandboxWriteExecutionMode = Literal[
    "dry_run", "fake_write", "controlled_sandbox_write"
]
SandboxWriteExecutionStatus = Literal["planned", "simulated", "blocked"]
SandboxWriteOperationExecutionStatus = Literal["planned", "simulated", "blocked"]


class ProjectDirectorSandboxWriteOperationResult(DomainModel):
    """One no-write operation result derived from a passed P20 preflight path."""

    operation_id: str = Field(min_length=1, max_length=120)
    path: str = Field(min_length=1, max_length=1_000)
    operation: str = Field(min_length=1, max_length=120)
    execution_status: SandboxWriteOperationExecutionStatus
    source_preflight_path_policy_allowed: bool = False
    before_hash: str | None = Field(default=None, max_length=200)
    after_hash: str | None = Field(default=None, max_length=200)
    content_preview_hash: str | None = Field(default=None, max_length=200)
    rollback_snapshot_available: bool = False
    cleanup_required: bool = False
    file_written: bool = False
    patch_applied: bool = False
    worktree_written: bool = False
    git_write_performed: bool = False
    notes: list[str] = Field(default_factory=list)

    @field_validator(
        "rollback_snapshot_available",
        "cleanup_required",
        "file_written",
        "patch_applied",
        "worktree_written",
        "git_write_performed",
        mode="after",
    )
    @classmethod
    def reject_write_and_cleanup_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError("P21-A operation write and cleanup flags must remain false")
        return value


class ProjectDirectorSandboxWriteExecutionResult(DomainModel):
    """P21-A execution result that never writes files, worktrees, or Git state."""

    execution_status: SandboxWriteExecutionStatus
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    execution_mode: SandboxWriteExecutionMode = "dry_run"
    source_preflight_status: str | None = Field(default=None, max_length=120)
    source_preflight_message_bound: bool = False
    policy_only_source_verified: bool = False
    sandbox_write_execution: bool = True
    no_write_execution: bool = True
    dry_run_only: bool = True
    fake_write_only: bool = False
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
    execution_message_bound: bool = False
    checked_operations_count: int = Field(default=0, ge=0)
    simulated_operations_count: int = Field(default=0, ge=0)
    blocked_operations_count: int = Field(default=0, ge=0)
    operation_results: list[ProjectDirectorSandboxWriteOperationResult] = Field(
        default_factory=list
    )
    accepted_operation_paths: list[str] = Field(default_factory=list)
    blocked_operation_paths: list[str] = Field(default_factory=list)
    execution_summary: str = Field(min_length=1, max_length=2_000)
    recommended_next_step: str = Field(min_length=1, max_length=1_000)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
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
        mode="after",
    )
    @classmethod
    def reject_write_start_creation_and_cleanup_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError("P21-A execution safety flags must remain false")
        return value


__all__ = (
    "ProjectDirectorSandboxWriteExecutionResult",
    "ProjectDirectorSandboxWriteOperationResult",
    "SandboxWriteExecutionMode",
    "SandboxWriteExecutionStatus",
    "SandboxWriteOperationExecutionStatus",
)
