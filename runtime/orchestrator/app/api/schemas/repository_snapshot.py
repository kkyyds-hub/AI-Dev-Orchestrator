"""Repository snapshot response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.repository_snapshot import (
    RepositoryLanguageStat,
    RepositorySnapshot,
    RepositorySnapshotStatus,
    RepositoryTreeNode,
    RepositoryTreeNodeKind,
)


class RepositoryLanguageStatResponse(BaseModel):
    """One language/file-type bucket returned with a repository snapshot."""

    language: str
    file_count: int

    @classmethod
    def from_stat(
        cls,
        stat: RepositoryLanguageStat,
    ) -> "RepositoryLanguageStatResponse":
        """Convert one language stat into an API DTO."""

        return cls(language=stat.language, file_count=stat.file_count)


class RepositoryTreeNodeResponse(BaseModel):
    """One bounded tree node returned with the Day02 snapshot summary."""

    name: str
    relative_path: str
    kind: RepositoryTreeNodeKind
    directory_count: int
    file_count: int
    children: list["RepositoryTreeNodeResponse"] = Field(default_factory=list)
    truncated: bool = False

    @classmethod
    def from_node(
        cls,
        node: RepositoryTreeNode,
    ) -> "RepositoryTreeNodeResponse":
        """Convert one repository tree node into an API DTO."""

        return cls(
            name=node.name,
            relative_path=node.relative_path,
            kind=node.kind,
            directory_count=node.directory_count,
            file_count=node.file_count,
            children=[cls.from_node(child) for child in node.children],
            truncated=node.truncated,
        )


class RepositorySnapshotResponse(BaseModel):
    """Latest structured repository snapshot shared by repository/project payloads."""

    id: UUID
    project_id: UUID
    repository_workspace_id: UUID
    repository_root_path: str
    status: RepositorySnapshotStatus
    directory_count: int
    file_count: int
    ignored_directory_names: list[str]
    language_breakdown: list[RepositoryLanguageStatResponse]
    tree: list[RepositoryTreeNodeResponse]
    scan_error: str | None = None
    scanned_at: datetime
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_snapshot(
        cls,
        snapshot: RepositorySnapshot,
    ) -> "RepositorySnapshotResponse":
        """Convert one repository snapshot domain model into an API DTO."""

        return cls(
            id=snapshot.id,
            project_id=snapshot.project_id,
            repository_workspace_id=snapshot.repository_workspace_id,
            repository_root_path=snapshot.repository_root_path,
            status=snapshot.status,
            directory_count=snapshot.directory_count,
            file_count=snapshot.file_count,
            ignored_directory_names=list(snapshot.ignored_directory_names),
            language_breakdown=[
                RepositoryLanguageStatResponse.from_stat(stat)
                for stat in snapshot.language_breakdown
            ],
            tree=[RepositoryTreeNodeResponse.from_node(node) for node in snapshot.tree],
            scan_error=snapshot.scan_error,
            scanned_at=snapshot.scanned_at,
            created_at=snapshot.created_at,
            updated_at=snapshot.updated_at,
        )


RepositoryTreeNodeResponse.model_rebuild()
