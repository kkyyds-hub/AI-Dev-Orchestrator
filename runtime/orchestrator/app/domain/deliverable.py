"""Deliverable domain models introduced for V3 Day09."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.project import ProjectStage
from app.domain.project_role import ProjectRoleCode


class DeliverableType(StrEnum):
    """Stable deliverable types tracked by the project artifact repository."""

    PRD = "prd"
    DESIGN = "design"
    TASK_BREAKDOWN = "task_breakdown"
    CODE_PLAN = "code_plan"
    ACCEPTANCE_CONCLUSION = "acceptance_conclusion"
    STAGE_ARTIFACT = "stage_artifact"


class DeliverableContentFormat(StrEnum):
    """Stored snapshot format used by one deliverable version."""

    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"
    JSON = "json"
    LINK = "link"


class Deliverable(DomainModel):
    """One durable project artifact tracked across multiple submitted versions."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    type: DeliverableType
    title: str = Field(min_length=1, max_length=200)
    stage: ProjectStage
    created_by_role_code: ProjectRoleCode
    current_version_number: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """Trim the deliverable title and reject blank text."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Deliverable title cannot be blank.")

        return normalized_value

    @model_validator(mode="after")
    def validate_timestamps(self) -> "Deliverable":
        """Normalize persisted timestamps to UTC-aware values."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        if self.updated_at < self.created_at:
            raise ValueError("Deliverable updated_at cannot be earlier than created_at.")

        return self


class DeliverableVersion(DomainModel):
    """Immutable snapshot submitted under one deliverable."""

    id: UUID = Field(default_factory=uuid4)
    deliverable_id: UUID
    version_number: int = Field(ge=1)
    author_role_code: ProjectRoleCode
    summary: str = Field(min_length=1, max_length=1_000)
    content: str = Field(min_length=1, max_length=40_000)
    content_format: DeliverableContentFormat = Field(
        default=DeliverableContentFormat.MARKDOWN
    )
    source_task_id: UUID | None = None
    source_run_id: UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("summary", "content")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        """Trim text snapshots while keeping their full content."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Deliverable version text fields cannot be blank.")

        return normalized_value

    @model_validator(mode="after")
    def validate_created_at(self) -> "DeliverableVersion":
        """Normalize persisted timestamps to UTC-aware values."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        return self
