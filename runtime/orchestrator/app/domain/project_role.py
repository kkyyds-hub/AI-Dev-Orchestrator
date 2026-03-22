"""Role catalog and project role configuration models for V3 Day05."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class ProjectRoleCode(StrEnum):
    """Stable built-in role codes available to each project."""

    PRODUCT_MANAGER = "product_manager"
    ARCHITECT = "architect"
    ENGINEER = "engineer"
    REVIEWER = "reviewer"


class RoleProfile(DomainModel):
    """Shared editable identity fields for system roles and project roles."""

    name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    responsibilities: list[str] = Field(default_factory=list, max_length=12)
    input_boundary: list[str] = Field(default_factory=list, max_length=12)
    output_boundary: list[str] = Field(default_factory=list, max_length=12)
    default_skill_slots: list[str] = Field(default_factory=list, max_length=12)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("name", "summary")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        """Trim text fields and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Role text fields cannot be blank.")

        return normalized_value

    @field_validator(
        "responsibilities",
        "input_boundary",
        "output_boundary",
        "default_skill_slots",
    )
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate editable list fields."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for item in value:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_items:
                continue

            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)

        return normalized_items


class RoleCatalogEntry(RoleProfile):
    """One immutable built-in role entry exposed by the Day05 catalog."""

    code: ProjectRoleCode
    enabled_by_default: bool = True

    def create_project_role_config(self, project_id: UUID) -> "ProjectRoleConfig":
        """Expand one built-in catalog entry into a project-owned config object."""

        return ProjectRoleConfig(
            project_id=project_id,
            role_code=self.code,
            enabled=self.enabled_by_default,
            name=self.name,
            summary=self.summary,
            responsibilities=list(self.responsibilities),
            input_boundary=list(self.input_boundary),
            output_boundary=list(self.output_boundary),
            default_skill_slots=list(self.default_skill_slots),
            sort_order=self.sort_order,
        )


class ProjectRoleConfig(RoleProfile):
    """Persisted role configuration owned by one project."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    role_code: ProjectRoleCode
    enabled: bool = True
    custom_notes: str | None = Field(default=None, max_length=1_000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("custom_notes")
    @classmethod
    def normalize_custom_notes(cls, value: str | None) -> str | None:
        """Collapse blank note fields into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @model_validator(mode="after")
    def validate_timestamps(self) -> "ProjectRoleConfig":
        """Keep persisted timestamps UTC-aware and ordered."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")

        return self


class ProjectRoleCatalog(DomainModel):
    """Resolved role catalog snapshot returned for one project."""

    project_id: UUID
    available_role_count: int = Field(ge=0)
    enabled_role_count: int = Field(ge=0)
    roles: list[ProjectRoleConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts(self) -> "ProjectRoleCatalog":
        """Keep summary counts aligned with the actual role list."""

        if self.available_role_count != len(self.roles):
            raise ValueError("available_role_count must equal the number of roles.")

        actual_enabled_count = sum(1 for role in self.roles if role.enabled)
        if self.enabled_role_count != actual_enabled_count:
            raise ValueError("enabled_role_count must equal the enabled role total.")

        return self
