"""Agent-thread timeline and intervention message models for Day11."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class AgentMessageRole(StrEnum):
    """Actor role for one agent-thread message."""

    SYSTEM = "system"
    AGENT = "agent"
    REVIEWER = "reviewer"
    BOSS = "boss"


class AgentMessageType(StrEnum):
    """Day12-consumable message category."""

    TIMELINE = "timeline"
    REVIEW = "review"
    REWORK = "rework"
    INTERVENTION = "intervention"
    NOTE_EVENT = "note_event"


class AgentMessage(DomainModel):
    """One persisted agent-thread message."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    project_id: UUID
    task_id: UUID
    run_id: UUID
    sequence_no: int = Field(ge=1)
    role: AgentMessageRole
    message_type: AgentMessageType
    event_type: str = Field(min_length=1, max_length=80)
    phase: str | None = Field(default=None, max_length=40)
    state_from: str | None = Field(default=None, max_length=40)
    state_to: str | None = Field(default=None, max_length=40)
    intervention_type: str | None = Field(default=None, max_length=80)
    note_event_type: str | None = Field(default=None, max_length=80)
    context_checkpoint_id: str | None = Field(default=None, max_length=120)
    context_rehydrated: bool | None = None
    content_summary: str = Field(min_length=1, max_length=2_000)
    content_detail: str | None = Field(default=None, max_length=4_000)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "event_type",
        "phase",
        "state_from",
        "state_to",
        "intervention_type",
        "note_event_type",
        "context_checkpoint_id",
        "content_summary",
        "content_detail",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        """Trim text fields and collapse optional blank values."""

        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            return None
        return normalized_value

    @model_validator(mode="after")
    def validate_timestamp(self) -> "AgentMessage":
        """Ensure persisted timestamps are UTC-aware."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        return self
