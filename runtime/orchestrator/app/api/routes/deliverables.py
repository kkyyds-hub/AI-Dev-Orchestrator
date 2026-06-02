"""Deliverable repository endpoints for V3 Day09."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.approval import ApprovalStatus
from app.domain.change_evidence import ChangeEvidencePackage
from app.domain.deliverable import DeliverableContentFormat, DeliverableType
from app.domain.project import ProjectStage
from app.domain.project_role import ProjectRoleCode
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.deliverable_repository import DeliverableRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.verification_run_repository import VerificationRunRepository
from app.services.deliverable_service import (
    DeliverableDetail,
    DeliverableDiffLine,
    DeliverableService,
    DeliverableSummary,
    DeliverableVersionDiff,
    ProjectDeliverableSnapshot,
    TaskRelatedDeliverable,
)
from app.services.diff_summary_service import (
    DiffSummaryApprovalNotFoundError,
    DiffSummaryChangeBatchNotFoundError,
    DiffSummaryDeliverableNotFoundError,
    DiffSummaryProjectNotFoundError,
    DiffSummaryService,
    DiffSummaryWorkspaceNotFoundError,
)


class DeliverableStatus(StrEnum):
    """Stage 6-A frontend-facing deliverable lifecycle status."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    NEEDS_REWORK = "needs_rework"
    ARCHIVED = "archived"


def _derive_deliverable_status(latest_approval_status: ApprovalStatus | None) -> DeliverableStatus:
    """Map the latest approval state into the Stage 6-A deliverable status."""

    if latest_approval_status is None:
        return DeliverableStatus.DRAFT
    if latest_approval_status == ApprovalStatus.PENDING_APPROVAL:
        return DeliverableStatus.PENDING_REVIEW
    if latest_approval_status == ApprovalStatus.APPROVED:
        return DeliverableStatus.APPROVED
    if latest_approval_status in {
        ApprovalStatus.REJECTED,
        ApprovalStatus.CHANGES_REQUESTED,
    }:
        return DeliverableStatus.NEEDS_REWORK
    return DeliverableStatus.DRAFT


def _latest_approval_status(
    approval_repository: ApprovalRepository,
    deliverable_id: UUID,
    *,
    current_version_number: int | None = None,
) -> ApprovalStatus | None:
    """Return the latest approval status for a deliverable when one exists."""

    latest_record = approval_repository.get_latest_record_by_deliverable_id(deliverable_id)
    if latest_record is None:
        return None
    if (
        current_version_number is not None
        and latest_record.approval.deliverable_version_number != current_version_number
    ):
        return None
    return latest_record.approval.status


def _derive_source_type(version) -> str | None:
    """Derive a conservative Stage 6-A source type from existing version links."""

    if version.source_run_id is not None:
        return "run"
    if version.source_task_id is not None:
        return "task"
    return None


def _derive_source_label(version) -> str | None:
    """Derive a stable source label without introducing new joins or storage."""

    if version.source_run_id is not None:
        return f"Run {version.source_run_id}"
    if version.source_task_id is not None:
        return f"Task {version.source_task_id}"
    return None


@dataclass(slots=True, frozen=True)
class DeliverableEvidenceProjection:
    """Stage 6-A compatibility evidence derived from existing backend records."""

    source_draft_id: str | None = None
    repository_change_id: UUID | None = None
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)


