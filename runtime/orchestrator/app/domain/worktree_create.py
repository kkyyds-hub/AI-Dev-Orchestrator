"""Workspace create blocked skeleton domain models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel, utc_now
from app.domain.worktree_plan import WorktreePlan


class WorktreeWriteCommandPreview(DomainModel):
    """Immutable preview of one future write git command."""

    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int
    mutates_repository: bool = True
    command_kind: str
    execution_enabled: bool = False

    @field_validator("cwd", "command_kind")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required preview text."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("write command preview text must not be blank")
        return normalized_value


class WorktreeCreateResult(DomainModel):
    """Blocked response shape for future real workspace creation.

    P1-D-E-A defines the write-command boundary and API/service contract only.
    It never runs git, creates a worktree, creates a branch, or mutates
    AgentSession workspace fields.
    """

    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    plan_hash: str = Field(min_length=64, max_length=64)
    submitted_plan_hash: str = Field(min_length=64, max_length=64)
    create_status: str = "blocked"
    blocked_reason: str = "workspace_create_not_implemented"
    dry_run: bool = True
    requires_user_confirmation: bool = True
    worktree_path: str | None = Field(default=None, max_length=1_000)
    branch_name: str | None = Field(default=None, max_length=200)
    base_branch: str | None = Field(default=None, max_length=200)
    base_commit_sha: str | None = Field(default=None, max_length=80)
    checked_at: datetime = Field(default_factory=utc_now)
    write_command_preview: list[WorktreeWriteCommandPreview] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_action: str = "implement_workspace_create_execution_after_gate"
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
        write_command_preview: list[WorktreeWriteCommandPreview] | None = None,
    ) -> "WorktreeCreateResult":
        """Build a blocked create skeleton result from the current plan."""

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
            write_command_preview=write_command_preview or [],
            blockers=blockers,
            warnings=warnings or [],
        )

    @field_validator("create_status", "blocked_reason", "next_action")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required status labels."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("create label must not be blank")
        return normalized_value

    @field_validator("blockers", "warnings")
    @classmethod
    def normalize_reason_lists(cls, value: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate reason lists."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for item in value:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_items:
                continue
            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)
        return normalized_items
