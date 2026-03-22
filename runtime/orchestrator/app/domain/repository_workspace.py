"""Repository workspace domain models introduced for V4 Day01."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class RepositoryAccessMode(StrEnum):
    """Stable access modes exposed by the repository binding model."""

    READ_ONLY = "read_only"


class RepositoryWorkspace(DomainModel):
    """One project-bound local repository workspace entry."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    root_path: str = Field(min_length=1, max_length=1_000)
    display_name: str = Field(min_length=1, max_length=200)
    access_mode: RepositoryAccessMode = Field(default=RepositoryAccessMode.READ_ONLY)
    default_base_branch: str = Field(min_length=1, max_length=200, default="main")
    ignore_rule_summary: list[str] = Field(default_factory=list, max_length=20)
    allowed_workspace_root: str = Field(min_length=1, max_length=1_000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "root_path",
        "display_name",
        "default_base_branch",
        "allowed_workspace_root",
    )
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        """Trim persisted text values and reject blank strings."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Repository workspace text fields cannot be blank.")

        return normalized_value

    @field_validator("ignore_rule_summary")
    @classmethod
    def normalize_ignore_rule_summary(cls, value: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate ignore-summary items."""

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
    def validate_consistency(self) -> "RepositoryWorkspace":
        """Ensure timestamps and persisted paths remain self-consistent."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        if self.updated_at < self.created_at:
            raise ValueError(
                "Repository workspace updated_at cannot be earlier than created_at."
            )

        root_path = Path(self.root_path)
        allowed_workspace_root = Path(self.allowed_workspace_root)
        if not root_path.is_absolute():
            raise ValueError("Repository workspace root_path must be absolute.")
        if not allowed_workspace_root.is_absolute():
            raise ValueError(
                "Repository workspace allowed_workspace_root must be absolute."
            )

        try:
            root_path.relative_to(allowed_workspace_root)
        except ValueError as exc:
            raise ValueError(
                "Repository workspace root_path must stay within the allowed workspace root."
            ) from exc

        return self
