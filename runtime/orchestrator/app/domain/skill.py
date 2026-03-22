"""Skill registry and role-binding domain models for V3 Day13."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
import re
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.project_role import ProjectRoleCode


_SKILL_CODE_PATTERN = re.compile(r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$")
_SKILL_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")


class SkillBindingSource(StrEnum):
    """How one project-role skill binding was produced."""

    DEFAULT_SEED = "default_seed"
    MANUAL = "manual"


class SkillVersionRecord(DomainModel):
    """Immutable snapshot of one Skill version."""

    id: UUID = Field(default_factory=uuid4)
    skill_id: UUID
    version: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=1_000)
    applicable_role_codes: list[ProjectRoleCode] = Field(default_factory=list, max_length=12)
    enabled: bool = True
    change_note: str | None = Field(default=None, max_length=1_000)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("version")
    @classmethod
    def normalize_version(cls, value: str) -> str:
        """Trim and validate one Skill version string."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Skill version cannot be blank.")
        if not _SKILL_VERSION_PATTERN.fullmatch(normalized_value):
            raise ValueError(
                "Skill version must use letters, numbers, dots, underscores or hyphens."
            )

        return normalized_value

    @field_validator("name", "summary", "purpose")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        """Trim text fields and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Skill text fields cannot be blank.")

        return normalized_value

    @field_validator("change_note")
    @classmethod
    def normalize_change_note(cls, value: str | None) -> str | None:
        """Collapse blank change notes into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("applicable_role_codes")
    @classmethod
    def normalize_applicable_role_codes(
        cls,
        value: list[ProjectRoleCode],
    ) -> list[ProjectRoleCode]:
        """Deduplicate applicable role codes while preserving order."""

        normalized_codes: list[ProjectRoleCode] = []
        seen_codes: set[ProjectRoleCode] = set()

        for role_code in value:
            if role_code in seen_codes:
                continue

            normalized_codes.append(role_code)
            seen_codes.add(role_code)

        if not normalized_codes:
            raise ValueError("Skill must target at least one applicable role.")

        return normalized_codes

    @model_validator(mode="after")
    def validate_created_at(self) -> "SkillVersionRecord":
        """Keep persisted timestamps UTC-aware."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        return self


class SkillDefinition(DomainModel):
    """Current registry record for one Skill."""

    id: UUID = Field(default_factory=uuid4)
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=1_000)
    applicable_role_codes: list[ProjectRoleCode] = Field(default_factory=list, max_length=12)
    enabled: bool = True
    current_version: str = Field(min_length=1, max_length=40)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    version_history: list[SkillVersionRecord] = Field(default_factory=list, max_length=200)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        """Normalize one stable Skill code."""

        normalized_value = value.strip().lower().replace(" ", "_")
        if not normalized_value:
            raise ValueError("Skill code cannot be blank.")
        if not _SKILL_CODE_PATTERN.fullmatch(normalized_value):
            raise ValueError(
                "Skill code must use lowercase letters, numbers, underscores or hyphens."
            )

        return normalized_value

    @field_validator("name", "summary", "purpose")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        """Trim text fields and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Skill text fields cannot be blank.")

        return normalized_value

    @field_validator("current_version")
    @classmethod
    def normalize_current_version(cls, value: str) -> str:
        """Reuse the version validation for the current Skill version."""

        return SkillVersionRecord.normalize_version(value)

    @field_validator("applicable_role_codes")
    @classmethod
    def normalize_applicable_role_codes(
        cls,
        value: list[ProjectRoleCode],
    ) -> list[ProjectRoleCode]:
        """Deduplicate applicable role codes while preserving order."""

        return SkillVersionRecord.normalize_applicable_role_codes(value)

    @model_validator(mode="after")
    def validate_consistency(self) -> "SkillDefinition":
        """Keep timestamps and version history aligned."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")

        if self.version_history:
            latest_version = self.version_history[-1]
            if latest_version.version != self.current_version:
                raise ValueError(
                    "Skill version history must end with the current version."
                )

        return self


class SkillRegistrySnapshot(DomainModel):
    """Current skill-registry view returned to API consumers."""

    total_skill_count: int = Field(default=0, ge=0)
    enabled_skill_count: int = Field(default=0, ge=0)
    version_record_count: int = Field(default=0, ge=0)
    skills: list[SkillDefinition] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_counts(self) -> "SkillRegistrySnapshot":
        """Keep summary counts consistent with the registry list."""

        object.__setattr__(self, "generated_at", ensure_utc_datetime(self.generated_at))

        if self.total_skill_count != len(self.skills):
            raise ValueError("total_skill_count must equal the number of skills.")

        actual_enabled_count = sum(1 for skill in self.skills if skill.enabled)
        if self.enabled_skill_count != actual_enabled_count:
            raise ValueError(
                "enabled_skill_count must equal the number of enabled skills."
            )

        actual_version_record_count = sum(len(skill.version_history) for skill in self.skills)
        if self.version_record_count != actual_version_record_count:
            raise ValueError(
                "version_record_count must equal the number of version records."
            )

        return self


class ProjectRoleSkillBinding(DomainModel):
    """Persisted relation between one project role and one concrete Skill version."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    role_code: ProjectRoleCode
    skill_id: UUID
    skill_code: str = Field(min_length=1, max_length=80)
    skill_name: str = Field(min_length=1, max_length=100)
    bound_version: str = Field(min_length=1, max_length=40)
    binding_source: SkillBindingSource = Field(default=SkillBindingSource.MANUAL)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("skill_code")
    @classmethod
    def normalize_skill_code(cls, value: str) -> str:
        """Normalize the denormalized bound Skill code."""

        return SkillDefinition.normalize_code(value)

    @field_validator("skill_name")
    @classmethod
    def normalize_skill_name(cls, value: str) -> str:
        """Trim and validate the denormalized bound Skill name."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Bound Skill name cannot be blank.")

        return normalized_value

    @field_validator("bound_version")
    @classmethod
    def normalize_bound_version(cls, value: str) -> str:
        """Normalize the bound Skill version."""

        return SkillVersionRecord.normalize_version(value)

    @model_validator(mode="after")
    def validate_timestamps(self) -> "ProjectRoleSkillBinding":
        """Keep persisted timestamps UTC-aware and ordered."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")

        return self


