"""AI summary domain models for run-level generated summaries."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class RunAISummaryType(StrEnum):
    """Supported AI summary scopes stored in the run summary ledger."""

    RUN = "run"
    TASK = "task"
    PROJECT = "project"
    DELIVERABLE = "deliverable"
    APPROVAL = "approval"
    PROJECT_CONFIG = "project_config"
    RUN_LOG = "run_log"


class RunAISummary(DomainModel):
    """One persisted AI summary snapshot for a run."""

    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    project_id: UUID | None = None
    task_id: UUID | None = None
    deliverable_id: UUID | None = None
    summary_type: RunAISummaryType = Field(default=RunAISummaryType.RUN)
    summary_markdown: str = Field(min_length=1, max_length=20_000)
    source_version: str = Field(default="run.summary.v1", min_length=1, max_length=40)
    source_hash: str = Field(min_length=1, max_length=128)
    generated_by_model: str | None = Field(default=None, max_length=100)
    provider_receipt_id: str | None = Field(default=None, max_length=100)
    generated_at: datetime = Field(default_factory=utc_now)
    stale: bool = False

    @field_validator(
        "generated_by_model",
        "provider_receipt_id",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Collapse blank optional text fields into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("summary_markdown", "source_version", "source_hash")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required text fields and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Run AI summary text fields cannot be blank.")

        return normalized_value

    @model_validator(mode="after")
    def validate_generated_at(self) -> "RunAISummary":
        """Normalize timestamps to UTC-aware values."""

        object.__setattr__(self, "generated_at", ensure_utc_datetime(self.generated_at))
        return self
