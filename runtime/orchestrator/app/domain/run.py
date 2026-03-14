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


class RunFailureCategory(StrEnum):
    """Structured failure categories exposed by the Day 14 quality gate."""

    EXECUTION_FAILED = "execution_failed"
    VERIFICATION_FAILED = "verification_failed"
    VERIFICATION_CONFIGURATION_FAILED = "verification_configuration_failed"
    DAILY_BUDGET_EXCEEDED = "daily_budget_exceeded"
    SESSION_BUDGET_EXCEEDED = "session_budget_exceeded"
    RETRY_LIMIT_EXCEEDED = "retry_limit_exceeded"


class RunBudgetPressureLevel(StrEnum):
    """Normalized budget-pressure level used by V2-B routing and guard decisions."""

    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    BLOCKED = "blocked"


class RunBudgetStrategyAction(StrEnum):
    """Suggested action exposed by the V2-B budget strategy."""

    FULL_SPEED = "full_speed"
    CONSERVATIVE = "conservative"
    DEGRADED = "degraded"
    BLOCK = "block"


class RunEventReason(StrEnum):
    """Stable run event reasons published to the console stream."""

    CREATED = "created"
    LOG_PATH_SET = "log_path_set"
    FINISHED = "finished"


class RunRoutingScoreItem(DomainModel):
    """One normalized routing-score contribution item."""

    code: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=100)
    score: float
    detail: str = Field(min_length=1, max_length=500)


class Run(DomainModel):
    """Minimal persisted execution record."""

    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    status: RunStatus = Field(default=RunStatus.QUEUED)
    model_name: str | None = Field(default=None, max_length=100)
    route_reason: str | None = Field(default=None, max_length=2_000)
    routing_score: float | None = Field(default=None)
    routing_score_breakdown: list[RunRoutingScoreItem] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_summary: str | None = Field(default=None, max_length=2_000)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    log_path: str | None = Field(default=None, max_length=500)
    verification_mode: str | None = Field(default=None, max_length=100)
    verification_template: str | None = Field(default=None, max_length=100)
    verification_command: str | None = Field(default=None, max_length=500)
    verification_summary: str | None = Field(default=None, max_length=2_000)
    failure_category: RunFailureCategory | None = None
    quality_gate_passed: bool | None = None
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
