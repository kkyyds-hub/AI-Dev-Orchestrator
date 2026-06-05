"""Blocked workspace cleanup domain models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel, utc_now
from app.domain.worktree_plan import WorktreePlan


class WorktreeCleanupCommandPreview(DomainModel):
    """Disabled preview of one future cleanup command.

    P1-E-A exposes intended commands for review only.  These previews must not
    be passed to a runner and are always returned with execution_enabled=False.
    """

    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int = 120
    mutates_repository: bool = True
    command_kind: str
    execution_enabled: bool = False

    @field_validator("cwd", "command_kind")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required preview text."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("cleanup command preview text must not be blank")
        return normalized_value


class WorktreeCleanupPreflight(DomainModel):
    """Read-only cleanup preflight for the current AgentSession worktree."""

    preflight_status: str = "not_run"
    read_only: bool = True
    commands_run: list[str] = Field(default_factory=list)
    worktree_path_exists: bool | None = None
    worktree_path_is_directory: bool | None = None
    worktree_path_safe: bool | None = None
    worktree_registered: bool | None = None
    worktree_clean: bool | None = None
    repository_is_git_worktree: bool | None = None
    registered_worktree_paths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("preflight_status")
    @classmethod
    def normalize_preflight_status(cls, value: str) -> str:
        """Trim preflight status."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("cleanup preflight status must not be blank")
        return normalized_value

    @field_validator("commands_run", "registered_worktree_paths", "errors", "warnings")
    @classmethod
    def normalize_preflight_lists(cls, value: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate preflight lists."""

        return _normalize_string_list(value)


class WorktreeCleanupResult(DomainModel):
    """Blocked cleanup result for future workspace removal.

    P1-E-A is intentionally non-mutating: no git command is executed, no
    worktree or branch is deleted, no directory is removed, and AgentSession
    workspace fields are not changed.
    """

    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    plan_hash: str = Field(min_length=64, max_length=64)
    submitted_plan_hash: str = Field(min_length=64, max_length=64)
    cleanup_status: str = "blocked"
    blocked_reason: str = "workspace_cleanup_blocked"
    dry_run: bool = True
    requires_user_confirmation: bool = True
    worktree_path: str | None = Field(default=None, max_length=1_000)
    branch_name: str | None = Field(default=None, max_length=200)
    base_branch: str | None = Field(default=None, max_length=200)
    base_commit_sha: str | None = Field(default=None, max_length=80)
    checked_at: datetime = Field(default_factory=utc_now)
    cleanup_preflight: WorktreeCleanupPreflight | None = None
    cleanup_command_preview: list[WorktreeCleanupCommandPreview] = Field(
        default_factory=list
    )
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_action: str = "keep_workspace_until_cleanup_execution_gate_passes"
    removes_worktree: bool = False
    deletes_branch: bool = False
    deletes_directory: bool = False
    runs_git: bool = False
    runs_write_git: bool = False
    mutates_agent_session_workspace: bool = False

    @classmethod
    def blocked_from_plan(
        cls,
        *,
        plan: WorktreePlan,
        submitted_plan_hash: str,
        worktree_path: str | None,
        branch_name: str | None,
        blockers: list[str],
        warnings: list[str] | None = None,
        cleanup_preflight: WorktreeCleanupPreflight | None = None,
        cleanup_command_preview: list[WorktreeCleanupCommandPreview] | None = None,
    ) -> "WorktreeCleanupResult":
        """Build the default blocked cleanup skeleton from the current plan."""

        return cls(
            agent_session_id=plan.agent_session_id,
            project_id=plan.project_id,
            repository_workspace_id=plan.repository_workspace_id,
            plan_hash=plan.plan_hash,
            submitted_plan_hash=submitted_plan_hash,
            worktree_path=worktree_path,
            branch_name=branch_name,
            base_branch=plan.base_branch,
            base_commit_sha=plan.base_commit_sha,
            cleanup_preflight=cleanup_preflight,
            cleanup_command_preview=cleanup_command_preview or [],
            blockers=blockers,
            warnings=warnings or [],
            runs_git=(
                cleanup_preflight is not None
                and len(cleanup_preflight.commands_run) > 0
            ),
        )

    @field_validator("cleanup_status", "blocked_reason", "next_action")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required status labels."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("cleanup label must not be blank")
        return normalized_value

    @field_validator("blockers", "warnings")
    @classmethod
    def normalize_reason_lists(cls, value: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate reason lists."""

        return _normalize_string_list(value)


def _normalize_string_list(value: list[str]) -> list[str]:
    """Trim, drop blanks and deduplicate one string list."""

    normalized_items: list[str] = []
    seen_items: set[str] = set()
    for item in value:
        normalized_item = item.strip()
        if not normalized_item or normalized_item in seen_items:
            continue
        normalized_items.append(normalized_item)
        seen_items.add(normalized_item)
    return normalized_items