class ProjectRoleBoundSkill(DomainModel):
    """Resolved binding item shown in the project skill-binding view."""

    skill_id: UUID
    skill_code: str = Field(min_length=1, max_length=80)
    skill_name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=1_000)
    bound_version: str = Field(min_length=1, max_length=40)
    registry_current_version: str | None = Field(default=None, max_length=40)
    registry_enabled: bool = True
    upgrade_available: bool = False
    applicable_role_codes: list[ProjectRoleCode] = Field(default_factory=list, max_length=12)
    binding_source: SkillBindingSource
    created_at: datetime
    updated_at: datetime

    @field_validator("skill_code")
    @classmethod
    def normalize_skill_code(cls, value: str) -> str:
        return SkillDefinition.normalize_code(value)

    @field_validator("skill_name", "summary", "purpose")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Resolved bound Skill text fields cannot be blank.")

        return normalized_value

    @field_validator("bound_version")
    @classmethod
    def normalize_bound_version(cls, value: str) -> str:
        return SkillVersionRecord.normalize_version(value)

    @field_validator("registry_current_version")
    @classmethod
    def normalize_registry_current_version(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return SkillVersionRecord.normalize_version(value)

    @field_validator("applicable_role_codes")
    @classmethod
    def normalize_applicable_role_codes(
        cls,
        value: list[ProjectRoleCode],
    ) -> list[ProjectRoleCode]:
        return SkillVersionRecord.normalize_applicable_role_codes(value)

    @model_validator(mode="after")
    def validate_timestamps(self) -> "ProjectRoleBoundSkill":
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        return self


class ProjectRoleSkillBindingGroup(DomainModel):
    """One role lane inside the Day13 project binding snapshot."""

    role_code: ProjectRoleCode
    role_name: str = Field(min_length=1, max_length=100)
    role_enabled: bool = True
    default_skill_slots: list[str] = Field(default_factory=list, max_length=12)
    bound_skill_count: int = Field(default=0, ge=0)
    skills: list[ProjectRoleBoundSkill] = Field(default_factory=list)

    @field_validator("role_name")
    @classmethod
    def normalize_role_name(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Role name cannot be blank.")

        return normalized_value

    @field_validator("default_skill_slots")
    @classmethod
    def normalize_default_skill_slots(cls, value: list[str]) -> list[str]:
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
    def validate_counts(self) -> "ProjectRoleSkillBindingGroup":
        if self.bound_skill_count != len(self.skills):
            raise ValueError("bound_skill_count must equal the number of bound skills.")

        return self


class ProjectSkillBindingSnapshot(DomainModel):
    """Project-level skill-binding overview shown on the Day13 UI."""

    project_id: UUID
    project_name: str = Field(min_length=1, max_length=200)
    total_roles: int = Field(default=0, ge=0)
    enabled_roles: int = Field(default=0, ge=0)
    total_bound_skills: int = Field(default=0, ge=0)
    outdated_binding_count: int = Field(default=0, ge=0)
    roles: list[ProjectRoleSkillBindingGroup] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)

    @field_validator("project_name")
    @classmethod
    def normalize_project_name(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Project name cannot be blank.")

        return normalized_value

    @model_validator(mode="after")
    def validate_counts(self) -> "ProjectSkillBindingSnapshot":
        object.__setattr__(self, "generated_at", ensure_utc_datetime(self.generated_at))

        if self.total_roles != len(self.roles):
            raise ValueError("total_roles must equal the number of role groups.")

        actual_enabled_roles = sum(1 for role in self.roles if role.role_enabled)
        if self.enabled_roles != actual_enabled_roles:
            raise ValueError("enabled_roles must equal the number of enabled role groups.")

        actual_bound_skills = sum(len(role.skills) for role in self.roles)
        if self.total_bound_skills != actual_bound_skills:
            raise ValueError(
                "total_bound_skills must equal the number of resolved bound skills."
            )

        actual_outdated_bindings = sum(
            1
            for role in self.roles
            for skill in role.skills
            if skill.upgrade_available
        )
        if self.outdated_binding_count != actual_outdated_bindings:
            raise ValueError(
                "outdated_binding_count must equal the number of upgradeable bindings."
            )

        return self