class DeliverableEvidenceProjector:
    """Read-only projector over the existing task/run/change-evidence graph."""

    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        change_batch_repository: ChangeBatchRepository,
        verification_run_repository: VerificationRunRepository,
    ) -> None:
        self.task_repository = task_repository
        self.run_repository = run_repository
        self.change_batch_repository = change_batch_repository
        self.verification_run_repository = verification_run_repository
        self._task_cache: dict[UUID, Any | None] = {}
        self._run_cache: dict[UUID, Any | None] = {}
        self._change_batch_cache: dict[UUID, list[Any]] = {}
        self._verification_run_cache: dict[UUID, list[Any]] = {}

    def project(self, *, deliverable, version) -> DeliverableEvidenceProjection:
        """Derive the Stage 6-A evidence fields for one deliverable version."""

        refs: list[dict[str, Any]] = []
        source_task_id = version.source_task_id
        source_run = self._get_run(version.source_run_id)
        if source_task_id is None and source_run is not None:
            source_task_id = source_run.task_id

        source_task = self._get_task(source_task_id)
        source_draft_id = source_task.source_draft_id if source_task is not None else None

        if source_task is not None:
            refs.append(
                {
                    "kind": "task",
                    "ref": str(source_task.id),
                    "label": source_task.title,
                }
            )
            if source_draft_id:
                refs.append(
                    {
                        "kind": "source_draft",
                        "ref": source_draft_id,
                        "label": "Task source draft",
                    }
                )

        if source_run is not None:
            refs.append(
                {
                    "kind": "run",
                    "ref": str(source_run.id),
                    "label": source_run.result_summary or f"Run {source_run.id}",
                    "status": source_run.status.value,
                }
            )

        change_batch = self._find_relevant_change_batch(
            project_id=deliverable.project_id,
            deliverable_id=deliverable.id,
            source_task_id=source_task_id,
        )
        if change_batch is None:
            return DeliverableEvidenceProjection(
                source_draft_id=source_draft_id,
                evidence_refs=refs,
            )

        refs.append(
            {
                "kind": "change_batch",
                "ref": str(change_batch.id),
                "label": change_batch.title,
                "summary": change_batch.summary,
            }
        )

        relevant_plan_ids: list[UUID] = []
        for snapshot in change_batch.plan_snapshots:
            snapshot_matches_deliverable = any(
                item.deliverable_id == deliverable.id
                for item in snapshot.related_deliverables
            )
            snapshot_matches_task = (
                source_task_id is not None and snapshot.task_id == source_task_id
            )
            if not snapshot_matches_deliverable and not snapshot_matches_task:
                continue

            relevant_plan_ids.append(snapshot.change_plan_id)
            refs.append(
                {
                    "kind": "change_plan",
                    "ref": str(snapshot.change_plan_id),
                    "label": snapshot.change_plan_title,
                    "task_id": str(snapshot.task_id),
                    "selected_version_number": snapshot.selected_version_number,
                }
            )

        for verification_run in self._list_verification_runs(change_batch):
            if (
                relevant_plan_ids
                and verification_run.change_plan_id not in relevant_plan_ids
            ):
                continue
            refs.append(
                {
                    "kind": "verification_run",
                    "ref": str(verification_run.id),
                    "label": verification_run.command,
                    "status": verification_run.status.value,
                    "summary": verification_run.output_summary,
                    "change_plan_id": str(verification_run.change_plan_id),
                }
            )

        return DeliverableEvidenceProjection(
            source_draft_id=source_draft_id,
            repository_change_id=change_batch.id,
            evidence_refs=self._deduplicate_refs(refs),
        )

    def _get_task(self, task_id: UUID | None):
        if task_id is None:
            return None
        if task_id not in self._task_cache:
            self._task_cache[task_id] = self.task_repository.get_by_id(task_id)
        return self._task_cache[task_id]

    def _get_run(self, run_id: UUID | None):
        if run_id is None:
            return None
        if run_id not in self._run_cache:
            self._run_cache[run_id] = self.run_repository.get_by_id(run_id)
        return self._run_cache[run_id]

    def _list_change_batches(self, project_id: UUID) -> list[Any]:
        if project_id not in self._change_batch_cache:
            self._change_batch_cache[project_id] = (
                self.change_batch_repository.list_by_project_id(project_id)
            )
        return self._change_batch_cache[project_id]

    def _list_verification_runs(self, change_batch) -> list[Any]:
        change_batch_id = change_batch.id
        if change_batch_id not in self._verification_run_cache:
            self._verification_run_cache[change_batch_id] = (
                self.verification_run_repository.list_by_project_id(
                    change_batch.project_id,
                    change_batch_id=change_batch_id,
                )
            )
        return self._verification_run_cache[change_batch_id]

    def _find_relevant_change_batch(
        self,
        *,
        project_id: UUID,
        deliverable_id: UUID,
        source_task_id: UUID | None,
    ):
        fallback = None
        for change_batch in self._list_change_batches(project_id):
            for snapshot in change_batch.plan_snapshots:
                if any(
                    item.deliverable_id == deliverable_id
                    for item in snapshot.related_deliverables
                ):
                    return change_batch
                if source_task_id is not None and snapshot.task_id == source_task_id:
                    fallback = fallback or change_batch
        return fallback

    @staticmethod
    def _deduplicate_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_refs: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()
        for ref in refs:
            kind = str(ref.get("kind") or "evidence")
            ref_id = str(ref.get("ref") or "")
            key = (kind, ref_id)
            if key in seen_keys:
                continue
            normalized_refs.append(ref)
            seen_keys.add(key)
        return normalized_refs


