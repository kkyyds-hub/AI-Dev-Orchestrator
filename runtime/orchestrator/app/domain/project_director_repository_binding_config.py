"""Project-level Project Director repository binding configuration suggestions.

This persists AI Project Director repository-binding suggestions as review-only
project configuration. Confirming a row never creates RepositoryWorkspace
records, writes repository files, invokes git-commit/apply-local/planning/apply,
dispatches workers, starts runs, or calls providers.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from app.domain._base import DomainModel


class RepositoryBindingConfigStatus(StrEnum):
    """Lifecycle for a project-level repository binding suggestion config."""

    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ProjectDirectorRepositoryBindingConfigItem(DomainModel):
    """One suggested repository binding persisted for a Project."""

    binding_type: str = Field(default="review_only", max_length=120)
    binding_mode: str = Field(default="not_bound", max_length=120)
    target: str = Field(min_length=1, max_length=500)
    branch: str = Field(default="未指定", max_length=200)
    focus_paths: list[str] = Field(default_factory=list)
    usage: str = Field(min_length=1, max_length=1000)
    safety_note: str = Field(min_length=1, max_length=1000)
    review_status: str = Field(default="pending_confirmation", max_length=80)


class ProjectDirectorRepositoryBindingConfig(DomainModel):
    """Project-level pending/confirmed/rejected repository binding suggestion."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    plan_version_id: UUID
    source_draft_id: str = Field(min_length=1, max_length=120)
    status: RepositoryBindingConfigStatus = Field(
        default=RepositoryBindingConfigStatus.PENDING_CONFIRMATION
    )
    repository_bindings: list[ProjectDirectorRepositoryBindingConfigItem] = Field(
        default_factory=list
    )
    warnings: list[str] = Field(default_factory=list)
    review_note: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    confirmed_at: datetime | None = None
    rejected_at: datetime | None = None
