"""Repository change-batch request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas.repository_verification import (
    RepositoryVerificationTemplateReferenceResponse,
)
from app.domain.change_batch import (
    ChangeBatchLinkedDeliverable,
    ChangeBatchPreflight,
    ChangeBatchStatus,
)
from app.domain.change_plan import ChangePlanTargetFile
from app.services.change_batch_service import (
    ChangeBatchDependencyView,
    ChangeBatchDetail,
    ChangeBatchSummary,
    ChangeBatchTargetFileView,
    ChangeBatchTaskView,
    ChangeBatchTimelineEntry,
)


class ChangeBatchCreateRequest(BaseModel):
    """DTO used to create one new Day07 change batch."""

    title: str | None = Field(default=None, max_length=200)
    change_plan_ids: list[UUID] = Field(
        min_length=2,
        max_length=10,
        description="Latest ChangePlan heads selected for this execution-preparation batch.",
    )


class ChangeBatchPreflightRequest(BaseModel):
    """Optional command text inspected by the Day08 execution-preflight guard."""

    candidate_commands: list[str] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "Optional command text inspected by Day08 before any real execution. "
            "Commands are only classified, never executed."
        ),
    )


class ChangeBatchTargetFileResponse(BaseModel):
    """One target file rendered inside a Day07 change-batch task."""

    relative_path: str
    language: str
    file_type: str
    rationale: str | None = None
    match_reasons: list[str]

    @classmethod
    def from_target_file(
        cls,
        target_file: ChangePlanTargetFile,
    ) -> "ChangeBatchTargetFileResponse":
        """Convert one target-file domain model into a Day07 API DTO."""

        return cls(
            relative_path=target_file.relative_path,
            language=target_file.language,
            file_type=target_file.file_type,
            rationale=target_file.rationale,
            match_reasons=list(target_file.match_reasons),
        )


class ChangeBatchLinkedDeliverableResponse(BaseModel):
    """One linked deliverable embedded in a Day07 batch snapshot."""

    deliverable_id: UUID
    title: str
    type: str
    current_version_number: int

    @classmethod
    def from_deliverable(
        cls,
        deliverable: ChangeBatchLinkedDeliverable,
    ) -> "ChangeBatchLinkedDeliverableResponse":
        """Convert one embedded deliverable snapshot into an API DTO."""

        return cls(
            deliverable_id=deliverable.deliverable_id,
            title=deliverable.title,
            type=deliverable.type.value,
            current_version_number=deliverable.current_version_number,
        )


class ChangeBatchDependencyResponse(BaseModel):
    """One task dependency shown inside the Day07 execution board."""

    task_id: UUID
    task_title: str
    in_batch: bool
    missing: bool
    order_index: int | None = None

    @classmethod
    def from_view(
        cls,
        dependency: ChangeBatchDependencyView,
    ) -> "ChangeBatchDependencyResponse":
        """Convert one service-layer dependency view into an API DTO."""

        return cls(
            task_id=dependency.task_id,
            task_title=dependency.task_title,
            in_batch=dependency.in_batch,
            missing=dependency.missing,
            order_index=dependency.order_index,
        )


class ChangeBatchTaskResponse(BaseModel):
    """One ordered task row returned with Day07 change-batch detail."""

    order_index: int
    task_id: UUID
    task_title: str
    task_priority: str
    task_risk_level: str
    change_plan_id: UUID
    change_plan_title: str
    selected_version_number: int
    intent_summary: str
    expected_actions: list[str]
    verification_commands: list[str]
    verification_templates: list[RepositoryVerificationTemplateReferenceResponse]
    related_deliverables: list[ChangeBatchLinkedDeliverableResponse]
    dependencies: list[ChangeBatchDependencyResponse]
    target_files: list[ChangeBatchTargetFileResponse]
    overlap_file_paths: list[str]

    @classmethod
    def from_view(
        cls,
        item: ChangeBatchTaskView,
    ) -> "ChangeBatchTaskResponse":
        """Convert one service-layer task view into an API DTO."""

        return cls(
            order_index=item.order_index,
            task_id=item.task_id,
            task_title=item.task_title,
            task_priority=item.task_priority,
            task_risk_level=item.task_risk_level,
            change_plan_id=item.change_plan_id,
            change_plan_title=item.change_plan_title,
            selected_version_number=item.selected_version_number,
            intent_summary=item.intent_summary,
            expected_actions=list(item.expected_actions),
            verification_commands=list(item.verification_commands),
            verification_templates=[
                RepositoryVerificationTemplateReferenceResponse.from_reference(
                    template
                )
                for template in item.verification_templates
            ],
            related_deliverables=[
                ChangeBatchLinkedDeliverableResponse.from_deliverable(deliverable)
                for deliverable in item.related_deliverables
            ],
            dependencies=[
                ChangeBatchDependencyResponse.from_view(dependency)
                for dependency in item.dependencies
            ],
            target_files=[
                ChangeBatchTargetFileResponse.from_target_file(target_file)
                for target_file in item.target_files
            ],
            overlap_file_paths=list(item.overlap_file_paths),
        )


class ChangeBatchTargetFileAggregateResponse(BaseModel):
    """One repository-level file aggregate returned with Day07 batch detail."""

    relative_path: str
    language: str
    file_type: str
    match_reasons: list[str]
    rationales: list[str]
    task_ids: list[UUID]
    task_titles: list[str]
    change_plan_ids: list[UUID]
    change_plan_titles: list[str]
    overlap_count: int

    @classmethod
    def from_view(
        cls,
        item: ChangeBatchTargetFileView,
    ) -> "ChangeBatchTargetFileAggregateResponse":
        """Convert one aggregated file view into an API DTO."""

        return cls(
            relative_path=item.relative_path,
            language=item.language,
            file_type=item.file_type,
            match_reasons=list(item.match_reasons),
            rationales=list(item.rationales),
            task_ids=list(item.task_ids),
            task_titles=list(item.task_titles),
            change_plan_ids=list(item.change_plan_ids),
            change_plan_titles=list(item.change_plan_titles),
            overlap_count=item.overlap_count,
        )


class ChangeBatchTimelineEntryResponse(BaseModel):
    """One local Day07 timeline entry rendered in the repository board."""

    entry_type: str
    label: str
    summary: str
    occurred_at: datetime

    @classmethod
    def from_entry(
        cls,
        entry: ChangeBatchTimelineEntry,
    ) -> "ChangeBatchTimelineEntryResponse":
        """Convert one service-layer timeline entry into an API DTO."""

        return cls(
            entry_type=entry.entry_type,
            label=entry.label,
            summary=entry.summary,
            occurred_at=entry.occurred_at,
        )


class ChangeBatchSummaryResponse(BaseModel):
    """Project-scoped Day07 change-batch summary returned to the frontend."""

    id: UUID
    project_id: UUID
    repository_workspace_id: UUID | None = None
    status: ChangeBatchStatus
    title: str
    summary: str
    active: bool
    change_plan_count: int
    task_count: int
    target_file_count: int
    overlap_file_count: int
    dependency_count: int
    verification_command_count: int
    preflight: ChangeBatchPreflight = Field(default_factory=ChangeBatchPreflight)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_summary(
        cls,
        item: ChangeBatchSummary,
    ) -> "ChangeBatchSummaryResponse":
        """Convert one Day07 service-layer summary into an API DTO."""

        return cls(
            id=item.change_batch.id,
            project_id=item.change_batch.project_id,
            repository_workspace_id=item.change_batch.repository_workspace_id,
            status=item.change_batch.status,
            title=item.change_batch.title,
            summary=item.change_batch.summary,
            active=item.active,
            change_plan_count=item.change_plan_count,
            task_count=item.task_count,
            target_file_count=item.target_file_count,
            overlap_file_count=item.overlap_file_count,
            dependency_count=item.dependency_count,
            verification_command_count=item.verification_command_count,
            preflight=item.change_batch.preflight,
            created_at=item.change_batch.created_at,
            updated_at=item.change_batch.updated_at,
        )


class ChangeBatchDetailResponse(ChangeBatchSummaryResponse):
    """Full Day07 change-batch detail returned to the repository view."""

    tasks: list[ChangeBatchTaskResponse]
    target_files: list[ChangeBatchTargetFileAggregateResponse]
    overlap_files: list[ChangeBatchTargetFileAggregateResponse]
    timeline: list[ChangeBatchTimelineEntryResponse]

    @classmethod
    def from_detail(
        cls,
        detail: ChangeBatchDetail,
    ) -> "ChangeBatchDetailResponse":
        """Convert one Day07 service-layer detail into an API DTO."""

        summary = detail.summary
        return cls(
            id=summary.change_batch.id,
            project_id=summary.change_batch.project_id,
            repository_workspace_id=summary.change_batch.repository_workspace_id,
            status=summary.change_batch.status,
            title=summary.change_batch.title,
            summary=summary.change_batch.summary,
            active=summary.active,
            change_plan_count=summary.change_plan_count,
            task_count=summary.task_count,
            target_file_count=summary.target_file_count,
            overlap_file_count=summary.overlap_file_count,
            dependency_count=summary.dependency_count,
            verification_command_count=summary.verification_command_count,
            preflight=summary.change_batch.preflight,
            created_at=summary.change_batch.created_at,
            updated_at=summary.change_batch.updated_at,
            tasks=[ChangeBatchTaskResponse.from_view(item) for item in detail.tasks],
            target_files=[
                ChangeBatchTargetFileAggregateResponse.from_view(item)
                for item in detail.target_files
            ],
            overlap_files=[
                ChangeBatchTargetFileAggregateResponse.from_view(item)
                for item in detail.overlap_files
            ],
            timeline=[
                ChangeBatchTimelineEntryResponse.from_entry(item)
                for item in detail.timeline
            ],
        )