class DeliverableVersionSummaryResponse(BaseModel):
    """Compact version payload used by list and related-item responses."""

    id: UUID
    version_number: int
    version_no: int
    author_role_code: ProjectRoleCode
    created_by: str
    summary: str
    content_markdown: str | None = None
    content_format: DeliverableContentFormat
    task_id: UUID | None = None
    run_id: UUID | None = None
    source_draft_id: str | None = None
    repository_change_id: UUID | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    source_type: str | None = None
    source_label: str | None = None
    source_task_id: UUID | None = None
    source_run_id: UUID | None = None
    created_at: datetime

    @classmethod
    def from_version_summary(
        cls,
        summary_version,
        *,
        deliverable=None,
        evidence_projector: DeliverableEvidenceProjector | None = None,
    ) -> "DeliverableVersionSummaryResponse":
        """Convert one domain deliverable version into a compact DTO."""

        evidence = (
            evidence_projector.project(
                deliverable=deliverable,
                version=summary_version,
            )
            if deliverable is not None and evidence_projector is not None
            else DeliverableEvidenceProjection()
        )
        return cls(
            id=summary_version.id,
            version_number=summary_version.version_number,
            version_no=summary_version.version_number,
            author_role_code=summary_version.author_role_code,
            created_by=summary_version.author_role_code.value,
            summary=summary_version.summary,
            content_markdown=getattr(summary_version, "content", None),
            content_format=summary_version.content_format,
            task_id=summary_version.source_task_id,
            run_id=summary_version.source_run_id,
            source_draft_id=evidence.source_draft_id,
            repository_change_id=evidence.repository_change_id,
            evidence_refs=evidence.evidence_refs,
            source_type=_derive_source_type(summary_version),
            source_label=_derive_source_label(summary_version),
            source_task_id=summary_version.source_task_id,
            source_run_id=summary_version.source_run_id,
            created_at=summary_version.created_at,
        )


class DeliverableVersionResponse(DeliverableVersionSummaryResponse):
    """Full immutable snapshot payload returned by the detail endpoint."""

    content: str
    content_markdown: str

    @classmethod
    def from_version(
        cls,
        version,
        *,
        deliverable=None,
        evidence_projector: DeliverableEvidenceProjector | None = None,
    ) -> "DeliverableVersionResponse":
        """Convert one full domain version into its API DTO."""

        evidence = (
            evidence_projector.project(deliverable=deliverable, version=version)
            if deliverable is not None and evidence_projector is not None
            else DeliverableEvidenceProjection()
        )
        return cls(
            id=version.id,
            version_number=version.version_number,
            version_no=version.version_number,
            author_role_code=version.author_role_code,
            created_by=version.author_role_code.value,
            summary=version.summary,
            content=version.content,
            content_markdown=version.content,
            content_format=version.content_format,
            task_id=version.source_task_id,
            run_id=version.source_run_id,
            source_draft_id=evidence.source_draft_id,
            repository_change_id=evidence.repository_change_id,
            evidence_refs=evidence.evidence_refs,
            source_type=_derive_source_type(version),
            source_label=_derive_source_label(version),
            source_task_id=version.source_task_id,
            source_run_id=version.source_run_id,
            created_at=version.created_at,
        )


class DeliverableSummaryResponse(BaseModel):
    """One deliverable card returned by the project repository view."""

    id: UUID
    project_id: UUID
    type: DeliverableType
    title: str
    summary: str
    content_markdown: str | None = None
    status: DeliverableStatus
    stage: ProjectStage
    created_by_role_code: ProjectRoleCode
    created_by: str
    current_version_number: int
    version_no: int
    total_versions: int
    task_id: UUID | None = None
    run_id: UUID | None = None
    source_draft_id: str | None = None
    repository_change_id: UUID | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    source_type: str | None = None
    source_label: str | None = None
    created_at: datetime
    updated_at: datetime
    latest_version: DeliverableVersionSummaryResponse

    @classmethod
    def from_summary(
        cls,
        summary: DeliverableSummary,
        *,
        latest_approval_status: ApprovalStatus | None = None,
        evidence_projector: DeliverableEvidenceProjector | None = None,
    ) -> "DeliverableSummaryResponse":
        """Convert one service-level summary into its API DTO."""

        deliverable = summary.deliverable
        latest_version = summary.latest_version
        evidence = (
            evidence_projector.project(
                deliverable=deliverable,
                version=latest_version,
            )
            if evidence_projector is not None
            else DeliverableEvidenceProjection()
        )
        return cls(
            id=deliverable.id,
            project_id=deliverable.project_id,
            type=deliverable.type,
            title=deliverable.title,
            summary=latest_version.summary,
            content_markdown=latest_version.content,
            status=_derive_deliverable_status(latest_approval_status),
            stage=deliverable.stage,
            created_by_role_code=deliverable.created_by_role_code,
            created_by=deliverable.created_by_role_code.value,
            current_version_number=deliverable.current_version_number,
            version_no=deliverable.current_version_number,
            total_versions=summary.total_versions,
            task_id=latest_version.source_task_id,
            run_id=latest_version.source_run_id,
            source_draft_id=evidence.source_draft_id,
            repository_change_id=evidence.repository_change_id,
            evidence_refs=evidence.evidence_refs,
            source_type=_derive_source_type(latest_version),
            source_label=_derive_source_label(latest_version),
            created_at=deliverable.created_at,
            updated_at=deliverable.updated_at,
            latest_version=DeliverableVersionSummaryResponse.from_version_summary(
                latest_version,
                deliverable=deliverable,
                evidence_projector=evidence_projector,
            ),
        )


