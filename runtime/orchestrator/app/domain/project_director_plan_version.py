"""AI Project Director Plan Version domain model.

BCG-02 Phase1: plan draft → pending_confirmation → confirmed.
Deterministic generation only — no AI, no Provider, no task creation.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from app.domain._base import DomainModel


class PlanVersionStatus(StrEnum):
    """Plan version lifecycle."""

    DRAFT = "draft"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class PlanPhase(DomainModel):
    """A single phase within a plan version."""

    sequence: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=1, max_length=1000)
    task_count_hint: int = Field(default=1, ge=1)


class ProposedTask(DomainModel):
    """A proposed task within a plan version — NOT a real task in the queue."""

    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2000)
    suggested_role_code: str = Field(default="developer", max_length=80)
    priority_hint: str = Field(default="normal", max_length=40)


class ProjectDirectorPlanVersion(DomainModel):
    """A plan version generated from a confirmed Project Director session.

    Not a real planning/apply output — purely a reviewable draft.
    Does NOT create tasks, dispatch workers, or write repositories.
    """

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    project_id: UUID | None = None
    version_no: int = Field(ge=1)
    status: PlanVersionStatus = Field(default=PlanVersionStatus.DRAFT)
    plan_summary: str = Field(default="", max_length=5000)
    phases: list[PlanPhase] = Field(default_factory=list)
    proposed_tasks: list[ProposedTask] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    confirmed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
