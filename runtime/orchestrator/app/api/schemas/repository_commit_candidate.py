"""Repository commit-candidate request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.commit_candidate import (
    CommitCandidate,
    CommitCandidateLinkedDeliverable,
    CommitCandidateStatus,
    CommitCandidateVerificationSummary,
    CommitCandidateVersion,
)


class CommitCandidateDraftUpsertRequest(BaseModel):
    """Optional Day13 draft overrides used when generating a new candidate revision."""

    message_title: str | None = Field(default=None, max_length=200)
    message_body: str | None = Field(default=None, max_length=4_000)
    impact_scope: list[str] = Field(default_factory=list, max_length=40)
    related_files: list[str] = Field(default_factory=list, max_length=120)
    revision_note: str | None = Field(default=None, max_length=1_000)


class CommitCandidateVerificationSummaryResponse(BaseModel):
    """Verification summary embedded in one commit-candidate revision payload."""

    total_runs: int
    passed_runs: int
    failed_runs: int
    skipped_runs: int
    latest_finished_at: datetime | None = None
    highlights: list[str]

    @classmethod
    def from_summary(
        cls,
        summary: CommitCandidateVerificationSummary,
    ) -> "CommitCandidateVerificationSummaryResponse":
        """Convert one domain verification summary into an API DTO."""

        return cls(
            total_runs=summary.total_runs,
            passed_runs=summary.passed_runs,
            failed_runs=summary.failed_runs,
            skipped_runs=summary.skipped_runs,
            latest_finished_at=summary.latest_finished_at,
            highlights=list(summary.highlights),
        )


class CommitCandidateLinkedDeliverableResponse(BaseModel):
    """One deliverable reference embedded in one commit-candidate revision."""

    deliverable_id: UUID
    title: str
    type: str
    stage: str
    current_version_number: int
    latest_version_summary: str | None = None

    @classmethod
    def from_deliverable(
        cls,
        deliverable: CommitCandidateLinkedDeliverable,
    ) -> "CommitCandidateLinkedDeliverableResponse":
        """Convert one linked deliverable into an API DTO."""

        return cls(
            deliverable_id=deliverable.deliverable_id,
            title=deliverable.title,
            type=deliverable.type.value,
            stage=deliverable.stage.value,
            current_version_number=deliverable.current_version_number,
            latest_version_summary=deliverable.latest_version_summary,
        )


class CommitCandidateVersionResponse(BaseModel):
    """One immutable Day13 commit-candidate revision returned by the API."""

    id: UUID
    commit_candidate_id: UUID
    version_number: int
    message_title: str
    message_body: str | None = None
    impact_scope: list[str]
    related_files: list[str]
    verification_summary: CommitCandidateVerificationSummaryResponse
    related_deliverables: list[CommitCandidateLinkedDeliverableResponse]
    evidence_package_key: str
    evidence_summary: str
    revision_note: str | None = None
    created_at: datetime

    @classmethod
    def from_version(
        cls,
        version: CommitCandidateVersion,
    ) -> "CommitCandidateVersionResponse":
        """Convert one domain revision into an API DTO."""

        return cls(
            id=version.id,
            commit_candidate_id=version.commit_candidate_id,
            version_number=version.version_number,
            message_title=version.message_title,
            message_body=version.message_body,
            impact_scope=list(version.impact_scope),
            related_files=list(version.related_files),
            verification_summary=CommitCandidateVerificationSummaryResponse.from_summary(
                version.verification_summary
            ),
            related_deliverables=[
                CommitCandidateLinkedDeliverableResponse.from_deliverable(item)
                for item in version.related_deliverables
            ],
            evidence_package_key=version.evidence_package_key,
            evidence_summary=version.evidence_summary,
            revision_note=version.revision_note,
            created_at=version.created_at,
        )


class CommitCandidateSummaryResponse(BaseModel):
    """Project-scoped Day13 commit-candidate summary row."""

    id: UUID
    project_id: UUID
    change_batch_id: UUID
    change_batch_title: str
    status: CommitCandidateStatus
    current_version_number: int
    revision_count: int
    related_file_count: int
    deliverable_count: int
    verification_total_runs: int
    verification_passed: bool
    evidence_package_key: str
    created_at: datetime
    updated_at: datetime
    latest_version: CommitCandidateVersionResponse

    @classmethod
    def from_candidate(
        cls,
        candidate: CommitCandidate,
    ) -> "CommitCandidateSummaryResponse":
        """Convert one domain commit-candidate into a summary API DTO."""

        latest_version = candidate.versions[-1]
        return cls(
            id=candidate.id,
            project_id=candidate.project_id,
            change_batch_id=candidate.change_batch_id,
            change_batch_title=candidate.change_batch_title,
            status=candidate.status,
            current_version_number=candidate.current_version_number,
            revision_count=len(candidate.versions),
            related_file_count=len(latest_version.related_files),
            deliverable_count=len(latest_version.related_deliverables),
            verification_total_runs=latest_version.verification_summary.total_runs,
            verification_passed=(
                latest_version.verification_summary.failed_runs == 0
                and latest_version.verification_summary.passed_runs > 0
            ),
            evidence_package_key=latest_version.evidence_package_key,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
            latest_version=CommitCandidateVersionResponse.from_version(latest_version),
        )


class CommitCandidateDetailResponse(CommitCandidateSummaryResponse):
    """Full Day13 commit-candidate detail including revision history."""

    versions: list[CommitCandidateVersionResponse]

    @classmethod
    def from_candidate(
        cls,
        candidate: CommitCandidate,
    ) -> "CommitCandidateDetailResponse":
        """Convert one domain commit-candidate into a full-detail API DTO."""

        summary = CommitCandidateSummaryResponse.from_candidate(candidate)
        return cls(
            **summary.model_dump(),
            versions=[
                CommitCandidateVersionResponse.from_version(item)
                for item in candidate.versions
            ],
        )