class DeliverableDetailResponse(BaseModel):
    """Deliverable detail with the full immutable version history."""

    id: UUID
    project_id: UUID
    type: DeliverableType
    title: str
    summary: str
    content_markdown: str | None = None
    status: DeliverableStatus
    stage: ProjectStage
    created_by_role_code: ProjectRoleCode
    created_by: str
    current_version_number: int
    version_no: int
    total_versions: int
    task_id: UUID | None = None
    run_id: UUID | None = None
    source_draft_id: str | None = None
    repository_change_id: UUID | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    source_type: str | None = None
    source_label: str | None = None
    created_at: datetime
    updated_at: datetime
    versions: list[DeliverableVersionResponse]

    @classmethod
    def from_detail(
        cls,
        detail: DeliverableDetail,
        *,
        latest_approval_status: ApprovalStatus | None = None,
        evidence_projector: DeliverableEvidenceProjector | None = None,
    ) -> "DeliverableDetailResponse":
        """Convert one service detail into an API DTO."""

        deliverable = detail.deliverable
        latest_version = detail.versions[0] if detail.versions else None
        evidence = (
            evidence_projector.project(
                deliverable=deliverable,
                version=latest_version,
            )
            if latest_version is not None and evidence_projector is not None
            else DeliverableEvidenceProjection()
        )
        return cls(
            id=deliverable.id,
            project_id=deliverable.project_id,
            type=deliverable.type,
            title=deliverable.title,
            summary=latest_version.summary if latest_version is not None else "",
            content_markdown=(
                latest_version.content if latest_version is not None else None
            ),
            status=_derive_deliverable_status(latest_approval_status),
            stage=deliverable.stage,
            created_by_role_code=deliverable.created_by_role_code,
            created_by=deliverable.created_by_role_code.value,
            current_version_number=deliverable.current_version_number,
            version_no=deliverable.current_version_number,
            total_versions=len(detail.versions),
            task_id=(
                latest_version.source_task_id if latest_version is not None else None
            ),
            run_id=latest_version.source_run_id if latest_version is not None else None,
            source_draft_id=evidence.source_draft_id,
            repository_change_id=evidence.repository_change_id,
            evidence_refs=evidence.evidence_refs,
            source_type=(
                _derive_source_type(latest_version)
                if latest_version is not None
                else None
            ),
            source_label=(
                _derive_source_label(latest_version)
                if latest_version is not None
                else None
            ),
            created_at=deliverable.created_at,
            updated_at=deliverable.updated_at,
            versions=[
                DeliverableVersionResponse.from_version(
                    version,
                    deliverable=deliverable,
                    evidence_projector=evidence_projector,
                )
                for version in detail.versions
            ],
        )


class ProjectDeliverableSnapshotResponse(BaseModel):
    """Project-scoped deliverable repository view returned to the frontend."""

    project_id: UUID
    total_deliverables: int
    total_versions: int
    generated_at: datetime
    deliverables: list[DeliverableSummaryResponse]

    @classmethod
    def from_snapshot(
        cls,
        snapshot: ProjectDeliverableSnapshot,
        *,
        approval_repository: ApprovalRepository | None = None,
        evidence_projector: DeliverableEvidenceProjector | None = None,
    ) -> "ProjectDeliverableSnapshotResponse":
        """Convert one service snapshot into an API DTO."""

        return cls(
            project_id=snapshot.project_id,
            total_deliverables=snapshot.total_deliverables,
            total_versions=snapshot.total_versions,
            generated_at=snapshot.generated_at,
            deliverables=[
                DeliverableSummaryResponse.from_summary(
                    item,
                    latest_approval_status=(
                        _latest_approval_status(
                            approval_repository,
                            item.deliverable.id,
                            current_version_number=(
                                item.deliverable.current_version_number
                            ),
                        )
                        if approval_repository is not None
                        else None
                    ),
                    evidence_projector=evidence_projector,
                )
                for item in snapshot.deliverables
            ],
        )


