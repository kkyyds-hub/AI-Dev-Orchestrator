"""Domain models for V4 Day09 repository verification baselines."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class RepositoryVerificationCategory(StrEnum):
    """Stable Day09 verification-template categories."""

    BUILD = "build"
    TEST = "test"
    LINT = "lint"
    TYPECHECK = "typecheck"


class RepositoryVerificationTemplateReference(DomainModel):
    """One reusable verification template referenced by plans or batches."""

    id: UUID
    category: RepositoryVerificationCategory
    name: str = Field(min_length=1, max_length=100)
    command: str = Field(min_length=1, max_length=2_000)
    working_directory: str = Field(default=".", min_length=1, max_length=500)
    timeout_seconds: int = Field(default=600, ge=30, le=7_200)
    enabled_by_default: bool = True
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name", "command")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required text fields and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Repository verification template text cannot be blank.")

        return normalized_value

    @field_validator("description")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Trim optional text and collapse blanks into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("working_directory")
    @classmethod
    def normalize_working_directory(cls, value: str) -> str:
        """Store one repository-relative POSIX working directory."""

        normalized_value = value.replace("\\", "/").strip()
        if not normalized_value:
            return "."

        normalized_path = PurePosixPath(normalized_value)
        if normalized_path.is_absolute() or ".." in normalized_path.parts:
            raise ValueError(
                "Repository verification working_directory must stay inside the repository."
            )

        if normalized_path.as_posix() == ".":
            return "."

        return normalized_path.as_posix().lstrip("./")


class RepositoryVerificationTemplate(RepositoryVerificationTemplateReference):
    """One persisted Day09 verification template attached to a project repository."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_template_state(self) -> "RepositoryVerificationTemplate":
        """Normalize UTC timestamps and preserve chronological order."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        if self.updated_at < self.created_at:
            raise ValueError(
                "Repository verification template updated_at cannot be earlier than created_at."
            )

        return self


class RepositoryVerificationBaseline(DomainModel):
    """Repository-scoped Day09 verification baseline returned to the UI."""

    project_id: UUID
    templates: list[RepositoryVerificationTemplate] = Field(
        default_factory=list,
        max_length=4,
    )
    template_count: int = Field(default=0, ge=0, le=4)
    configured_categories: list[RepositoryVerificationCategory] = Field(
        default_factory=list,
        max_length=4,
    )
    last_updated_at: datetime | None = None

    @field_validator("templates")
    @classmethod
    def normalize_templates(
        cls,
        values: list[RepositoryVerificationTemplate],
    ) -> list[RepositoryVerificationTemplate]:
        """Deduplicate templates by category while preserving caller order."""

        normalized_items: list[RepositoryVerificationTemplate] = []
        seen_categories: set[RepositoryVerificationCategory] = set()

        for value in values:
            if value.category in seen_categories:
                continue

            normalized_items.append(value)
            seen_categories.add(value.category)

        return normalized_items

    @model_validator(mode="after")
    def validate_baseline_state(self) -> "RepositoryVerificationBaseline":
        """Derive Day09 aggregate fields from the embedded templates."""

        derived_categories = [template.category for template in self.templates]
        derived_template_count = len(self.templates)
        derived_last_updated_at = max(
            (template.updated_at for template in self.templates),
            default=None,
        )

        object.__setattr__(self, "configured_categories", derived_categories)
        object.__setattr__(self, "template_count", derived_template_count)
        object.__setattr__(
            self,
            "last_updated_at",
            ensure_utc_datetime(self.last_updated_at or derived_last_updated_at),
        )

        return self
