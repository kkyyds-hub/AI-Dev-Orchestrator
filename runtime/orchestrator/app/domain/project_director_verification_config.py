"""Project-level Project Director verification mechanism suggestions.

This persists AI Project Director verification mechanisms as review-only
project configuration. Confirming a row never executes commands, starts runs,
dispatches workers, calls providers, or invokes repository/apply actions.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from app.domain._base import DomainModel


class VerificationConfigStatus(StrEnum):
    """Lifecycle for a project-level verification mechanism suggestion config."""

    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ProjectDirectorVerificationConfigItem(DomainModel):
    """One suggested verification mechanism persisted for a Project."""

    name: str = Field(min_length=1, max_length=200)
    command_or_method: str = Field(min_length=1, max_length=1000)
    purpose: str = Field(default="", max_length=1000)
    evidence_required: str = Field(min_length=1, max_length=1000)
    owner_role_code: str = Field(default="reviewer", max_length=80)
    risk_level: str = Field(default="normal", max_length=40)
    requires_user_confirmation: bool = Field(default=False)
    review_status: str = Field(default="pending_confirmation", max_length=80)


class ProjectDirectorVerificationConfig(DomainModel):
    """Project-level pending/confirmed/rejected verification suggestion."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    plan_version_id: UUID
    source_draft_id: str = Field(min_length=1, max_length=120)
    status: VerificationConfigStatus = Field(
        default=VerificationConfigStatus.PENDING_CONFIRMATION
    )
    verification_mechanisms: list[ProjectDirectorVerificationConfigItem] = Field(
        default_factory=list
    )
    warnings: list[str] = Field(default_factory=list)
    review_note: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    confirmed_at: datetime | None = None
    rejected_at: datetime | None = None
