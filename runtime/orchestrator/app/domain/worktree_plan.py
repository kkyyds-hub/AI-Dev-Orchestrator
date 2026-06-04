"""Dry-run worktree planning domain models for coding sessions."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel


class WorktreePlan(DomainModel):
    """Pure dry-run plan for a future per-session worktree.

    The plan is intentionally descriptive only: commands are previews for a
    later confirmed operation and are never executed by P1-C code.
    """

    agent_session_id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    safe: bool
    workspace_type: str = "worktree"
    worktree_path: str | None = Field(default=None, max_length=1_000)
    branch_name: str | None = Field(default=None, max_length=200)
    base_branch: str | None = Field(default=None, max_length=200)
    base_commit_sha: str | None = Field(default=None, max_length=80)
    git_commands_to_run: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator(
        "worktree_path",
        "branch_name",
        "base_branch",
        "base_commit_sha",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Trim optional strings and collapse blanks to None."""

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
