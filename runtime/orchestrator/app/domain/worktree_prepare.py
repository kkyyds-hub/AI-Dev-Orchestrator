"""Workspace prepare skeleton domain models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel, utc_now
from app.domain.worktree_plan import WorktreePlan


class WorktreePrepareResult(DomainModel):
    """Blocked result for the future real workspace prepare step.

    P1-D-C intentionally exposes the API shape before implementation.  It never
    creates a worktree, creates a branch, runs git, or mutates AgentSession
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
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_action: str = "implement_workspace_prepare_execution_after_gate"
    creates_worktree: bool = False
    creates_branch: bool = False
    runs_git: bool = False
    mutates_agent_session_workspace: bool = False

    @classmethod
    def blocked_from_plan(
        cls,
        *,
        plan: WorktreePlan,
        submitted_plan_hash: str,
        blockers: list[str],
        warnings: list[str] | None = None,
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
            blockers=blockers,
            warnings=warnings or [],
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

        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for item in value:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_items:
                continue
            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)
        return normalized_items
