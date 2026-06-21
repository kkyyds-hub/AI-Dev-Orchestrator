"""Repository local git-write request and response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class LocalGitWriteFileEntry(BaseModel):
    """One file to write in an apply-local request."""

    relative_path: str = Field(
        min_length=1,
        max_length=2000,
        description="Relative path inside the repository workspace.",
    )
    content: str = Field(
        min_length=0,
        max_length=2_000_000,
        description="File content to write.",
    )


class ApplyLocalRequest(BaseModel):
    """Request body for apply-local."""

    files: list[LocalGitWriteFileEntry] = Field(
        min_length=1,
        max_length=200,
        description="Files to write into the workspace.",
    )


class ApplyLocalResponse(BaseModel):
    """Response for apply-local."""

    status: str
    change_batch_id: UUID
    changed_files: list[str] = Field(default_factory=list)
    diff_summary: dict[str, list[str]] = Field(default_factory=dict)
    verification_passed: bool = False
    rollback_performed: bool = False
    log_path: str
    error_category: str | None = None
    error_summary: str | None = None


class GitCommitResponse(BaseModel):
    """Response for git-commit."""

    status: str
    change_batch_id: UUID
    commit_sha: str | None = None
    branch_name: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    log_path: str
    error_category: str | None = None
    error_summary: str | None = None
