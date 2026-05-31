"""Project-level Project Director agent team configuration.

This stores a confirmed draft's agent-team suggestion as a reviewable project
configuration only. It never creates AgentSession, Worker, Run, Skill binding,
repository binding, or provider calls.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from app.domain._base import DomainModel


class AgentTeamConfigStatus(StrEnum):
    """Lifecycle for a project-level agent team configuration suggestion."""

    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ProjectDirectorAgentTeamMemberConfig(DomainModel):
    """One suggested team member/role persisted for a Project."""

    role_code: str = Field(min_length=1, max_length=100)
    role_name: str = Field(default="", max_length=100)
    responsibility: str = Field(min_length=1, max_length=1000)
    collaboration_notes: list[str] = Field(default_factory=list)
    review_status: str = Field(default="pending_confirmation", max_length=80)


class ProjectDirectorAgentTeamConfig(DomainModel):
    """Project-level pending/confirmed/rejected agent team configuration."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    plan_version_id: UUID
    source_draft_id: str = Field(min_length=1, max_length=120)
    status: AgentTeamConfigStatus = Field(
        default=AgentTeamConfigStatus.PENDING_CONFIRMATION
    )
    agent_team: list[ProjectDirectorAgentTeamMemberConfig] = Field(
        default_factory=list
    )
    warnings: list[str] = Field(default_factory=list)
    review_note: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    confirmed_at: datetime | None = None
    rejected_at: datetime | None = None

