"""AI Project Director session-scoped conversational message model."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class ProjectDirectorMessageRole(StrEnum):
    """Actor role for one Project Director conversation message."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ProjectDirectorMessageSource(StrEnum):
    """Source of a Project Director conversation message."""

    AI = "ai"
    RULE_FALLBACK = "rule_fallback"
    SYSTEM = "system"


class ProjectDirectorMessageRiskLevel(StrEnum):
    """Suggested-action risk level attached to an assistant reply."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProjectDirectorMessage(DomainModel):
    """One persisted message in a Project Director session conversation."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    role: ProjectDirectorMessageRole
    content: str = Field(min_length=1, max_length=10_000)
    sequence_no: int = Field(ge=1)

    intent: str | None = Field(default=None, max_length=80)
    related_plan_version_id: UUID | None = None
    related_project_id: UUID | None = None
    related_task_id: UUID | None = None

    source: ProjectDirectorMessageSource = ProjectDirectorMessageSource.SYSTEM
    source_detail: str = Field(default="", max_length=300)
    suggested_actions: list[dict] = Field(default_factory=list)
    requires_confirmation: bool = False
    risk_level: ProjectDirectorMessageRiskLevel | None = None
    forbidden_actions_detected: list[str] = Field(default_factory=list)
    token_count: int | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("content", "intent", "source_detail", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_timestamp(self) -> "ProjectDirectorMessage":
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        return self
