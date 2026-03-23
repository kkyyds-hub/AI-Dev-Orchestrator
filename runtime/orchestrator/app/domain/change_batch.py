"""Domain models for V4 Day07 change-batch execution preparation."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.change_plan import ChangePlanStatus, ChangePlanTargetFile
from app.domain.deliverable import DeliverableType
from app.domain.task import TaskPriority, TaskRiskLevel


class ChangeBatchStatus(StrEnum):
    """Stable Day07 change-batch states used before Day08 preflight."""

    PREPARING = "preparing"
    SUPERSEDED = "superseded"


class ChangeBatchLinkedDeliverable(DomainModel):
    """One deliverable snapshot embedded in a persisted change batch."""

    deliverable_id: UUID
    title: str = Field(min_length=1, max_length=200)
    type: DeliverableType
    current_version_number: int = Field(ge=1)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """Trim the embedded deliverable title and reject blanks."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Change-batch linked deliverable title cannot be blank.")

        return normalized_value


class ChangeBatchPlanSnapshot(DomainModel):
    """One immutable ChangePlan snapshot captured by a Day07 change batch."""

    change_plan_id: UUID
    change_plan_title: str = Field(min_length=1, max_length=200)
    change_plan_status: ChangePlanStatus
    selected_version_id: UUID
    selected_version_number: int = Field(ge=1)
    task_id: UUID
    task_title: str = Field(min_length=1, max_length=200)
    task_priority: TaskPriority
    task_risk_level: TaskRiskLevel
    depends_on_task_ids: list[UUID] = Field(default_factory=list, max_length=20)
    intent_summary: str = Field(min_length=1, max_length=2_000)
    source_summary: str = Field(min_length=1, max_length=1_200)
    focus_terms: list[str] = Field(default_factory=list, max_length=20)
    target_files: list[ChangePlanTargetFile] = Field(
        default_factory=list,
        min_length=1,
        max_length=30,
    )
    expected_actions: list[str] = Field(default_factory=list, min_length=1, max_length=20)
    risk_notes: list[str] = Field(default_factory=list, min_length=1, max_length=20)
    verification_commands: list[str] = Field(
        default_factory=list,
        min_length=1,
        max_length=20,
    )
    related_deliverables: list[ChangeBatchLinkedDeliverable] = Field(
        default_factory=list,
        max_length=10,
    )
    context_pack_generated_at: datetime | None = None
    captured_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "change_plan_title",
        "task_title",
        "intent_summary",
        "source_summary",
    )
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required snapshot text fields."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Change-batch snapshot text fields cannot be blank.")

        return normalized_value

    @field_validator(
        "focus_terms",
        "expected_actions",
        "risk_notes",
        "verification_commands",
    )
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate snapshot string lists."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    @field_validator("depends_on_task_ids")
    @classmethod
    def normalize_dependency_ids(cls, values: list[UUID]) -> list[UUID]:
        """Deduplicate dependency IDs while preserving caller order."""

        normalized_items: list[UUID] = []
        seen_items: set[UUID] = set()

        for value in values:
            if value in seen_items:
                continue

            normalized_items.append(value)
            seen_items.add(value)

        return normalized_items

    @field_validator("target_files")
    @classmethod
    def normalize_target_files(
        cls,
        values: list[ChangePlanTargetFile],
    ) -> list[ChangePlanTargetFile]:
        """Deduplicate target files by relative path."""

        normalized_items: list[ChangePlanTargetFile] = []
        seen_paths: set[str] = set()

        for value in values:
            if value.relative_path in seen_paths:
                continue

            normalized_items.append(value)
            seen_paths.add(value.relative_path)

        return normalized_items

    @field_validator("related_deliverables")
    @classmethod
    def normalize_related_deliverables(
        cls,
        values: list[ChangeBatchLinkedDeliverable],
    ) -> list[ChangeBatchLinkedDeliverable]:
        """Deduplicate embedded deliverables by ID."""

        normalized_items: list[ChangeBatchLinkedDeliverable] = []
        seen_ids: set[UUID] = set()

        for value in values:
            if value.deliverable_id in seen_ids:
                continue

            normalized_items.append(value)
            seen_ids.add(value.deliverable_id)

        return normalized_items

    @model_validator(mode="after")
    def validate_snapshot_state(self) -> "ChangeBatchPlanSnapshot":
        """Normalize all embedded timestamps into UTC-aware values."""

        object.__setattr__(self, "captured_at", ensure_utc_datetime(self.captured_at))
        object.__setattr__(
            self,
            "context_pack_generated_at",
            ensure_utc_datetime(self.context_pack_generated_at),
        )
        return self


class ChangeBatch(DomainModel):
    """One Day07 execution-preparation batch built from multiple ChangePlans."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    repository_workspace_id: UUID | None = None
    status: ChangeBatchStatus = Field(default=ChangeBatchStatus.PREPARING)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1_200)
    plan_snapshots: list[ChangeBatchPlanSnapshot] = Field(
        min_length=2,
        max_length=10,
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("title", "summary")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required batch text and reject blank content."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Change-batch text fields cannot be blank.")

        return normalized_value

    @field_validator("plan_snapshots")
    @classmethod
    def normalize_plan_snapshots(
        cls,
        values: list[ChangeBatchPlanSnapshot],
    ) -> list[ChangeBatchPlanSnapshot]:
        """Deduplicate selected ChangePlan snapshots by ChangePlan ID."""

        normalized_items: list[ChangeBatchPlanSnapshot] = []
        seen_ids: set[UUID] = set()

        for value in values:
            if value.change_plan_id in seen_ids:
                continue

            normalized_items.append(value)
            seen_ids.add(value.change_plan_id)

        return normalized_items

    @model_validator(mode="after")
    def validate_batch_state(self) -> "ChangeBatch":
        """Normalize UTC timestamps and ensure basic temporal consistency."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        if self.updated_at < self.created_at:
            raise ValueError("Change-batch updated_at cannot be earlier than created_at.")

        return self
