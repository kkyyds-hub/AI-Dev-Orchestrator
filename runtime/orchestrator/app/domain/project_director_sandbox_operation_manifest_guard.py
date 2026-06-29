"""Operation manifest guard result for Project Director P21-C sandbox writes."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel


SandboxOperationManifestGuardMode = Literal["dry_run", "fake_manifest"]
SandboxOperationManifestGuardStatus = Literal["manifested", "blocked"]


class SandboxOperationManifestEntry(DomainModel):
    """One future operation previewed under the guarded workspace path."""

    operation_id: str = Field(min_length=1, max_length=120)
    path: str = Field(default="", max_length=1_000)
    operation: str = Field(default="", max_length=120)
    workspace_target_path_preview: str = Field(default="", max_length=2_000)
    source_execution_status: str | None = Field(default=None, max_length=120)
    source_preflight_path_policy_allowed: bool | None = None
    path_within_workspace: bool = False
    operation_manifest_allowed: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)


class ProjectDirectorSandboxOperationManifestGuardResult(DomainModel):
    """P21-C manifest guard that previews operations without side effects."""

    manifest_status: SandboxOperationManifestGuardStatus
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    manifest_mode: SandboxOperationManifestGuardMode = "dry_run"
    source_workspace_guard_status: str | None = Field(default=None, max_length=120)
    source_workspace_guard_message_bound: bool = False
    source_workspace_guard_verified: bool = False
    source_design_lock_message_id: UUID | None = None
    source_execution_message_id: UUID | None = None
    workspace_path_preview: str | None = Field(default=None, max_length=2_000)
    workspace_path_within_root: bool = False
    operation_manifest_created: bool = False
    manifest_operations_count: int = Field(default=0, ge=0)
    manifest_allowed_operations_count: int = Field(default=0, ge=0)
    manifest_blocked_operations_count: int = Field(default=0, ge=0)
    manifest_operations: list[SandboxOperationManifestEntry] = Field(
        default_factory=list
    )
    allowed_operation_paths: list[str] = Field(default_factory=list)
    blocked_operation_paths: list[str] = Field(default_factory=list)
    workspace_created: bool = False
    workspace_written: bool = False
    file_written: bool = False
    controlled_sandbox_write_enabled: bool = False
    sandbox_write_allowed: bool = False
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    real_code_modified: bool = False
    real_diff_generated: bool = False
    patch_applied: bool = False
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
    target_file_content_read: bool = False
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_manifest_scope: list[str] = Field(default_factory=list)
    forbidden_manifest_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    manifest_summary: str = Field(min_length=1, max_length=2_000)
    recommended_next_step: str = Field(min_length=1, max_length=1_000)
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
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
        mode="after",
    )
    @classmethod
    def reject_runtime_side_effect_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError(
                "P21-C operation manifest guard side-effect flags must remain false"
            )
        return value


__all__ = (
    "ProjectDirectorSandboxOperationManifestGuardResult",
    "SandboxOperationManifestEntry",
    "SandboxOperationManifestGuardMode",
    "SandboxOperationManifestGuardStatus",
)
