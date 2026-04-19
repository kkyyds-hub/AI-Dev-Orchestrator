"""Agent-thread session domain models for Day11 backend chain."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.project_role import ProjectRoleCode


class AgentSessionStatus(StrEnum):
    """Lifecycle status for one persisted agent-thread session."""

    RUNNING = "running"
    REVIEW_REWORK = "review_rework"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class AgentSessionReviewStatus(StrEnum):
    """Review/rework state snapshot consumed by Day12."""

    NONE = "none"
    REVIEW_REQUIRED = "review_required"
    REWORK_REQUIRED = "rework_required"
    REVIEW_PASSED = "review_passed"


class AgentSessionPhase(StrEnum):
    """Minimal Day11 thread phase used by timeline and intervention contracts."""

    CONTEXT_READY = "context_ready"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    REWORKING = "reworking"
    FINALIZED = "finalized"


class AgentSession(DomainModel):
    """Persisted Day11 agent-thread session."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    task_id: UUID
    run_id: UUID
    status: AgentSessionStatus = Field(default=AgentSessionStatus.RUNNING)
    review_status: AgentSessionReviewStatus = Field(default=AgentSessionReviewStatus.NONE)
    current_phase: AgentSessionPhase = Field(default=AgentSessionPhase.CONTEXT_READY)
    owner_role_code: ProjectRoleCode | None = None
    context_checkpoint_id: str | None = Field(default=None, max_length=120)
    context_rehydrated: bool = False
    latest_intervention_type: str | None = Field(default=None, max_length=80)
    latest_note_event_type: str | None = Field(default=None, max_length=80)
    summary: str | None = Field(default=None, max_length=2_000)
    started_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None

    @field_validator(
        "context_checkpoint_id",
        "latest_intervention_type",
        "latest_note_event_type",
        "summary",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Collapse blank optional text fields into None."""

        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

    @model_validator(mode="after")
    def validate_timestamps(self) -> "AgentSession":
        """Ensure all persisted timestamps are UTC-aware."""

        object.__setattr__(self, "started_at", ensure_utc_datetime(self.started_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))
        object.__setattr__(self, "finished_at", ensure_utc_datetime(self.finished_at))
        return self
