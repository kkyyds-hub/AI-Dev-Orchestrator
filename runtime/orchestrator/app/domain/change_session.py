"""Change-session domain models introduced for V4 Day03."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


MAX_CHANGE_SESSION_DIRTY_FILE_PREVIEW = 20


class ChangeSessionWorkspaceStatus(StrEnum):
    """Stable workspace-status values exposed by the Day03 session snapshot."""

    CLEAN = "clean"
    DIRTY = "dirty"


class ChangeSessionGuardStatus(StrEnum):
    """Whether the current Day03 change session is ready for downstream planning."""

    READY = "ready"
    BLOCKED = "blocked"


class ChangeSessionDirtyFileScope(StrEnum):
    """Minimal dirty-file scopes derived from `git status --porcelain`."""

    UNTRACKED = "untracked"
    STAGED = "staged"
    UNSTAGED = "unstaged"
    MIXED = "mixed"


class ChangeSessionDirtyFile(DomainModel):
    """One dirty-file preview item stored with a change-session snapshot."""

    path: str = Field(min_length=1, max_length=2_000)
    git_status: str = Field(min_length=2, max_length=2)
    change_scope: ChangeSessionDirtyFileScope

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        """Trim persisted relative paths and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Change-session dirty-file path cannot be blank.")

        return normalized_value

    @field_validator("git_status")
    @classmethod
    def normalize_git_status(cls, value: str) -> str:
        """Store one stable two-character porcelain status code."""

        if len(value) != 2:
            raise ValueError(
                "Change-session dirty-file git_status must contain two status characters."
            )

        return value


class ChangeSession(DomainModel):
    """One project-bound Day03 branch/workspace status snapshot."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    repository_workspace_id: UUID
    repository_root_path: str = Field(min_length=1, max_length=1_000)
    current_branch: str = Field(min_length=1, max_length=200)
    head_ref: str = Field(min_length=1, max_length=500)
    head_commit_sha: str | None = Field(default=None, max_length=64)
    baseline_branch: str = Field(min_length=1, max_length=200)
    baseline_ref: str = Field(min_length=1, max_length=500)
    baseline_commit_sha: str | None = Field(default=None, max_length=64)
    workspace_status: ChangeSessionWorkspaceStatus = Field(
        default=ChangeSessionWorkspaceStatus.CLEAN
    )
    guard_status: ChangeSessionGuardStatus = Field(
        default=ChangeSessionGuardStatus.READY
    )
    guard_summary: str = Field(min_length=1, max_length=500)
    blocking_reasons: list[str] = Field(default_factory=list, max_length=20)
    dirty_file_count: int = Field(default=0, ge=0)
    dirty_files_truncated: bool = False
    dirty_files: list[ChangeSessionDirtyFile] = Field(
        default_factory=list,
        max_length=MAX_CHANGE_SESSION_DIRTY_FILE_PREVIEW,
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "repository_root_path",
        "current_branch",
        "head_ref",
        "baseline_branch",
        "baseline_ref",
        "guard_summary",
    )
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        """Trim persisted text fields and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Change-session text fields cannot be blank.")

        return normalized_value

    @field_validator("head_commit_sha", "baseline_commit_sha")
    @classmethod
    def normalize_commit_refs(cls, value: str | None) -> str | None:
        """Trim optional commit references and collapse blanks into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("blocking_reasons")
    @classmethod
    def normalize_blocking_reasons(cls, value: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate blocking reasons."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for item in value:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_items:
                continue

            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)

        return normalized_items

    @model_validator(mode="after")
    def validate_change_session(self) -> "ChangeSession":
        """Keep timestamps, dirty preview and guard state aligned."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        if self.updated_at < self.created_at:
            raise ValueError(
                "Change-session updated_at cannot be earlier than created_at."
            )

        repository_root_path = Path(self.repository_root_path)
        if not repository_root_path.is_absolute():
            raise ValueError("Change-session repository_root_path must be absolute.")

        if self.dirty_file_count < len(self.dirty_files):
            raise ValueError(
                "Change-session dirty_file_count cannot be smaller than the preview size."
            )

        if (
            self.workspace_status == ChangeSessionWorkspaceStatus.CLEAN
            and self.dirty_file_count != 0
        ):
            raise ValueError(
                "Clean change sessions cannot report a non-zero dirty_file_count."
            )
        if (
            self.workspace_status == ChangeSessionWorkspaceStatus.CLEAN
            and self.dirty_files
        ):
            raise ValueError(
                "Clean change sessions cannot carry dirty-file preview items."
            )
        if (
            self.workspace_status == ChangeSessionWorkspaceStatus.DIRTY
            and self.dirty_file_count == 0
        ):
            raise ValueError(
                "Dirty change sessions must report at least one dirty file."
            )

        if (
            self.guard_status == ChangeSessionGuardStatus.READY
            and self.blocking_reasons
        ):
            raise ValueError(
                "Ready change sessions cannot carry blocking reasons."
            )
        if (
            self.guard_status == ChangeSessionGuardStatus.BLOCKED
            and not self.blocking_reasons
        ):
            raise ValueError(
                "Blocked change sessions must report at least one blocking reason."
            )

        return self
