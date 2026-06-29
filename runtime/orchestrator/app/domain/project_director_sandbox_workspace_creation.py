"""Controlled sandbox workspace creation result for Project Director P21-C."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel


SandboxWorkspaceCreateMode = Literal["mkdir_only"]
SandboxWorkspaceCreationStatus = Literal["created", "already_exists", "blocked"]


class ProjectDirectorSandboxWorkspaceCreationResult(DomainModel):
    """P21-C result for creating only the isolated sandbox workspace directory."""

    creation_status: SandboxWorkspaceCreationStatus
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    create_mode: SandboxWorkspaceCreateMode = "mkdir_only"
    source_manifest_status: str | None = Field(default=None, max_length=120)
    source_manifest_message_bound: bool = False
    source_manifest_verified: bool = False
    workspace_path: str | None = Field(default=None, max_length=2_000)
    workspace_path_within_root: bool = False
    workspace_root: str | None = Field(default=None, max_length=2_000)
    workspace_created: bool = False
    workspace_already_existed: bool = False
    workspace_written: bool = False
    file_written: bool = False
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
    allowed_future_creation_scope: list[str] = Field(default_factory=list)
    forbidden_creation_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    creation_summary: str = Field(min_length=1, max_length=2_000)
    recommended_next_step: str = Field(min_length=1, max_length=1_000)
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
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
        mode="after",
    )
    @classmethod
    def reject_forbidden_side_effect_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError(
                "P21-C workspace creation may only create the workspace directory"
            )
        return value


__all__ = (
    "ProjectDirectorSandboxWorkspaceCreationResult",
    "SandboxWorkspaceCreateMode",
    "SandboxWorkspaceCreationStatus",
)
