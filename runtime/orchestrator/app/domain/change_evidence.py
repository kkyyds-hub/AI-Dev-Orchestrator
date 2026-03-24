"""Domain models for V4 Day11 code-diff summaries and acceptance evidence packs."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.approval import ApprovalDecisionAction, ApprovalStatus
from app.domain.deliverable import DeliverableType
from app.domain.project import ProjectStage
from app.domain.verification_run import (
    VerificationRunCommandSource,
    VerificationRunFailureCategory,
    VerificationRunStatus,
)


class DiffComparisonMode(StrEnum):
    """Stable comparison modes surfaced by the Day11 repository diff summary."""

    BASELINE_TO_WORKTREE = "baseline_to_worktree"


class DiffFileChangeKind(StrEnum):
    """Stable file-level change kinds used by the Day11 aggregated diff view."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNTRACKED = "untracked"


class ChangeEvidenceSnapshotKind(StrEnum):
    """Snapshot source kinds listed inside one Day11 evidence package."""

    CHANGE_BATCH = "change_batch"
    DELIVERABLE_VERSION = "deliverable_version"
    APPROVAL = "approval"
    VERIFICATION_RUN = "verification_run"


class DiffFileChange(DomainModel):
    """One file-level diff row aggregated for the Day11 repository evidence view."""

    relative_path: str = Field(min_length=1, max_length=2_000)
    change_kind: DiffFileChangeKind
    added_line_count: int = Field(default=0, ge=0)
    deleted_line_count: int = Field(default=0, ge=0)
    changed_line_count: int = Field(default=0, ge=0)
    in_change_batch: bool = False
    in_dirty_workspace: bool = False
    linked_task_ids: list[UUID] = Field(default_factory=list, max_length=20)
    linked_change_plan_ids: list[UUID] = Field(default_factory=list, max_length=20)
    notes: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("relative_path")
    @classmethod
    def normalize_relative_path(cls, value: str) -> str:
        """Normalize one repository-relative path and reject unsafe values."""

        normalized_value = value.replace("\\", "/").strip()
        if not normalized_value:
            raise ValueError("Diff summary relative_path cannot be blank.")

        normalized_path = PurePosixPath(normalized_value)
        if normalized_path.is_absolute() or ".." in normalized_path.parts:
            raise ValueError("Diff summary relative_path must stay inside the repository.")

        return normalized_path.as_posix().lstrip("./")

    @field_validator("linked_task_ids", "linked_change_plan_ids")
    @classmethod
    def deduplicate_uuid_lists(cls, values: list[UUID]) -> list[UUID]:
        """Deduplicate UUID lists while preserving order."""

        normalized_items: list[UUID] = []
        seen_items: set[UUID] = set()

        for value in values:
            if value in seen_items:
                continue

            normalized_items.append(value)
            seen_items.add(value)

        return normalized_items

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, values: list[str]) -> list[str]:
        """Trim, deduplicate and drop blank note text."""

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
    def validate_changed_line_count(self) -> "DiffFileChange":
        """Align the derived changed-line counter with the add/delete totals."""

        object.__setattr__(
            self,
            "changed_line_count",
            self.added_line_count + self.deleted_line_count,
        )
        return self


class DiffSummaryMetrics(DomainModel):
    """Aggregate counters rendered on top of the Day11 repository diff view."""

    changed_file_count: int = Field(default=0, ge=0)
    key_file_count: int = Field(default=0, ge=0)
    added_file_count: int = Field(default=0, ge=0)
    modified_file_count: int = Field(default=0, ge=0)
    deleted_file_count: int = Field(default=0, ge=0)
    untracked_file_count: int = Field(default=0, ge=0)
    total_added_line_count: int = Field(default=0, ge=0)
    total_deleted_line_count: int = Field(default=0, ge=0)


