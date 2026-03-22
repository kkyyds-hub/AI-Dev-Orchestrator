"""Repository snapshot domain models introduced for V4 Day02."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class RepositorySnapshotStatus(StrEnum):
    """Stable scan-status values exposed by the Day02 snapshot model."""

    SUCCESS = "success"
    FAILED = "failed"


class RepositoryTreeNodeKind(StrEnum):
    """Minimal node kinds kept in the repository tree snapshot."""

    DIRECTORY = "directory"
    FILE = "file"


class RepositoryLanguageStat(DomainModel):
    """One aggregated language/file-type bucket inside a repository snapshot."""

    language: str = Field(min_length=1, max_length=100)
    file_count: int = Field(default=0, ge=0)

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        """Trim language labels and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Repository language labels cannot be blank.")

        return normalized_value


class RepositoryTreeNode(DomainModel):
    """One directory/file node kept inside the Day02 tree summary."""

    name: str = Field(min_length=1, max_length=255)
    relative_path: str = Field(min_length=1, max_length=2_000)
    kind: RepositoryTreeNodeKind
    directory_count: int = Field(default=0, ge=0)
    file_count: int = Field(default=0, ge=0)
    children: list["RepositoryTreeNode"] = Field(default_factory=list, max_length=100)
    truncated: bool = False

    @field_validator("name", "relative_path")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        """Trim text fields and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Repository tree node text fields cannot be blank.")

        return normalized_value

    @model_validator(mode="after")
    def validate_tree_node(self) -> "RepositoryTreeNode":
        """Keep file nodes leaf-shaped and directory counters non-negative."""

        if self.kind == RepositoryTreeNodeKind.FILE and self.children:
            raise ValueError("Repository file nodes cannot contain child nodes.")
        if self.kind == RepositoryTreeNodeKind.FILE and self.directory_count != 0:
            raise ValueError("Repository file nodes cannot report directory counts.")
        if self.kind == RepositoryTreeNodeKind.FILE and self.file_count not in {0, 1}:
            raise ValueError("Repository file nodes must report a file_count of 0 or 1.")

        return self


class RepositorySnapshot(DomainModel):
    """Latest structured workspace scan summary attached to one project repository."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    repository_workspace_id: UUID
    repository_root_path: str = Field(min_length=1, max_length=1_000)
    status: RepositorySnapshotStatus = Field(default=RepositorySnapshotStatus.SUCCESS)
    directory_count: int = Field(default=0, ge=0)
    file_count: int = Field(default=0, ge=0)
    ignored_directory_names: list[str] = Field(default_factory=list, max_length=50)
    language_breakdown: list[RepositoryLanguageStat] = Field(
        default_factory=list,
        max_length=100,
    )
    tree: list[RepositoryTreeNode] = Field(default_factory=list, max_length=100)
    scan_error: str | None = Field(default=None, max_length=2_000)
    scanned_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("repository_root_path")
    @classmethod
    def normalize_repository_root_path(cls, value: str) -> str:
        """Trim and validate the persisted repository root path."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Repository snapshot repository_root_path cannot be blank.")

        return normalized_value

    @field_validator("scan_error")
    @classmethod
    def normalize_scan_error(cls, value: str | None) -> str | None:
        """Trim optional scan errors and collapse blanks into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("ignored_directory_names")
    @classmethod
    def normalize_ignored_directory_names(cls, value: list[str]) -> list[str]:
        """Trim, deduplicate and drop blank ignored-directory names."""

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
    def validate_snapshot(self) -> "RepositorySnapshot":
        """Keep timestamps, error state and persisted paths aligned."""

        object.__setattr__(self, "scanned_at", ensure_utc_datetime(self.scanned_at))
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        if self.updated_at < self.created_at:
            raise ValueError(
                "Repository snapshot updated_at cannot be earlier than created_at."
            )
        if self.scanned_at < self.created_at:
            raise ValueError(
                "Repository snapshot scanned_at cannot be earlier than created_at."
            )
        if self.status == RepositorySnapshotStatus.SUCCESS and self.scan_error is not None:
            raise ValueError("Successful repository snapshots cannot carry scan errors.")
        if self.status == RepositorySnapshotStatus.FAILED and self.scan_error is None:
            raise ValueError("Failed repository snapshots must carry one scan_error.")

        repository_root_path = Path(self.repository_root_path)
        if not repository_root_path.is_absolute():
            raise ValueError("Repository snapshot repository_root_path must be absolute.")

        return self


RepositoryTreeNode.model_rebuild()
