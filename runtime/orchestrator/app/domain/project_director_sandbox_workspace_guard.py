"""Workspace root guard result for Project Director P21-C sandbox writes."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel


SandboxWorkspaceGuardMode = Literal["dry_run", "fake_guard"]
SandboxWorkspaceGuardStatus = Literal["guarded", "blocked"]


class ProjectDirectorSandboxWorkspaceGuardResult(DomainModel):
    """P21-C workspace guard that previews an isolated workspace path only."""

    guard_status: SandboxWorkspaceGuardStatus
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    guard_mode: SandboxWorkspaceGuardMode = "dry_run"
    source_design_lock_status: str | None = Field(default=None, max_length=120)
    source_design_lock_message_bound: bool = False
    source_design_lock_verified: bool = False
    sandbox_workspace_guarded: bool = False
    sandbox_workspace_root: str | None = None
    sandbox_workspace_root_policy: str = Field(min_length=1, max_length=1_000)
    requested_workspace_name: str | None = Field(default=None, max_length=200)
    normalized_workspace_name: str | None = Field(default=None, max_length=120)
    workspace_path_preview: str | None = Field(default=None, max_length=2_000)
    workspace_path_within_root: bool = False
    workspace_created: bool = False
    workspace_written: bool = False
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
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_workspace_scope: list[str] = Field(default_factory=list)
    forbidden_workspace_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    guard_summary: str = Field(min_length=1, max_length=2_000)
    recommended_next_step: str = Field(min_length=1, max_length=1_000)
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
        "workspace_created",
        "workspace_written",
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
    def reject_runtime_side_effect_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError(
                "P21-C workspace guard runtime side-effect flags must remain false"
            )
        return value


__all__ = (
    "ProjectDirectorSandboxWorkspaceGuardResult",
    "SandboxWorkspaceGuardMode",
    "SandboxWorkspaceGuardStatus",
)
