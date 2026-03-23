"""Domain models for V4 Day07-Day08 change-batch execution preparation."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.change_plan import ChangePlanStatus, ChangePlanTargetFile
from app.domain.deliverable import DeliverableType
from app.domain.repository_verification import (
    RepositoryVerificationTemplateReference,
)
from app.domain.task import TaskPriority, TaskRiskLevel


class ChangeBatchStatus(StrEnum):
    """Stable Day07 change-batch states used before Day08 preflight."""

    PREPARING = "preparing"
    SUPERSEDED = "superseded"


class ChangeBatchRiskCategory(StrEnum):
    """Standardized Day08 preflight risk categories."""

    SENSITIVE_DIRECTORY = "sensitive_directory"
    SENSITIVE_FILE = "sensitive_file"
    DANGEROUS_COMMAND = "dangerous_command"
    WIDE_CHANGE = "wide_change"


class ChangeBatchRiskSeverity(StrEnum):
    """Stable severity levels emitted by the Day08 preflight guard."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeBatchPreflightStatus(StrEnum):
    """Status values for the Day08 execution-preflight result."""

    NOT_STARTED = "not_started"
    READY_FOR_EXECUTION = "ready_for_execution"
    BLOCKED_REQUIRES_CONFIRMATION = "blocked_requires_confirmation"
    MANUAL_CONFIRMED = "manual_confirmed"
    MANUAL_REJECTED = "manual_rejected"


class ChangeBatchManualConfirmationStatus(StrEnum):
    """Manual-confirmation state tracked under one Day08 preflight result."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ChangeBatchManualConfirmationAction(StrEnum):
    """Decision actions accepted by the Day08 manual-confirmation gate."""

    APPROVE = "approve"
    REJECT = "reject"


class ChangeBatchRiskFinding(DomainModel):
    """One standardized Day08 preflight finding attached to a change batch."""

    category: ChangeBatchRiskCategory
    severity: ChangeBatchRiskSeverity
    code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1_000)
    affected_paths: list[str] = Field(default_factory=list, max_length=20)
    related_commands: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("code", "title", "summary")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required finding text and reject blank content."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Change-batch preflight finding text cannot be blank.")

        return normalized_value

    @field_validator("affected_paths", "related_commands")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate finding evidence lists."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items


class ChangeBatchManualConfirmationDecision(DomainModel):
    """One auditable Day08 manual-confirmation decision."""

    action: ChangeBatchManualConfirmationAction
    actor_name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    comment: str | None = Field(default=None, max_length=2_000)
    highlighted_risks: list[str] = Field(default_factory=list, max_length=20)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("actor_name", "summary")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required manual-confirmation text fields."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Manual-confirmation text fields cannot be blank.")

        return normalized_value

    @field_validator("comment")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Trim optional decision comments and collapse blanks into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("highlighted_risks")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate highlighted-risk entries."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    @model_validator(mode="after")
    def validate_decision_state(self) -> "ChangeBatchManualConfirmationDecision":
        """Normalize the decision timestamp into UTC."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        return self


class ChangeBatchPreflight(DomainModel):
    """Structured Day08 preflight result stored on one change batch."""

    status: ChangeBatchPreflightStatus = Field(
        default=ChangeBatchPreflightStatus.NOT_STARTED
    )
    summary: str | None = Field(default=None, max_length=1_200)
    overall_severity: ChangeBatchRiskSeverity | None = None
    blocked: bool = False
    ready_for_execution: bool = False
    findings: list[ChangeBatchRiskFinding] = Field(default_factory=list, max_length=50)
    finding_count: int = Field(default=0, ge=0)
    critical_risk_count: int = Field(default=0, ge=0)
    high_risk_count: int = Field(default=0, ge=0)
    medium_risk_count: int = Field(default=0, ge=0)
    low_risk_count: int = Field(default=0, ge=0)
    scanned_target_file_count: int = Field(default=0, ge=0)
    unique_directory_count: int = Field(default=0, ge=0)
    inspected_command_count: int = Field(default=0, ge=0)
    inspected_commands: list[str] = Field(default_factory=list, max_length=20)
    manual_confirmation_required: bool = False
    manual_confirmation_status: ChangeBatchManualConfirmationStatus = Field(
        default=ChangeBatchManualConfirmationStatus.NOT_REQUIRED
    )
    requested_at: datetime | None = None
    evaluated_at: datetime | None = None
    decided_at: datetime | None = None
    decision_history: list[ChangeBatchManualConfirmationDecision] = Field(
        default_factory=list,
        max_length=20,
    )

    @field_validator("summary")
    @classmethod
    def normalize_optional_summary(cls, value: str | None) -> str | None:
        """Trim optional summary text and collapse blanks into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("inspected_commands")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate preflight command text."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    @model_validator(mode="after")
    def validate_preflight_state(self) -> "ChangeBatchPreflight":
        """Normalize timestamps and align aggregate counters with findings."""

        object.__setattr__(self, "requested_at", ensure_utc_datetime(self.requested_at))
        object.__setattr__(self, "evaluated_at", ensure_utc_datetime(self.evaluated_at))
        object.__setattr__(self, "decided_at", ensure_utc_datetime(self.decided_at))

        findings = list(self.findings)
        severity_counter = {
            ChangeBatchRiskSeverity.CRITICAL: 0,
            ChangeBatchRiskSeverity.HIGH: 0,
            ChangeBatchRiskSeverity.MEDIUM: 0,
            ChangeBatchRiskSeverity.LOW: 0,
        }
        for finding in findings:
            severity_counter[finding.severity] += 1

        object.__setattr__(self, "finding_count", len(findings))
        object.__setattr__(
            self,
            "critical_risk_count",
            severity_counter[ChangeBatchRiskSeverity.CRITICAL],
        )
        object.__setattr__(
            self,
            "high_risk_count",
            severity_counter[ChangeBatchRiskSeverity.HIGH],
        )
        object.__setattr__(
            self,
            "medium_risk_count",
            severity_counter[ChangeBatchRiskSeverity.MEDIUM],
        )
        object.__setattr__(
            self,
            "low_risk_count",
            severity_counter[ChangeBatchRiskSeverity.LOW],
        )
        object.__setattr__(
            self,
            "inspected_command_count",
            len(self.inspected_commands),
        )

        if self.findings:
            severity_order = [
                ChangeBatchRiskSeverity.CRITICAL,
                ChangeBatchRiskSeverity.HIGH,
                ChangeBatchRiskSeverity.MEDIUM,
                ChangeBatchRiskSeverity.LOW,
            ]
            derived_overall_severity = next(
                (
                    severity
                    for severity in severity_order
                    if severity_counter[severity] > 0
                ),
                None,
            )
            object.__setattr__(self, "overall_severity", derived_overall_severity)
        elif self.overall_severity is not None:
            object.__setattr__(self, "overall_severity", self.overall_severity)

        return self


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
    verification_templates: list[RepositoryVerificationTemplateReference] = Field(
        default_factory=list,
        max_length=4,
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

    @field_validator("verification_templates")
    @classmethod
    def normalize_verification_templates(
        cls,
        values: list[RepositoryVerificationTemplateReference],
    ) -> list[RepositoryVerificationTemplateReference]:
        """Deduplicate embedded verification-template references by ID."""

        normalized_items: list[RepositoryVerificationTemplateReference] = []
        seen_ids: set[UUID] = set()

        for value in values:
            if value.id in seen_ids:
                continue

            normalized_items.append(value)
            seen_ids.add(value.id)

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
    preflight: ChangeBatchPreflight = Field(default_factory=ChangeBatchPreflight)
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
