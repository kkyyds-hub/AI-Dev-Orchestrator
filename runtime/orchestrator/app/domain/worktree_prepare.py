"""Workspace prepare skeleton domain models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel, utc_now
from app.domain.worktree_plan import WorktreePlan


class WorktreeGitPreflight(DomainModel):
    """Read-only git preflight details for future workspace creation."""

    preflight_status: str = "not_run"
    read_only: bool = True
    commands_run: list[str] = Field(default_factory=list)
    repository_is_git_worktree: bool | None = None
    repository_head_sha: str | None = Field(default=None, max_length=80)
    repository_clean: bool | None = None
    planned_branch_exists: bool | None = None
    planned_worktree_registered: bool | None = None
    registered_worktree_paths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("preflight_status")
    @classmethod
    def normalize_preflight_status(cls, value: str) -> str:
        """Trim preflight status."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("preflight_status must not be blank")
        return normalized_value

    @field_validator("commands_run", "registered_worktree_paths", "errors", "warnings")
    @classmethod
    def normalize_preflight_lists(cls, value: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate preflight lists."""

        return _normalize_string_list(value)


class WorktreePrepareResult(DomainModel):
    """Blocked result for the future real workspace prepare step.

    P1-D-D adds read-only git preflight before implementation.  It never creates
    a worktree, creates a branch, runs write git, or mutates AgentSession
    workspace fields.
    """

    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    plan_hash: str = Field(min_length=64, max_length=64)
    submitted_plan_hash: str = Field(min_length=64, max_length=64)
    prepare_status: str = "blocked"
    blocked_reason: str = "workspace_prepare_not_implemented"
    dry_run: bool = True
    requires_user_confirmation: bool = True
    worktree_path: str | None = Field(default=None, max_length=1_000)
    branch_name: str | None = Field(default=None, max_length=200)
    base_branch: str | None = Field(default=None, max_length=200)
    base_commit_sha: str | None = Field(default=None, max_length=80)
    checked_at: datetime = Field(default_factory=utc_now)
    git_preflight: WorktreeGitPreflight | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_action: str = "implement_workspace_prepare_execution_after_gate"
    creates_worktree: bool = False
    creates_branch: bool = False
    runs_git: bool = False
    runs_write_git: bool = False
    mutates_agent_session_workspace: bool = False

    @classmethod
    def blocked_from_plan(
        cls,
        *,
        plan: WorktreePlan,
        submitted_plan_hash: str,
        blockers: list[str],
        warnings: list[str] | None = None,
        git_preflight: WorktreeGitPreflight | None = None,
    ) -> "WorktreePrepareResult":
        """Build a blocked prepare result from the current dry-run plan."""

        return cls(
            agent_session_id=plan.agent_session_id,
            project_id=plan.project_id,
            repository_workspace_id=plan.repository_workspace_id,
            plan_hash=plan.plan_hash,
            submitted_plan_hash=submitted_plan_hash,
            worktree_path=plan.worktree_path,
            branch_name=plan.branch_name,
            base_branch=plan.base_branch,
            base_commit_sha=plan.base_commit_sha,
            git_preflight=git_preflight,
            blockers=blockers,
            warnings=warnings or [],
            runs_git=git_preflight is not None,
        )

    @field_validator("prepare_status", "blocked_reason", "next_action")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required status labels."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("prepare label must not be blank")
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
