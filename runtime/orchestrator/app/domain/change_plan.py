"""Domain models for V4 Day06 structured change-plan drafts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.repository_verification import (
    RepositoryVerificationTemplateReference,
)


class ChangePlanStatus(StrEnum):
    """Stable status values for Day06 change-plan heads."""

    DRAFT = "draft"


class ChangePlanTargetFile(DomainModel):
    """One target file carried by a change-plan draft version."""

    relative_path: str = Field(min_length=1, max_length=1_000)
    language: str = Field(min_length=1, max_length=100)
    file_type: str = Field(min_length=1, max_length=50)
    rationale: str | None = Field(default=None, max_length=300)
    match_reasons: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("relative_path")
    @classmethod
    def normalize_relative_path(cls, value: str) -> str:
        """Store one safe repository-relative POSIX path."""

        normalized_value = value.replace("\\", "/").strip().lstrip("./")
        if not normalized_value:
            raise ValueError("Change-plan target relative_path cannot be blank.")

        normalized_path = PurePosixPath(normalized_value)
        if normalized_path.is_absolute() or ".." in normalized_path.parts:
            raise ValueError("Change-plan target relative_path must stay inside the repository.")

        return normalized_path.as_posix()

    @field_validator("language", "file_type")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required target-file text values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Change-plan target text fields cannot be blank.")

        return normalized_value

    @field_validator("rationale")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Trim optional text and collapse blanks into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("match_reasons")
    @classmethod
    def normalize_match_reasons(cls, values: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate target-file reasons."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items


class ChangePlanVersion(DomainModel):
    """One immutable Day06 change-plan draft snapshot."""

    id: UUID = Field(default_factory=uuid4)
    change_plan_id: UUID
    version_number: int = Field(ge=1)
    intent_summary: str = Field(min_length=1, max_length=2_000)
    source_summary: str = Field(min_length=1, max_length=1_200)
    focus_terms: list[str] = Field(default_factory=list, max_length=20)
    target_files: list[ChangePlanTargetFile] = Field(default_factory=list, min_length=1, max_length=30)
    expected_actions: list[str] = Field(default_factory=list, min_length=1, max_length=20)
    risk_notes: list[str] = Field(default_factory=list, min_length=1, max_length=20)
    verification_commands: list[str] = Field(default_factory=list, max_length=20)
    verification_templates: list[RepositoryVerificationTemplateReference] = Field(
        default_factory=list,
        max_length=4,
    )
    related_deliverable_ids: list[UUID] = Field(default_factory=list, min_length=1, max_length=10)
    context_pack_generated_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("intent_summary", "source_summary")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required version text values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Change-plan version text fields cannot be blank.")

        return normalized_value

    @field_validator("focus_terms", "expected_actions", "risk_notes", "verification_commands")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate version string-list fields."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    @field_validator("related_deliverable_ids")
    @classmethod
    def normalize_related_deliverable_ids(cls, values: list[UUID]) -> list[UUID]:
        """Deduplicate related deliverable IDs while preserving order."""

        normalized_items: list[UUID] = []
        seen_items: set[UUID] = set()

        for value in values:
            if value in seen_items:
                continue

            normalized_items.append(value)
            seen_items.add(value)

        return normalized_items

    @field_validator("target_files")
    @classmethod
    def normalize_target_files(
        cls,
        values: list[ChangePlanTargetFile],
    ) -> list[ChangePlanTargetFile]:
        """Deduplicate target files by relative path."""

        normalized_items: list[ChangePlanTargetFile] = []
        seen_paths: set[str] = set()

        for value in values:
            if value.relative_path in seen_paths:
                continue

            normalized_items.append(value)
            seen_paths.add(value.relative_path)

        return normalized_items

    @field_validator("verification_templates")
    @classmethod
    def normalize_verification_templates(
        cls,
        values: list[RepositoryVerificationTemplateReference],
    ) -> list[RepositoryVerificationTemplateReference]:
        """Deduplicate verification-template references by ID."""

        normalized_items: list[RepositoryVerificationTemplateReference] = []
        seen_ids: set[UUID] = set()

        for value in values:
            if value.id in seen_ids:
                continue

            normalized_items.append(value)
            seen_ids.add(value.id)

        return normalized_items

    @model_validator(mode="after")
    def validate_version_state(self) -> "ChangePlanVersion":
        """Normalize UTC-aware timestamps for persisted version snapshots."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(
            self,
            "context_pack_generated_at",
            ensure_utc_datetime(self.context_pack_generated_at),
        )
        if not self.verification_commands and not self.verification_templates:
            raise ValueError(
                "Change-plan version requires at least one verification command or template."
            )
        return self


class ChangePlan(DomainModel):
    """One Day06 change-plan head that can accumulate multiple draft versions."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    task_id: UUID
    primary_deliverable_id: UUID | None = None
    status: ChangePlanStatus = Field(default=ChangePlanStatus.DRAFT)
    title: str = Field(min_length=1, max_length=200)
    current_version_number: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """Trim the change-plan title and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Change-plan title cannot be blank.")

        return normalized_value

    @model_validator(mode="after")
    def validate_plan_state(self) -> "ChangePlan":
        """Normalize UTC timestamps and keep head counters aligned."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        if self.updated_at < self.created_at:
            raise ValueError("Change-plan updated_at cannot be earlier than created_at.")

        return self
