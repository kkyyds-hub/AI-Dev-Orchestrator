"""AI summary domain models for run-level generated summaries."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class RunAISummaryType(StrEnum):
    """Supported AI summary scopes stored in the summary ledger."""

    RUN = "run"
    TASK = "task"
    PROJECT = "project"
    DELIVERABLE = "deliverable"
    APPROVAL = "approval"
    PROJECT_CONFIG = "project_config"
    RUN_LOG = "run_log"


class RunAISummaryStatus(StrEnum):
    """Lifecycle status for one stored AI summary."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunAISummarySource(StrEnum):
    """Where one summary snapshot came from."""

    AI = "ai"
    RULE_FALLBACK = "rule_fallback"


class RunAISummary(DomainModel):
    """One persisted AI summary snapshot for a run."""

    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    project_id: UUID | None = None
    task_id: UUID | None = None
    deliverable_id: UUID | None = None
    summary_type: RunAISummaryType = Field(default=RunAISummaryType.RUN)
    status: RunAISummaryStatus = Field(default=RunAISummaryStatus.PENDING)
    source: RunAISummarySource = Field(default=RunAISummarySource.RULE_FALLBACK)
    summary_markdown: str = Field(min_length=1, max_length=20_000)
    source_version: str = Field(default="run.summary.v2", min_length=1, max_length=40)
    source_fingerprint: str = Field(min_length=1, max_length=128)
    source_hash: str = Field(min_length=1, max_length=128)
    model_provider: str | None = Field(default=None, max_length=100)
    model_name: str | None = Field(default=None, max_length=100)
    prompt_hash: str = Field(min_length=1, max_length=128)
    provider_receipt_id: str | None = Field(default=None, max_length=100)
    generated_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    error_summary: str | None = Field(default=None, max_length=2_000)
    stale: bool = False

    @field_validator(
        "model_provider",
        "model_name",
        "provider_receipt_id",
        "error_summary",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Collapse blank optional text fields into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator(
        "summary_markdown",
        "source_version",
        "source_fingerprint",
        "source_hash",
        "prompt_hash",
    )
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required text fields and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Run AI summary text fields cannot be blank.")

        return normalized_value

    @model_validator(mode="after")
    def validate_timestamps(self) -> "RunAISummary":
        """Normalize timestamps to UTC-aware values."""

        object.__setattr__(self, "generated_at", ensure_utc_datetime(self.generated_at))
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))
        return self