class RelatedTaskDeliverableResponse(BaseModel):
    """One deliverable version shown from the task detail reverse lookup."""

    deliverable_id: UUID
    project_id: UUID
    type: DeliverableType
    title: str
    stage: ProjectStage
    current_version_number: int
    matched_version: DeliverableVersionSummaryResponse

    @classmethod
    def from_related_item(
        cls,
        related_item: TaskRelatedDeliverable,
    ) -> "RelatedTaskDeliverableResponse":
        """Convert one service-side related deliverable into an API DTO."""

        return cls(
            deliverable_id=related_item.deliverable.id,
            project_id=related_item.deliverable.project_id,
            type=related_item.deliverable.type,
            title=related_item.deliverable.title,
            stage=related_item.deliverable.stage,
            current_version_number=related_item.deliverable.current_version_number,
            matched_version=DeliverableVersionSummaryResponse.from_version_summary(
                related_item.version,
                deliverable=related_item.deliverable,
            ),
        )


class DeliverableDiffLineResponse(BaseModel):
    """One line-level diff row returned by the Day11 compare endpoint."""

    kind: str
    content: str
    base_line_number: int | None = None
    target_line_number: int | None = None

    @classmethod
    def from_line(cls, line: DeliverableDiffLine) -> "DeliverableDiffLineResponse":
        """Convert one service diff line into an API DTO."""

        return cls(
            kind=line.kind,
            content=line.content,
            base_line_number=line.base_line_number,
            target_line_number=line.target_line_number,
        )


class DeliverableVersionDiffResponse(BaseModel):
    """Minimal version-comparison payload used by the Day11 diff panel."""

    deliverable_id: UUID
    project_id: UUID
    title: str
    type: DeliverableType
    stage: ProjectStage
    base_version: DeliverableVersionResponse
    target_version: DeliverableVersionResponse
    format_changed: bool
    added_line_count: int
    removed_line_count: int
    unchanged_line_count: int
    changed_block_count: int
    diff_lines: list[DeliverableDiffLineResponse]

    @classmethod
    def from_diff(
        cls,
        diff: DeliverableVersionDiff,
    ) -> "DeliverableVersionDiffResponse":
        """Convert one service-level version diff into its API DTO."""

        return cls(
            deliverable_id=diff.deliverable.id,
            project_id=diff.deliverable.project_id,
            title=diff.deliverable.title,
            type=diff.deliverable.type,
            stage=diff.deliverable.stage,
            base_version=DeliverableVersionResponse.from_version(diff.base_version),
            target_version=DeliverableVersionResponse.from_version(diff.target_version),
            format_changed=diff.format_changed,
            added_line_count=diff.added_line_count,
            removed_line_count=diff.removed_line_count,
            unchanged_line_count=diff.unchanged_line_count,
            changed_block_count=diff.changed_block_count,
            diff_lines=[
                DeliverableDiffLineResponse.from_line(line) for line in diff.diff_lines
            ],
        )


