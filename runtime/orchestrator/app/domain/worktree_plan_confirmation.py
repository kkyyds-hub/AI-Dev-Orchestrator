"""Workspace plan confirmation receipt domain models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel, utc_now
from app.domain.worktree_plan import WorktreePlan


class WorktreePlanConfirmationReceipt(DomainModel):
    """Non-persistent receipt for a user-confirmed dry-run worktree plan.

    P1-D-B stops at confirmation intent capture.  The receipt proves that a
    user confirmed the current plan hash, but it does not create a worktree,
    create a branch, run git, or mutate AgentSession workspace fields.
    """

    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    plan_hash: str = Field(min_length=64, max_length=64)
    confirmed_plan_hash: str = Field(min_length=64, max_length=64)
    confirmation_status: str = "confirmed"
    confirmation_scope: str = "workspace_plan_dry_run"
    dry_run: bool = True
    requires_user_confirmation: bool = True
    worktree_path: str | None = Field(default=None, max_length=1_000)
    branch_name: str | None = Field(default=None, max_length=200)
    base_branch: str | None = Field(default=None, max_length=200)
    base_commit_sha: str | None = Field(default=None, max_length=80)
    confirmed_by: str | None = Field(default=None, max_length=200)
    confirmed_at: datetime = Field(default_factory=utc_now)
    next_action: str = "await_explicit_workspace_creation_request"
    creates_worktree: bool = False
    creates_branch: bool = False
    mutates_agent_session_workspace: bool = False

    @classmethod
    def from_plan(
        cls,
        *,
        plan: WorktreePlan,
        confirmed_by: str | None = None,
    ) -> "WorktreePlanConfirmationReceipt":
        """Build a receipt from the currently validated dry-run plan."""

        return cls(
            agent_session_id=plan.agent_session_id,
            project_id=plan.project_id,
            repository_workspace_id=plan.repository_workspace_id,
            plan_hash=plan.plan_hash,
            confirmed_plan_hash=plan.plan_hash,
            worktree_path=plan.worktree_path,
            branch_name=plan.branch_name,
            base_branch=plan.base_branch,
            base_commit_sha=plan.base_commit_sha,
            confirmed_by=confirmed_by,
        )

    @field_validator("confirmation_status", "confirmation_scope", "next_action")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required receipt labels."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("receipt label must not be blank")
        return normalized_value

    @field_validator("confirmed_by", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Trim optional user identity text."""

        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None
