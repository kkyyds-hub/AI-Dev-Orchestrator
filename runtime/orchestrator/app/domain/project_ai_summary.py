"""Project-level persisted AI summary snapshots."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.run_ai_summary import RunAISummarySource, RunAISummaryStatus


class ProjectAISummary(DomainModel):
    """One persisted project summary snapshot.

    Stage 3 intentionally uses a local rule-fallback generator only.  The
    model/source fields are retained so the UI can expose provenance and future
    provider-generated summaries can share the same readback contract.
    """

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    status: RunAISummaryStatus = Field(default=RunAISummaryStatus.PENDING)
    source: RunAISummarySource = Field(default=RunAISummarySource.RULE_FALLBACK)
    summary_markdown: str = Field(min_length=1, max_length=20_000)
    source_version: str = Field(default="project.summary.v1", min_length=1, max_length=40)
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
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator(
        "summary_markdown",
        "source_version",
        "source_fingerprint",
        "source_hash",
        "prompt_hash",
    )
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project AI summary text fields cannot be blank.")
        return normalized

    @model_validator(mode="after")
    def validate_timestamps(self) -> "ProjectAISummary":
        object.__setattr__(self, "generated_at", ensure_utc_datetime(self.generated_at))
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))
        return self