class DeliverableCreateRequest(BaseModel):
    """Payload used to create the initial deliverable plus version `v1`."""

    project_id: UUID
    type: DeliverableType
    title: str = Field(min_length=1, max_length=200)
    stage: ProjectStage = ProjectStage.DELIVERY
    created_by_role_code: ProjectRoleCode = ProjectRoleCode.PRODUCT_MANAGER
    created_by: str | None = None
    summary: str = Field(min_length=1, max_length=1_000)
    content: str = Field(default="", max_length=40_000)
    content_markdown: str | None = Field(default=None, max_length=40_000)
    content_format: DeliverableContentFormat = DeliverableContentFormat.MARKDOWN
    version_no: int | None = Field(default=None, ge=1)
    task_id: UUID | None = None
    run_id: UUID | None = None
    source_task_id: UUID | None = None
    source_run_id: UUID | None = None
    source_draft_id: str | None = Field(default=None, max_length=200)
    repository_change_id: UUID | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    source_type: str | None = Field(default=None, max_length=50)
    source_label: str | None = Field(default=None, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def normalize_stage_6a_aliases(cls, data):
        """Accept Stage 6-A field names while keeping the old service contract."""

        if not isinstance(data, dict):
            return data

        normalized_data = dict(data)
        if not normalized_data.get("content") and normalized_data.get("content_markdown"):
            normalized_data["content"] = normalized_data["content_markdown"]
        if normalized_data.get("source_task_id") is None and normalized_data.get("task_id"):
            normalized_data["source_task_id"] = normalized_data["task_id"]
        if normalized_data.get("source_run_id") is None and normalized_data.get("run_id"):
            normalized_data["source_run_id"] = normalized_data["run_id"]
        if (
            normalized_data.get("created_by_role_code") is None
            and normalized_data.get("created_by")
        ):
            normalized_data["created_by_role_code"] = normalized_data["created_by"]
        return normalized_data

    @model_validator(mode="after")
    def validate_content_alias(self) -> "DeliverableCreateRequest":
        """Require persisted content after resolving Stage 6-A aliases."""

        if not self.content.strip():
            raise ValueError("Deliverable content cannot be blank.")
        return self


class DeliverableVersionCreateRequest(BaseModel):
    """Payload used to submit one more immutable deliverable version."""

    author_role_code: ProjectRoleCode
    created_by: str | None = None
    summary: str = Field(min_length=1, max_length=1_000)
    content: str = Field(default="", max_length=40_000)
    content_markdown: str | None = Field(default=None, max_length=40_000)
    content_format: DeliverableContentFormat = DeliverableContentFormat.MARKDOWN
    version_no: int | None = Field(default=None, ge=1)
    task_id: UUID | None = None
    run_id: UUID | None = None
    source_task_id: UUID | None = None
    source_run_id: UUID | None = None
    source_draft_id: str | None = Field(default=None, max_length=200)
    repository_change_id: UUID | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    source_type: str | None = Field(default=None, max_length=50)
    source_label: str | None = Field(default=None, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def normalize_stage_6a_aliases(cls, data):
        """Accept Stage 6-A field names while keeping the old service contract."""

        if not isinstance(data, dict):
            return data

        normalized_data = dict(data)
        if not normalized_data.get("content") and normalized_data.get("content_markdown"):
            normalized_data["content"] = normalized_data["content_markdown"]
        if normalized_data.get("source_task_id") is None and normalized_data.get("task_id"):
            normalized_data["source_task_id"] = normalized_data["task_id"]
        if normalized_data.get("source_run_id") is None and normalized_data.get("run_id"):
            normalized_data["source_run_id"] = normalized_data["run_id"]
        if normalized_data.get("author_role_code") is None and normalized_data.get("created_by"):
            normalized_data["author_role_code"] = normalized_data["created_by"]
        return normalized_data

    @model_validator(mode="after")
    def validate_content_alias(self) -> "DeliverableVersionCreateRequest":
        """Require persisted content after resolving Stage 6-A aliases."""

        if not self.content.strip():
            raise ValueError("Deliverable version content cannot be blank.")
        return self


def get_deliverable_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> DeliverableService:
    """Create the Day09 deliverable-service dependency."""

    return DeliverableService(
        deliverable_repository=DeliverableRepository(session),
        project_repository=ProjectRepository(session),
        task_repository=TaskRepository(session),
        run_repository=RunRepository(session),
    )


def get_diff_summary_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> DiffSummaryService:
    """Create the shared Day11 diff-summary / evidence-package dependency."""

    return DiffSummaryService(
        project_repository=ProjectRepository(session),
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
        change_batch_repository=ChangeBatchRepository(session),
        deliverable_repository=DeliverableRepository(session),
        approval_repository=ApprovalRepository(session),
        verification_run_repository=VerificationRunRepository(session),
    )


def get_approval_repository(
    session: Annotated[Session, Depends(get_db_session)],
) -> ApprovalRepository:
    """Create the approval repository dependency for read-only status projection."""

    return ApprovalRepository(session)


def get_deliverable_evidence_projector(
    session: Annotated[Session, Depends(get_db_session)],
) -> DeliverableEvidenceProjector:
    """Create the read-only Stage 6-A deliverable evidence projector."""

    return DeliverableEvidenceProjector(
        task_repository=TaskRepository(session),
        run_repository=RunRepository(session),
        change_batch_repository=ChangeBatchRepository(session),
        verification_run_repository=VerificationRunRepository(session),
    )


router = APIRouter(prefix="/deliverables", tags=["deliverables"])


@router.post(
    "",
    response_model=DeliverableDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建交付件并生成初始版本快照",
)
def create_deliverable(
    request: DeliverableCreateRequest,
    deliverable_service: Annotated[
        DeliverableService, Depends(get_deliverable_service)
    ],
    evidence_projector: Annotated[
        DeliverableEvidenceProjector,
        Depends(get_deliverable_evidence_projector),
    ],
) -> DeliverableDetailResponse:
    """Create one Day09 deliverable together with its first immutable snapshot."""

    try:
        detail = deliverable_service.create_deliverable(
            project_id=request.project_id,
            type=request.type,
            title=request.title,
            stage=request.stage,
            created_by_role_code=request.created_by_role_code,
            summary=request.summary,
            content=request.content,
            content_format=request.content_format,
            source_task_id=request.source_task_id,
            source_run_id=request.source_run_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return DeliverableDetailResponse.from_detail(
        detail,
        evidence_projector=evidence_projector,
    )


@router.get(
    "",
    response_model=list[DeliverableSummaryResponse],
    summary="List deliverables by project using the Stage 6-A compatible contract",
)
def list_deliverables(
    project_id: UUID,
    deliverable_service: Annotated[
        DeliverableService, Depends(get_deliverable_service)
    ],
    approval_repository: Annotated[
        ApprovalRepository, Depends(get_approval_repository)
    ],
    evidence_projector: Annotated[
        DeliverableEvidenceProjector,
        Depends(get_deliverable_evidence_projector),
    ],
) -> list[DeliverableSummaryResponse]:
    """Return project deliverables as a flat list for Stage 6-A consumers."""

    snapshot = deliverable_service.get_project_deliverable_snapshot(project_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return [
        DeliverableSummaryResponse.from_summary(
            item,
            latest_approval_status=_latest_approval_status(
                approval_repository,
                item.deliverable.id,
                current_version_number=item.deliverable.current_version_number,
            ),
            evidence_projector=evidence_projector,
        )
        for item in snapshot.deliverables
    ]


@router.get(
    "/projects/{project_id}",
    response_model=ProjectDeliverableSnapshotResponse,
    summary="获取项目交付件仓库视图",
)
def get_project_deliverable_snapshot(
    project_id: UUID,
    deliverable_service: Annotated[
        DeliverableService, Depends(get_deliverable_service)
    ],
    approval_repository: Annotated[
        ApprovalRepository, Depends(get_approval_repository)
    ],
    evidence_projector: Annotated[
        DeliverableEvidenceProjector,
        Depends(get_deliverable_evidence_projector),
    ],
) -> ProjectDeliverableSnapshotResponse:
    """Return the deliverable repository view for one project."""

    snapshot = deliverable_service.get_project_deliverable_snapshot(project_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return ProjectDeliverableSnapshotResponse.from_snapshot(
        snapshot,
        approval_repository=approval_repository,
        evidence_projector=evidence_projector,
    )


@router.get(
    "/projects/{project_id}/change-evidence",
    response_model=ChangeEvidencePackage,
    summary="获取项目维度的代码差异摘要与验收证据包",
)
def get_project_change_evidence(
    project_id: UUID,
    diff_summary_service: Annotated[
        DiffSummaryService,
        Depends(get_diff_summary_service),
    ],
    change_batch_id: UUID | None = None,
) -> ChangeEvidencePackage:
    """Return the Day11 acceptance evidence package for one project."""

    try:
        return diff_summary_service.get_project_change_evidence(
            project_id,
            change_batch_id=change_batch_id,
        )
    except (
        DiffSummaryProjectNotFoundError,
        DiffSummaryWorkspaceNotFoundError,
        DiffSummaryChangeBatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/tasks/{task_id}",
    response_model=list[RelatedTaskDeliverableResponse],
    summary="获取任务及其运行记录关联的交付件",
)
def list_task_related_deliverables(
    task_id: UUID,
    deliverable_service: Annotated[
        DeliverableService, Depends(get_deliverable_service)
    ],
) -> list[RelatedTaskDeliverableResponse]:
    """Return deliverable versions linked to one task or its runs."""

    related_items = deliverable_service.list_related_deliverables_by_task(task_id)
    if related_items is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return [
        RelatedTaskDeliverableResponse.from_related_item(item)
        for item in related_items
    ]


@router.get(
    "/approvals/{approval_id}/change-evidence",
    response_model=ChangeEvidencePackage,
    summary="获取审批维度的代码差异摘要与验收证据包",
)
def get_approval_change_evidence(
    approval_id: UUID,
    diff_summary_service: Annotated[
        DiffSummaryService,
        Depends(get_diff_summary_service),
    ],
) -> ChangeEvidencePackage:
    """Return the Day11 evidence package anchored to one approval item."""

    try:
        return diff_summary_service.get_approval_change_evidence(approval_id)
    except (
        DiffSummaryApprovalNotFoundError,
        DiffSummaryWorkspaceNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{deliverable_id}/compare",
    response_model=DeliverableVersionDiffResponse,
    summary="比较同一交付件的两个版本",
)
def compare_deliverable_versions(
    deliverable_id: UUID,
    base_version: int,
    target_version: int,
    deliverable_service: Annotated[
        DeliverableService, Depends(get_deliverable_service)
    ],
) -> DeliverableVersionDiffResponse:
    """Return a minimal diff between two saved deliverable versions."""

    try:
        diff = deliverable_service.compare_deliverable_versions(
            deliverable_id=deliverable_id,
            base_version_number=base_version,
            target_version_number=target_version,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if diff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deliverable not found: {deliverable_id}",
        )

    return DeliverableVersionDiffResponse.from_diff(diff)


@router.get(
    "/{deliverable_id}/change-evidence",
    response_model=ChangeEvidencePackage,
    summary="获取交付件维度的代码差异摘要与验收证据包",
)
def get_deliverable_change_evidence(
    deliverable_id: UUID,
    diff_summary_service: Annotated[
        DiffSummaryService,
        Depends(get_diff_summary_service),
    ],
) -> ChangeEvidencePackage:
    """Return the Day11 evidence package anchored to one deliverable."""

    try:
        return diff_summary_service.get_deliverable_change_evidence(deliverable_id)
    except (
        DiffSummaryDeliverableNotFoundError,
        DiffSummaryWorkspaceNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{deliverable_id}",
    response_model=DeliverableDetailResponse,
    summary="获取交付件详情与版本历史",
)
def get_deliverable_detail(
    deliverable_id: UUID,
    deliverable_service: Annotated[
        DeliverableService, Depends(get_deliverable_service)
    ],
    approval_repository: Annotated[
        ApprovalRepository, Depends(get_approval_repository)
    ],
    evidence_projector: Annotated[
        DeliverableEvidenceProjector,
        Depends(get_deliverable_evidence_projector),
    ],
) -> DeliverableDetailResponse:
    """Return one deliverable plus its immutable version snapshots."""

    detail = deliverable_service.get_deliverable_detail(deliverable_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deliverable not found: {deliverable_id}",
        )

    return DeliverableDetailResponse.from_detail(
        detail,
        latest_approval_status=_latest_approval_status(
            approval_repository,
            deliverable_id,
            current_version_number=detail.deliverable.current_version_number,
        ),
        evidence_projector=evidence_projector,
    )


@router.get(
    "/{deliverable_id}/versions",
    response_model=list[DeliverableVersionResponse],
    summary="List immutable deliverable versions for Stage 6-A consumers",
)
def list_deliverable_versions(
    deliverable_id: UUID,
    deliverable_service: Annotated[
        DeliverableService, Depends(get_deliverable_service)
    ],
    evidence_projector: Annotated[
        DeliverableEvidenceProjector,
        Depends(get_deliverable_evidence_projector),
    ],
) -> list[DeliverableVersionResponse]:
    """Return the ordered immutable version snapshots for one deliverable."""

    detail = deliverable_service.get_deliverable_detail(deliverable_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deliverable not found: {deliverable_id}",
        )

    return [
        DeliverableVersionResponse.from_version(
            version,
            deliverable=detail.deliverable,
            evidence_projector=evidence_projector,
        )
        for version in detail.versions
    ]


@router.post(
    "/{deliverable_id}/versions",
    response_model=DeliverableDetailResponse,
    summary="提交交付件新版本快照",
)
def submit_deliverable_version(
    deliverable_id: UUID,
    request: DeliverableVersionCreateRequest,
    deliverable_service: Annotated[
        DeliverableService, Depends(get_deliverable_service)
    ],
    evidence_projector: Annotated[
        DeliverableEvidenceProjector,
        Depends(get_deliverable_evidence_projector),
    ],
) -> DeliverableDetailResponse:
    """Append one new immutable version snapshot to a deliverable."""

    try:
        detail = deliverable_service.submit_deliverable_version(
            deliverable_id=deliverable_id,
            author_role_code=request.author_role_code,
            summary=request.summary,
            content=request.content,
            content_format=request.content_format,
            source_task_id=request.source_task_id,
            source_run_id=request.source_run_id,
        )
    except ValueError as exc:
        message = str(exc)
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if message.startswith("Deliverable not found:")
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=message,
        ) from exc

    return DeliverableDetailResponse.from_detail(
        detail,
        evidence_projector=evidence_projector,
    )
