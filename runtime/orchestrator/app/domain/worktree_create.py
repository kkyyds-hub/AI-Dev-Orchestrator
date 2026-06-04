"""Workspace create domain models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel, utc_now
from app.domain.worktree_plan import WorktreePlan
from app.domain.worktree_prepare import WorktreeGitPreflight


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
    """Response shape for guarded real workspace creation."""

    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    plan_hash: str = Field(min_length=64, max_length=64)
    submitted_plan_hash: str = Field(min_length=64, max_length=64)
    create_status: str = "blocked"
    blocked_reason: str | None = "workspace_create_blocked"
    dry_run: bool = True
    requires_user_confirmation: bool = True
    worktree_path: str | None = Field(default=None, max_length=1_000)
    branch_name: str | None = Field(default=None, max_length=200)
    base_branch: str | None = Field(default=None, max_length=200)
    base_commit_sha: str | None = Field(default=None, max_length=80)
    checked_at: datetime = Field(default_factory=utc_now)
    git_preflight: WorktreeGitPreflight | None = None
    write_command_preview: list[WorktreeWriteCommandPreview] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_action: str = "resolve_workspace_create_blockers"
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
            git_preflight=None,
            write_command_preview=write_command_preview or [],
            blockers=blockers,
            warnings=warnings or [],
        )

    @classmethod
    def created_from_plan(
        cls,
        *,
        plan: WorktreePlan,
        submitted_plan_hash: str,
        git_preflight: WorktreeGitPreflight,
        write_command_preview: list[WorktreeWriteCommandPreview],
        warnings: list[str] | None = None,
    ) -> "WorktreeCreateResult":
        """Build a successful create result from a validated plan."""

        return cls(
            agent_session_id=plan.agent_session_id,
            project_id=plan.project_id,
            repository_workspace_id=plan.repository_workspace_id,
            plan_hash=plan.plan_hash,
            submitted_plan_hash=submitted_plan_hash,
            create_status="created",
            blocked_reason=None,
            dry_run=False,
            requires_user_confirmation=plan.requires_user_confirmation,
            worktree_path=plan.worktree_path,
            branch_name=plan.branch_name,
            base_branch=plan.base_branch,
            base_commit_sha=git_preflight.repository_head_sha,
            git_preflight=git_preflight,
            write_command_preview=write_command_preview,
            blockers=[],
            warnings=warnings or [],
            next_action="workspace_created_ready_for_coding",
            creates_worktree=True,
            creates_branch=True,
            runs_git=True,
            runs_write_git=True,
            mutates_agent_session_workspace=True,
        )

    @classmethod
    def failed_from_plan(
        cls,
        *,
        plan: WorktreePlan,
        submitted_plan_hash: str,
        blocked_reason: str,
        blockers: list[str],
        warnings: list[str] | None = None,
        git_preflight: WorktreeGitPreflight | None = None,
        write_command_preview: list[WorktreeWriteCommandPreview] | None = None,
        attempted_write_git: bool = False,
        wrote_agent_session_error: bool = False,
    ) -> "WorktreeCreateResult":
        """Build a failed create result after guarded validation or execution."""

        return cls(
            agent_session_id=plan.agent_session_id,
            project_id=plan.project_id,
            repository_workspace_id=plan.repository_workspace_id,
            plan_hash=plan.plan_hash,
            submitted_plan_hash=submitted_plan_hash,
            create_status="failed" if attempted_write_git else "blocked",
            blocked_reason=blocked_reason,
            dry_run=True,
            requires_user_confirmation=plan.requires_user_confirmation,
            worktree_path=plan.worktree_path,
            branch_name=plan.branch_name,
            base_branch=plan.base_branch,
            base_commit_sha=(
                git_preflight.repository_head_sha if git_preflight is not None else None
            ),
            git_preflight=git_preflight,
            write_command_preview=write_command_preview or [],
            blockers=blockers,
            warnings=warnings or [],
            next_action="resolve_workspace_create_blockers",
            creates_worktree=False,
            creates_branch=False,
            runs_git=git_preflight is not None or attempted_write_git,
            runs_write_git=attempted_write_git,
            mutates_agent_session_workspace=wrote_agent_session_error,
        )

    @field_validator("create_status", "next_action")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required status labels."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("create label must not be blank")
        return normalized_value

    @field_validator("blocked_reason")
    @classmethod
    def normalize_optional_blocked_reason(cls, value: str | None) -> str | None:
        """Trim optional blocked reason."""

        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

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
