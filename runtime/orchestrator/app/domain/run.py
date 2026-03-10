"""Run domain model definitions."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class RunStatus(StrEnum):
    """Status of a single execution attempt."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Run(DomainModel):
    """Minimal persisted execution record."""

    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    status: RunStatus = Field(default=RunStatus.QUEUED)
    model_name: str | None = Field(default=None, max_length=100)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_summary: str | None = Field(default=None, max_length=2_000)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    log_path: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_time_range(self) -> "Run":
        """Ensure persisted timestamps are always UTC-aware."""

        object.__setattr__(self, "started_at", ensure_utc_datetime(self.started_at))
        object.__setattr__(self, "finished_at", ensure_utc_datetime(self.finished_at))
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))

        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("finished_at cannot be earlier than started_at")

        return self
