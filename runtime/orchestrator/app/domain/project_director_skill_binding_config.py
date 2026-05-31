"""Project-level Project Director skill binding configuration suggestions.

This persists AI Project Director skill-binding suggestions as review-only project
configuration. Confirming a row never creates ProjectRoleSkillBinding records,
enables Skills, dispatches workers, starts runs, or calls providers.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from app.domain._base import DomainModel


class SkillBindingConfigStatus(StrEnum):
    """Lifecycle for a project-level skill binding configuration suggestion."""

    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ProjectDirectorSkillBindingConfigItem(DomainModel):
    """One suggested Skill-to-role binding persisted for a Project."""

    skill_code: str = Field(default="", max_length=120)
    skill_name: str = Field(default="", max_length=120)
    owner_role_code: str = Field(min_length=1, max_length=100)
    usage: str = Field(min_length=1, max_length=1000)
    activation_stage: str = Field(default="planning", max_length=120)
    binding_mode: str = Field(default="suggested", max_length=120)
    reason: str = Field(default="", max_length=1000)
    review_status: str = Field(default="pending_confirmation", max_length=80)


class ProjectDirectorSkillBindingConfig(DomainModel):
    """Project-level pending/confirmed/rejected Skill binding suggestion config."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    plan_version_id: UUID
    source_draft_id: str = Field(min_length=1, max_length=120)
    status: SkillBindingConfigStatus = Field(
        default=SkillBindingConfigStatus.PENDING_CONFIRMATION
    )
    skill_bindings: list[ProjectDirectorSkillBindingConfigItem] = Field(
        default_factory=list
    )
    warnings: list[str] = Field(default_factory=list)
    review_note: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    confirmed_at: datetime | None = None
    rejected_at: datetime | None = None
