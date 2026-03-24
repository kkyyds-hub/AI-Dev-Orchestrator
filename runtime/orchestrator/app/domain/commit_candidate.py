"""Domain models for V4 Day13 commit-candidate drafts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.deliverable import DeliverableType
from app.domain.project import ProjectStage


class CommitCandidateStatus(StrEnum):
    """Stable Day13 commit-candidate states."""

    DRAFT = "draft"


class CommitCandidateVerificationSummary(DomainModel):
    """Verification aggregate embedded in one commit-candidate revision."""

    total_runs: int = Field(default=0, ge=0)
    passed_runs: int = Field(default=0, ge=0)
    failed_runs: int = Field(default=0, ge=0)
    skipped_runs: int = Field(default=0, ge=0)
    latest_finished_at: datetime | None = None
    highlights: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("highlights")
    @classmethod
    def normalize_highlights(cls, values: list[str]) -> list[str]:
        """Trim, deduplicate and drop blank verification highlights."""

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
    def validate_summary(self) -> "CommitCandidateVerificationSummary":
        """Normalize timestamps and align aggregate counters."""

        object.__setattr__(
            self,
            "latest_finished_at",
            ensure_utc_datetime(self.latest_finished_at),
        )

        classified_total = self.passed_runs + self.failed_runs + self.skipped_runs
        if classified_total > self.total_runs:
            raise ValueError(
                "Commit-candidate verification classified counters cannot exceed total_runs."
            )

        return self


class CommitCandidateLinkedDeliverable(DomainModel):
    """One deliverable reference embedded in one commit-candidate revision."""

    deliverable_id: UUID
    title: str = Field(min_length=1, max_length=200)
    type: DeliverableType
    stage: ProjectStage
    current_version_number: int = Field(ge=1)
    latest_version_summary: str | None = Field(default=None, max_length=1_000)

    @field_validator("title", "latest_version_summary")
    @classmethod
    def normalize_text_fields(cls, value: str | None) -> str | None:
        """Trim text fields and collapse blank optional values into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        return normalized_value


class CommitCandidateVersion(DomainModel):
    """One immutable Day13 commit-candidate draft revision."""

    id: UUID = Field(default_factory=uuid4)
    commit_candidate_id: UUID
    version_number: int = Field(ge=1)
    message_title: str = Field(min_length=1, max_length=200)
    message_body: str | None = Field(default=None, max_length=4_000)
    impact_scope: list[str] = Field(default_factory=list, min_length=1, max_length=40)
    related_files: list[str] = Field(default_factory=list, min_length=1, max_length=120)
    verification_summary: CommitCandidateVerificationSummary
    related_deliverables: list[CommitCandidateLinkedDeliverable] = Field(
        default_factory=list,
        max_length=20,
    )
    evidence_package_key: str = Field(min_length=1, max_length=200)
    evidence_summary: str = Field(min_length=1, max_length=1_200)
    revision_note: str | None = Field(default=None, max_length=1_000)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "message_title",
        "message_body",
        "evidence_package_key",
        "evidence_summary",
        "revision_note",
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

    @field_validator("impact_scope")
    @classmethod
    def normalize_impact_scope(cls, values: list[str]) -> list[str]:
        """Trim, deduplicate and drop blank impact-scope items."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    @field_validator("related_files")
    @classmethod
    def normalize_related_files(cls, values: list[str]) -> list[str]:
        """Normalize repository-relative paths for one revision."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in values:
            normalized_value = value.replace("\\", "/").strip()
            if not normalized_value:
                continue

            normalized_path = PurePosixPath(normalized_value)
            if normalized_path.is_absolute() or ".." in normalized_path.parts:
                raise ValueError("Commit-candidate related_files must stay inside the repository.")

            final_path = normalized_path.as_posix().lstrip("./")
            if not final_path or final_path in seen_items:
                continue

            normalized_items.append(final_path)
            seen_items.add(final_path)

        return normalized_items

    @field_validator("related_deliverables")
    @classmethod
    def deduplicate_related_deliverables(
        cls,
        values: list[CommitCandidateLinkedDeliverable],
    ) -> list[CommitCandidateLinkedDeliverable]:
        """Deduplicate deliverables by ID while preserving order."""

        normalized_items: list[CommitCandidateLinkedDeliverable] = []
        seen_items: set[UUID] = set()

        for value in values:
            if value.deliverable_id in seen_items:
                continue

            normalized_items.append(value)
            seen_items.add(value.deliverable_id)

        return normalized_items

    @model_validator(mode="after")
    def validate_version_state(self) -> "CommitCandidateVersion":
        """Normalize timestamps and enforce required text fields."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))

        if self.message_body is None:
            object.__setattr__(
                self,
                "message_body",
                "本草案仅用于审批审阅，不触发真实 Git 提交或远程放行操作。",
            )

        return self


class CommitCandidate(DomainModel):
    """One Day13 project-scoped commit-candidate draft aggregate."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    change_batch_id: UUID
    change_batch_title: str = Field(min_length=1, max_length=200)
    status: CommitCandidateStatus = Field(default=CommitCandidateStatus.DRAFT)
    current_version_number: int = Field(ge=1)
    versions: list[CommitCandidateVersion] = Field(min_length=1, max_length=50)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("change_batch_title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """Trim candidate title and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Commit-candidate change_batch_title cannot be blank.")

        return normalized_value

    @model_validator(mode="after")
    def validate_candidate_state(self) -> "CommitCandidate":
        """Normalize timestamps and align current-version pointers."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        ordered_versions = sorted(
            self.versions,
            key=lambda item: (item.version_number, item.created_at),
        )
        if not ordered_versions:
            raise ValueError("Commit-candidate must keep at least one revision.")

        seen_numbers: set[int] = set()
        for version in ordered_versions:
            if version.commit_candidate_id != self.id:
                raise ValueError("Commit-candidate revision commit_candidate_id mismatch.")
            if version.version_number in seen_numbers:
                raise ValueError("Commit-candidate revision version_number must be unique.")
            seen_numbers.add(version.version_number)

        latest_version = ordered_versions[-1]
        object.__setattr__(self, "versions", ordered_versions)
        object.__setattr__(self, "current_version_number", latest_version.version_number)

        if self.updated_at < self.created_at:
            raise ValueError("Commit-candidate updated_at cannot be earlier than created_at.")
        if self.updated_at < latest_version.created_at:
            object.__setattr__(self, "updated_at", latest_version.created_at)

        return self