class DiffSummary(DomainModel):
    """One project-scoped Day11 repository diff summary grouped by file path."""

    project_id: UUID
    repository_workspace_id: UUID
    repository_root_path: str = Field(min_length=1, max_length=1_000)
    baseline_label: str = Field(min_length=1, max_length=500)
    target_label: str = Field(min_length=1, max_length=500)
    comparison_mode: DiffComparisonMode = Field(
        default=DiffComparisonMode.BASELINE_TO_WORKTREE
    )
    dirty_workspace: bool = False
    dirty_file_count: int = Field(default=0, ge=0)
    note: str | None = Field(default=None, max_length=1_000)
    generated_at: datetime = Field(default_factory=utc_now)
    metrics: DiffSummaryMetrics = Field(default_factory=DiffSummaryMetrics)
    key_files: list[DiffFileChange] = Field(default_factory=list, max_length=20)
    files: list[DiffFileChange] = Field(default_factory=list, max_length=500)

    @field_validator("repository_root_path", "baseline_label", "target_label")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required diff-summary text fields and reject blanks."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Diff summary text fields cannot be blank.")

        return normalized_value

    @field_validator("note")
    @classmethod
    def normalize_optional_note(cls, value: str | None) -> str | None:
        """Trim optional diff-summary notes and collapse blanks into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @model_validator(mode="after")
    def validate_summary_state(self) -> "DiffSummary":
        """Normalize timestamps, root paths and aggregate counters."""

        object.__setattr__(self, "generated_at", ensure_utc_datetime(self.generated_at))

        repository_root_path = Path(self.repository_root_path)
        if not repository_root_path.is_absolute():
            raise ValueError("Diff summary repository_root_path must be absolute.")

        metrics = DiffSummaryMetrics(
            changed_file_count=len(self.files),
            key_file_count=len(self.key_files),
            added_file_count=sum(
                1 for item in self.files if item.change_kind == DiffFileChangeKind.ADDED
            ),
            modified_file_count=sum(
                1 for item in self.files if item.change_kind == DiffFileChangeKind.MODIFIED
            ),
            deleted_file_count=sum(
                1 for item in self.files if item.change_kind == DiffFileChangeKind.DELETED
            ),
            untracked_file_count=sum(
                1 for item in self.files if item.change_kind == DiffFileChangeKind.UNTRACKED
            ),
            total_added_line_count=sum(item.added_line_count for item in self.files),
            total_deleted_line_count=sum(item.deleted_line_count for item in self.files),
        )
        object.__setattr__(self, "metrics", metrics)

        if self.dirty_file_count < sum(1 for item in self.files if item.in_dirty_workspace):
            raise ValueError(
                "Diff summary dirty_file_count cannot be smaller than dirty diff rows."
            )

        return self


class ChangeEvidencePlanItem(DomainModel):
    """One immutable ChangePlan snapshot referenced by the Day11 evidence package."""

    change_plan_id: UUID
    change_plan_title: str = Field(min_length=1, max_length=200)
    selected_version_number: int = Field(ge=1)
    task_id: UUID
    task_title: str = Field(min_length=1, max_length=200)
    intent_summary: str = Field(min_length=1, max_length=2_000)
    expected_actions: list[str] = Field(default_factory=list, max_length=20)
    risk_notes: list[str] = Field(default_factory=list, max_length=20)
    target_file_paths: list[str] = Field(default_factory=list, max_length=30)
    verification_commands: list[str] = Field(default_factory=list, max_length=20)
    verification_template_names: list[str] = Field(default_factory=list, max_length=10)
    related_deliverable_ids: list[UUID] = Field(default_factory=list, max_length=10)
    related_deliverable_titles: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("change_plan_title", "task_title", "intent_summary")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required plan-context text fields and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Change-evidence plan text fields cannot be blank.")

        return normalized_value

    @field_validator(
        "expected_actions",
        "risk_notes",
        "verification_commands",
        "verification_template_names",
        "related_deliverable_titles",
    )
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        """Trim, deduplicate and drop blank list items."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    @field_validator("target_file_paths")
    @classmethod
    def normalize_target_file_paths(cls, values: list[str]) -> list[str]:
        """Normalize repository-relative file paths referenced by the plan snapshot."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.replace("\\", "/").strip()
            if not normalized_value:
                continue

            normalized_path = PurePosixPath(normalized_value)
            if normalized_path.is_absolute() or ".." in normalized_path.parts:
                raise ValueError(
                    "Change-evidence plan target_file_paths must stay inside the repository."
                )

            final_value = normalized_path.as_posix().lstrip("./")
            if final_value in seen_items:
                continue

            normalized_items.append(final_value)
            seen_items.add(final_value)

        return normalized_items

    @field_validator("related_deliverable_ids")
    @classmethod
    def deduplicate_deliverable_ids(cls, values: list[UUID]) -> list[UUID]:
        """Deduplicate related deliverable IDs while preserving order."""

        normalized_items: list[UUID] = []
        seen_items: set[UUID] = set()

        for value in values:
            if value in seen_items:
                continue

            normalized_items.append(value)
            seen_items.add(value)

        return normalized_items


class ChangeEvidenceVerificationRunItem(DomainModel):
    """One structured verification result embedded inside the Day11 evidence package."""

    verification_run_id: UUID
    change_batch_id: UUID
    change_batch_title: str = Field(min_length=1, max_length=200)
    change_plan_id: UUID
    change_plan_title: str = Field(min_length=1, max_length=200)
    task_title: str | None = Field(default=None, max_length=200)
    verification_template_name: str | None = Field(default=None, max_length=100)
    status: VerificationRunStatus
    failure_category: VerificationRunFailureCategory | None = None
    command_source: VerificationRunCommandSource
    command: str = Field(min_length=1, max_length=2_000)
    output_summary: str = Field(min_length=1, max_length=2_000)
    started_at: datetime
    finished_at: datetime

    @field_validator(
        "change_batch_title",
        "change_plan_title",
        "task_title",
        "verification_template_name",
        "command",
        "output_summary",
    )
    @classmethod
    def normalize_text_fields(cls, value: str | None) -> str | None:
        """Trim text fields and collapse blank optional values into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        return normalized_value

    @model_validator(mode="after")
    def validate_run_timestamps(self) -> "ChangeEvidenceVerificationRunItem":
        """Normalize persisted timestamps to UTC-aware values."""

        object.__setattr__(self, "started_at", ensure_utc_datetime(self.started_at))
        object.__setattr__(self, "finished_at", ensure_utc_datetime(self.finished_at))

        if self.finished_at < self.started_at:
            raise ValueError(
                "Change-evidence verification finished_at cannot be earlier than started_at."
            )

        return self


class ChangeEvidenceVerificationSummary(DomainModel):
    """Aggregated verification counters and sample runs shown in the evidence package."""

    total_runs: int = Field(default=0, ge=0)
    passed_runs: int = Field(default=0, ge=0)
    failed_runs: int = Field(default=0, ge=0)
    skipped_runs: int = Field(default=0, ge=0)
    latest_finished_at: datetime | None = None
    runs: list[ChangeEvidenceVerificationRunItem] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_summary(self) -> "ChangeEvidenceVerificationSummary":
        """Normalize timestamps and align counters with the embedded sample runs."""

        object.__setattr__(
            self,
            "latest_finished_at",
            ensure_utc_datetime(self.latest_finished_at),
        )

        if self.total_runs < len(self.runs):
            raise ValueError(
                "Change-evidence verification total_runs cannot be smaller than sample size."
            )

        return self


class ChangeEvidenceDeliverableReference(DomainModel):
    """One deliverable head referenced by the Day11 evidence package."""

    deliverable_id: UUID
    title: str = Field(min_length=1, max_length=200)
    type: DeliverableType
    stage: ProjectStage
    current_version_number: int = Field(ge=1)
    latest_version_id: UUID | None = None
    latest_version_summary: str | None = Field(default=None, max_length=1_000)
    latest_version_created_at: datetime | None = None
    source_task_id: UUID | None = None
    source_run_id: UUID | None = None
    selected: bool = False

    @field_validator("title", "latest_version_summary")
    @classmethod
    def normalize_text_fields(cls, value: str | None) -> str | None:
        """Trim text fields and reject blank required values."""

        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        return normalized_value

    @model_validator(mode="after")
    def validate_latest_version_timestamp(
        self,
    ) -> "ChangeEvidenceDeliverableReference":
        """Normalize optional version timestamps to UTC-aware values."""

        object.__setattr__(
            self,
            "latest_version_created_at",
            ensure_utc_datetime(self.latest_version_created_at),
        )
        return self


class ChangeEvidenceApprovalReference(DomainModel):
    """One approval-context row embedded inside the Day11 evidence package."""

    approval_id: UUID
    deliverable_id: UUID
    deliverable_title: str = Field(min_length=1, max_length=200)
    deliverable_version_number: int = Field(ge=1)
    status: ApprovalStatus
    request_note: str | None = Field(default=None, max_length=2_000)
    latest_summary: str | None = Field(default=None, max_length=500)
    latest_decision_action: ApprovalDecisionAction | None = None
    latest_decision_summary: str | None = Field(default=None, max_length=500)
    latest_decision_actor_name: str | None = Field(default=None, max_length=100)
    latest_decision_at: datetime | None = None
    requested_changes: list[str] = Field(default_factory=list, max_length=20)
    highlighted_risks: list[str] = Field(default_factory=list, max_length=20)
    requested_at: datetime
    due_at: datetime
    decided_at: datetime | None = None
    selected: bool = False

    @field_validator(
        "deliverable_title",
        "request_note",
        "latest_summary",
        "latest_decision_summary",
        "latest_decision_actor_name",
    )
    @classmethod
    def normalize_text_fields(cls, value: str | None) -> str | None:
        """Trim approval-context text fields and collapse blanks into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        return normalized_value

    @field_validator("requested_changes", "highlighted_risks")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        """Trim, deduplicate and drop blank structured approval context lists."""

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
    def validate_timestamps(self) -> "ChangeEvidenceApprovalReference":
        """Normalize approval timestamps into UTC-aware values."""

        object.__setattr__(self, "requested_at", ensure_utc_datetime(self.requested_at))
        object.__setattr__(self, "due_at", ensure_utc_datetime(self.due_at))
        object.__setattr__(self, "decided_at", ensure_utc_datetime(self.decided_at))
        object.__setattr__(
            self,
            "latest_decision_at",
            ensure_utc_datetime(self.latest_decision_at),
        )

        if self.due_at < self.requested_at:
            raise ValueError("Change-evidence approval due_at cannot be earlier than requested_at.")

        return self


class ChangeEvidenceSnapshot(DomainModel):
    """One comparable snapshot row listed under the Day11 evidence package."""

    snapshot_id: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=500)
    snapshot_kind: ChangeEvidenceSnapshotKind
    source_id: str | None = Field(default=None, max_length=200)
    recorded_at: datetime
    selected: bool = False

    @field_validator("snapshot_id", "label", "summary", "source_id")
    @classmethod
    def normalize_text_fields(cls, value: str | None) -> str | None:
        """Trim snapshot text fields and collapse blank optional values into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        return normalized_value

    @model_validator(mode="after")
    def validate_recorded_at(self) -> "ChangeEvidenceSnapshot":
        """Normalize the snapshot timestamp into UTC."""

        object.__setattr__(self, "recorded_at", ensure_utc_datetime(self.recorded_at))
        return self


class ChangeEvidenceReverseLookup(DomainModel):
    """IDs that allow project, deliverable and approval pages to reverse-resolve one package."""

    project_id: UUID
    change_batch_id: UUID | None = None
    deliverable_ids: list[UUID] = Field(default_factory=list, max_length=20)
    approval_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @field_validator("deliverable_ids", "approval_ids")
    @classmethod
    def deduplicate_uuid_lists(cls, values: list[UUID]) -> list[UUID]:
        """Deduplicate reverse-lookup UUIDs while preserving order."""

        normalized_items: list[UUID] = []
        seen_items: set[UUID] = set()

        for value in values:
            if value in seen_items:
                continue

            normalized_items.append(value)
            seen_items.add(value)

        return normalized_items


class ChangeEvidencePackage(DomainModel):
    """One Day11 acceptance evidence package assembled around one repository change scope."""

    project_id: UUID
    repository_workspace_id: UUID
    repository_root_path: str = Field(min_length=1, max_length=1_000)
    package_key: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1_000)
    selected_change_batch_id: UUID | None = None
    selected_change_batch_title: str | None = Field(default=None, max_length=200)
    selected_deliverable_id: UUID | None = None
    selected_approval_id: UUID | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    diff_summary: DiffSummary
    plan_items: list[ChangeEvidencePlanItem] = Field(default_factory=list, max_length=20)
    verification_summary: ChangeEvidenceVerificationSummary = Field(
        default_factory=ChangeEvidenceVerificationSummary
    )
    deliverables: list[ChangeEvidenceDeliverableReference] = Field(
        default_factory=list,
        max_length=20,
    )
    approvals: list[ChangeEvidenceApprovalReference] = Field(
        default_factory=list,
        max_length=20,
    )
    snapshots: list[ChangeEvidenceSnapshot] = Field(default_factory=list, max_length=30)
    reverse_lookup: ChangeEvidenceReverseLookup

    @field_validator("repository_root_path", "package_key", "summary", "selected_change_batch_title")
    @classmethod
    def normalize_text_fields(cls, value: str | None) -> str | None:
        """Trim package text fields and collapse blank optional values into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        return normalized_value

    @model_validator(mode="after")
    def validate_package_state(self) -> "ChangeEvidencePackage":
        """Normalize timestamps and ensure the stored root path is absolute."""

        object.__setattr__(self, "generated_at", ensure_utc_datetime(self.generated_at))

        repository_root_path = Path(self.repository_root_path)
        if not repository_root_path.is_absolute():
            raise ValueError("Change-evidence repository_root_path must be absolute.")

        return self
