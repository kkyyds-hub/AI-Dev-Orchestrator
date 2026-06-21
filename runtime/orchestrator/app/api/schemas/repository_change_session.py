"""Repository change-session response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.change_session import (
    ChangeSession,
    ChangeSessionDirtyFile,
    ChangeSessionDirtyFileScope,
    ChangeSessionGuardStatus,
    ChangeSessionWorkspaceStatus,
)


class ChangeSessionDirtyFileResponse(BaseModel):
    """One bounded dirty-file preview item returned with a Day03 session snapshot."""

    path: str
    git_status: str
    change_scope: ChangeSessionDirtyFileScope

    @classmethod
    def from_dirty_file(
        cls,
        dirty_file: ChangeSessionDirtyFile,
    ) -> "ChangeSessionDirtyFileResponse":
        """Convert one change-session dirty-file item into an API DTO."""

        return cls(
            path=dirty_file.path,
            git_status=dirty_file.git_status,
            change_scope=dirty_file.change_scope,
        )


class ChangeSessionResponse(BaseModel):
    """Latest active Day03 change-session snapshot for one project repository."""

    id: UUID
    project_id: UUID
    repository_workspace_id: UUID
    repository_root_path: str
    current_branch: str
    head_ref: str
    head_commit_sha: str | None = None
    baseline_branch: str
    baseline_ref: str
    baseline_commit_sha: str | None = None
    workspace_status: ChangeSessionWorkspaceStatus
    guard_status: ChangeSessionGuardStatus
    guard_summary: str
    blocking_reasons: list[str]
    dirty_file_count: int
    dirty_files_truncated: bool = False
    dirty_files: list[ChangeSessionDirtyFileResponse]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_change_session(
        cls,
        change_session: ChangeSession,
    ) -> "ChangeSessionResponse":
        """Convert one Day03 change-session domain model into an API DTO."""

        return cls(
            id=change_session.id,
            project_id=change_session.project_id,
            repository_workspace_id=change_session.repository_workspace_id,
            repository_root_path=change_session.repository_root_path,
            current_branch=change_session.current_branch,
            head_ref=change_session.head_ref,
            head_commit_sha=change_session.head_commit_sha,
            baseline_branch=change_session.baseline_branch,
            baseline_ref=change_session.baseline_ref,
            baseline_commit_sha=change_session.baseline_commit_sha,
            workspace_status=change_session.workspace_status,
            guard_status=change_session.guard_status,
            guard_summary=change_session.guard_summary,
            blocking_reasons=list(change_session.blocking_reasons),
            dirty_file_count=change_session.dirty_file_count,
            dirty_files_truncated=change_session.dirty_files_truncated,
            dirty_files=[
                ChangeSessionDirtyFileResponse.from_dirty_file(item)
                for item in change_session.dirty_files
            ],
            created_at=change_session.created_at,
            updated_at=change_session.updated_at,
        )
