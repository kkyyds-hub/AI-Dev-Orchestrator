"""Repository workspace request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.repository_workspace import (
    RepositoryAccessMode,
    RepositoryWorkspace,
)
from app.services.repository_workspace_settings_service import (
    RepositoryWorkspaceSettingsSummary,
)


class RepositoryWorkspaceBindRequest(BaseModel):
    """DTO used to bind one project to a local repository workspace."""

    root_path: str = Field(
        min_length=1,
        max_length=1_000,
        description="Absolute local repository root path under the configured safety boundary.",
    )
    display_name: str | None = Field(
        default=None,
        max_length=200,
        description="Optional label shown on future repository cards and project detail views.",
    )
    access_mode: RepositoryAccessMode = Field(
        default=RepositoryAccessMode.READ_ONLY,
        description="Current Day01 access mode. Only read-only binding is supported.",
    )
    default_base_branch: str = Field(
        default="main",
        min_length=1,
        max_length=200,
        description="Default baseline branch recorded for later Day03-Day14 flows.",
    )
    ignore_rule_summary: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Optional ignore-rule summary. Defaults to the Day01 conservative baseline.",
    )


class RepositoryWorkspaceSettingsResponse(BaseModel):
    """DTO returned by the repository workspace settings endpoints."""

    allowed_workspace_roots: list[str]
    default_workspace_root: str
    using_default: bool

    @classmethod
    def from_summary(
        cls,
        summary: RepositoryWorkspaceSettingsSummary,
    ) -> "RepositoryWorkspaceSettingsResponse":
        """Convert one settings summary into an API DTO."""

        return cls(
            allowed_workspace_roots=list(summary.allowed_workspace_roots),
            default_workspace_root=summary.default_workspace_root,
            using_default=summary.using_default,
        )


class RepositoryWorkspaceSettingsUpdateRequest(BaseModel):
    """Editable repository workspace safety boundary settings."""

    allowed_workspace_roots: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Absolute local directories that may contain bindable Git repositories.",
    )


class RepositoryWorkspaceResponse(BaseModel):
    """API DTO shared by repository routes and project detail payloads."""

    id: UUID
    project_id: UUID
    root_path: str
    display_name: str
    access_mode: RepositoryAccessMode
    default_base_branch: str
    ignore_rule_summary: list[str]
    allowed_workspace_root: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_workspace(
        cls,
        workspace: RepositoryWorkspace,
    ) -> "RepositoryWorkspaceResponse":
        """Convert one repository-workspace domain model into an API DTO."""

        return cls(
            id=workspace.id,
            project_id=workspace.project_id,
            root_path=workspace.root_path,
            display_name=workspace.display_name,
            access_mode=workspace.access_mode,
            default_base_branch=workspace.default_base_branch,
            ignore_rule_summary=list(workspace.ignore_rule_summary),
            allowed_workspace_root=workspace.allowed_workspace_root,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )
