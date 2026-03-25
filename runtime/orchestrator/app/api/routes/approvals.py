"""Boss approval endpoints introduced for V3 Day10."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain._base import utc_now
from app.domain.approval import ApprovalDecisionAction, ApprovalStatus
from app.domain.change_batch import (
    ChangeBatchManualConfirmationAction,
    ChangeBatchPreflight,
    ChangeBatchPreflightStatus,
)
from app.domain.deliverable import DeliverableType
from app.domain.project import ProjectStage
from app.domain.project_role import ProjectRoleCode
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.change_plan_repository import ChangePlanRepository
from app.repositories.commit_candidate_repository import CommitCandidateRepository
from app.repositories.deliverable_repository import DeliverableRepository
from app.repositories.failure_review_repository import FailureReviewRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_snapshot_repository import (
    RepositorySnapshotRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.task_repository import TaskRepository
from app.repositories.verification_run_repository import VerificationRunRepository
from app.services.approval_service import (
    ApprovalDetail,
    ApprovalHistory,
    ApprovalHistoryStep,
    ApprovalQueueItem,
    ApprovalReworkCycle,
    ApprovalService,
    ProjectApprovalInbox,
)
from app.services.change_batch_service import (
    ChangeBatchDetail,
    ChangeBatchNotFoundError,
    ChangeBatchProjectNotFoundError,
    ChangeBatchSummary,
    ChangeBatchService,
)
from app.services.change_risk_guard_service import (
    ChangeRiskGuardBatchNotFoundError,
    ChangeRiskGuardManualConfirmationError,
    ChangeRiskGuardPreflightMissingError,
    ChangeRiskGuardProjectNotFoundError,
    ChangeRiskGuardService,
)
from app.services.change_rework_service import (
    ChangeReworkChainStep,
    ChangeReworkItem,
    ChangeReworkService,
    ProjectChangeReworkSnapshot,
    ProjectChangeReworkSummary,
)
from app.services.decision_replay_service import (
    DecisionReplayService,
    ProjectFailureRetrospectiveItem,
)
from app.services.diff_summary_service import DiffSummaryService
from app.services.failure_review_service import FailureReviewCluster, FailureReviewService
from app.services.repository_release_gate_service import (
    ProjectRepositoryReleaseGateInbox,
    RepositoryReleaseChecklistItem,
    RepositoryReleaseChecklistItemStatus,
    RepositoryReleaseGate,
    RepositoryReleaseGateActionValidationError,
    RepositoryReleaseGateBlockedError,
    RepositoryReleaseGateChangeBatchNotFoundError,
    RepositoryReleaseGateDecision,
    RepositoryReleaseGateProjectNotFoundError,
    RepositoryReleaseGateService,
    RepositoryReleaseGateStatus,
)
from app.services.run_logging_service import RunLoggingService


class ApprovalDecisionSummaryResponse(BaseModel):
    """Compact latest-decision payload used by approval list rows."""

    id: UUID
    action: ApprovalDecisionAction
    actor_name: str
    summary: str
    created_at: datetime

    @classmethod
    def from_decision(cls, decision) -> "ApprovalDecisionSummaryResponse":
        """Convert one domain approval decision into a compact API DTO."""

        return cls(
            id=decision.id,
            action=decision.action,
            actor_name=decision.actor_name,
            summary=decision.summary,
            created_at=decision.created_at,
        )


class ApprovalDecisionResponse(ApprovalDecisionSummaryResponse):
    """Full structured decision payload used by the replay drawer."""

    comment: str | None = None
    highlighted_risks: list[str]
    requested_changes: list[str]

    @classmethod
    def from_decision(cls, decision) -> "ApprovalDecisionResponse":
        """Convert one full approval decision into an API DTO."""

        return cls(
            id=decision.id,
            action=decision.action,
            actor_name=decision.actor_name,
            summary=decision.summary,
            comment=decision.comment,
            highlighted_risks=list(decision.highlighted_risks),
            requested_changes=list(decision.requested_changes),
            created_at=decision.created_at,
        )


class ApprovalSummaryResponse(BaseModel):
    """One approval request row returned to the Day10 inbox page."""

    id: UUID
    project_id: UUID
    deliverable_id: UUID
    deliverable_version_id: UUID | None = None
    deliverable_title: str
    deliverable_type: DeliverableType
    deliverable_stage: ProjectStage
    deliverable_version_number: int
    requester_role_code: ProjectRoleCode
    request_note: str | None = None
    status: ApprovalStatus
    requested_at: datetime
    due_at: datetime
    decided_at: datetime | None = None
    latest_summary: str | None = None
    overdue: bool
    latest_decision: ApprovalDecisionSummaryResponse | None = None

    @classmethod
    def from_queue_item(cls, item: ApprovalQueueItem) -> "ApprovalSummaryResponse":
        """Convert one service-level queue row into its API DTO."""

        approval = item.approval
        return cls(
            id=approval.id,
            project_id=approval.project_id,
            deliverable_id=approval.deliverable_id,
            deliverable_version_id=approval.deliverable_version_id,
            deliverable_title=approval.deliverable_title,
            deliverable_type=approval.deliverable_type,
            deliverable_stage=approval.deliverable_stage,
            deliverable_version_number=approval.deliverable_version_number,
            requester_role_code=approval.requester_role_code,
            request_note=approval.request_note,
            status=approval.status,
            requested_at=approval.requested_at,
            due_at=approval.due_at,
            decided_at=approval.decided_at,
            latest_summary=approval.latest_summary,
            overdue=item.overdue,
            latest_decision=(
                ApprovalDecisionSummaryResponse.from_decision(item.latest_decision)
                if item.latest_decision is not None
                else None
            ),
        )


class ApprovalDetailResponse(ApprovalSummaryResponse):
    """One approval request with its structured replay history."""

    decisions: list[ApprovalDecisionResponse]

    @classmethod
    def from_detail(cls, detail: ApprovalDetail) -> "ApprovalDetailResponse":
        """Convert one approval detail into its API DTO."""

        approval = detail.approval
        latest_decision = detail.decisions[-1] if detail.decisions else None
        return cls(
            id=approval.id,
            project_id=approval.project_id,
            deliverable_id=approval.deliverable_id,
            deliverable_version_id=approval.deliverable_version_id,
            deliverable_title=approval.deliverable_title,
            deliverable_type=approval.deliverable_type,
            deliverable_stage=approval.deliverable_stage,
            deliverable_version_number=approval.deliverable_version_number,
            requester_role_code=approval.requester_role_code,
            request_note=approval.request_note,
            status=approval.status,
            requested_at=approval.requested_at,
            due_at=approval.due_at,
            decided_at=approval.decided_at,
            latest_summary=approval.latest_summary,
            overdue=detail.overdue,
            latest_decision=(
                ApprovalDecisionSummaryResponse.from_decision(latest_decision)
                if latest_decision is not None
                else None
            ),
            decisions=[
                ApprovalDecisionResponse.from_decision(decision)
                for decision in detail.decisions
            ],
        )


class ProjectApprovalInboxResponse(BaseModel):
    """Project-scoped approval queue payload returned by `/approvals/projects/{id}`."""

    project_id: UUID
    total_requests: int
    pending_requests: int
    overdue_requests: int
    completed_requests: int
    generated_at: datetime
    approvals: list[ApprovalSummaryResponse]

    @classmethod
    def from_inbox(
        cls,
        inbox: ProjectApprovalInbox,
    ) -> "ProjectApprovalInboxResponse":
        """Convert one service-level inbox payload into its API DTO."""

        return cls(
            project_id=inbox.project_id,
            total_requests=inbox.total_requests,
            pending_requests=inbox.pending_requests,
            overdue_requests=inbox.overdue_requests,
            completed_requests=inbox.completed_requests,
            generated_at=inbox.generated_at,
            approvals=[
                ApprovalSummaryResponse.from_queue_item(item) for item in inbox.approvals
            ],
        )


class RepositoryPreflightApprovalSummaryResponse(BaseModel):
    """One Day08 repository-preflight item shown in the approvals area."""

    change_batch_id: UUID
    project_id: UUID
    title: str
    summary: str
    task_count: int
    target_file_count: int
    overlap_file_count: int
    preflight: ChangeBatchPreflight = Field(default_factory=ChangeBatchPreflight)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_change_batch_summary(
        cls,
        item: ChangeBatchSummary,
    ) -> "RepositoryPreflightApprovalSummaryResponse":
        """Convert one change-batch summary into its Day08 approval-panel DTO."""

        return cls(
            change_batch_id=item.change_batch.id,
            project_id=item.change_batch.project_id,
            title=item.change_batch.title,
            summary=item.change_batch.summary,
            task_count=item.task_count,
            target_file_count=item.target_file_count,
            overlap_file_count=item.overlap_file_count,
            preflight=item.change_batch.preflight,
            created_at=item.change_batch.created_at,
            updated_at=item.change_batch.updated_at,
        )


class ProjectRepositoryPreflightInboxResponse(BaseModel):
    """Project-scoped repository-preflight queue returned by Day08."""

    project_id: UUID
    total_batches: int
    pending_confirmations: int
    ready_batches: int
    rejected_batches: int
    generated_at: datetime
    items: list[RepositoryPreflightApprovalSummaryResponse]


class RepositoryPreflightApprovalDetailResponse(BaseModel):
    """One detailed Day08 repository-preflight record used by the approvals panel."""

    change_batch_id: UUID
    project_id: UUID
    title: str
    summary: str
    task_titles: list[str]
    target_files: list[str]
    overlap_files: list[str]
    preflight: ChangeBatchPreflight = Field(default_factory=ChangeBatchPreflight)
    timeline: list[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_change_batch_detail(
        cls,
        detail: ChangeBatchDetail,
    ) -> "RepositoryPreflightApprovalDetailResponse":
        """Convert one change-batch detail into a Day08 approval-panel DTO."""

        return cls(
            change_batch_id=detail.summary.change_batch.id,
            project_id=detail.summary.change_batch.project_id,
            title=detail.summary.change_batch.title,
            summary=detail.summary.change_batch.summary,
            task_titles=[item.task_title for item in detail.tasks],
            target_files=[item.relative_path for item in detail.target_files],
            overlap_files=[item.relative_path for item in detail.overlap_files],
            preflight=detail.summary.change_batch.preflight,
            timeline=[item.label for item in detail.timeline],
            created_at=detail.summary.change_batch.created_at,
            updated_at=detail.summary.change_batch.updated_at,
        )


class ApprovalHistoryStepResponse(BaseModel):
    """One replayable approval / redo step returned by the Day12 history API."""

    id: str
    event_kind: str
    occurred_at: datetime
    deliverable_version_number: int
    approval_id: UUID | None = None
    decision_id: UUID | None = None
    approval_status: ApprovalStatus | None = None
    decision_action: ApprovalDecisionAction | None = None
    actor_name: str | None = None
    requester_role_code: ProjectRoleCode | None = None
    author_role_code: ProjectRoleCode | None = None
    summary: str
    comment: str | None = None
    request_note: str | None = None
    requested_changes: list[str]
    highlighted_risks: list[str]
    is_rework: bool

    @classmethod
    def from_step(cls, step: ApprovalHistoryStep) -> "ApprovalHistoryStepResponse":
        """Convert one service-level history step into an API DTO."""

        return cls(
            id=step.id,
            event_kind=step.event_kind,
            occurred_at=step.occurred_at,
            deliverable_version_number=step.deliverable_version_number,
            approval_id=step.approval_id,
            decision_id=step.decision_id,
            approval_status=step.approval_status,
            decision_action=step.decision_action,
            actor_name=step.actor_name,
            requester_role_code=step.requester_role_code,
            author_role_code=step.author_role_code,
            summary=step.summary,
            comment=step.comment,
            request_note=step.request_note,
            requested_changes=list(step.requested_changes),
            highlighted_risks=list(step.highlighted_risks),
            is_rework=step.is_rework,
        )


class ApprovalHistoryResponse(BaseModel):
    """Deliverable-scoped approval / redo history returned by Day12."""

    project_id: UUID
    deliverable_id: UUID
    deliverable_title: str
    deliverable_stage: ProjectStage
    current_version_number: int
    latest_approval_id: UUID | None = None
    latest_approval_status: ApprovalStatus | None = None
    rework_status: str
    total_requests: int
    negative_decision_count: int
    rework_round_count: int
    steps: list[ApprovalHistoryStepResponse]

    @classmethod
    def from_history(cls, history: ApprovalHistory) -> "ApprovalHistoryResponse":
        """Convert one service-level approval history into its API DTO."""

        return cls(
            project_id=history.project_id,
            deliverable_id=history.deliverable_id,
            deliverable_title=history.deliverable_title,
            deliverable_stage=history.deliverable_stage,
            current_version_number=history.current_version_number,
            latest_approval_id=history.latest_approval_id,
            latest_approval_status=history.latest_approval_status,
            rework_status=history.rework_status,
            total_requests=history.total_requests,
            negative_decision_count=history.negative_decision_count,
            rework_round_count=history.rework_round_count,
            steps=[
                ApprovalHistoryStepResponse.from_step(step) for step in history.steps
            ],
        )


class ProjectRetrospectiveSummaryResponse(BaseModel):
    """Top-level counters shown at the top of the Day12 project retrospective."""

    total_approval_requests: int
    negative_approval_cycles: int
    open_rework_cycles: int
    total_failure_reviews: int
    failure_clusters: int


class ProjectRetrospectiveApprovalCycleResponse(BaseModel):
    """One negative approval cycle summarized inside the project retrospective."""

    cycle_id: str
    deliverable_id: UUID
    deliverable_title: str
    deliverable_stage: ProjectStage
    approval_id: UUID
    deliverable_version_number: int
    current_version_number: int
    decided_at: datetime
    decision_action: ApprovalDecisionAction
    summary: str
    comment: str | None = None
    requested_changes: list[str]
    highlighted_risks: list[str]
    status: str
    latest_approval_id: UUID | None = None
    latest_approval_status: ApprovalStatus | None = None
    resubmitted_version_number: int | None = None
    resubmitted_at: datetime | None = None

    @classmethod
    def from_cycle(
        cls,
        cycle: ApprovalReworkCycle,
    ) -> "ProjectRetrospectiveApprovalCycleResponse":
        """Convert one approval redo cycle into an API DTO."""

        return cls(
            cycle_id=cycle.cycle_id,
            deliverable_id=cycle.deliverable_id,
            deliverable_title=cycle.deliverable_title,
            deliverable_stage=cycle.deliverable_stage,
            approval_id=cycle.approval_id,
            deliverable_version_number=cycle.deliverable_version_number,
            current_version_number=cycle.current_version_number,
            decided_at=cycle.decided_at,
            decision_action=cycle.decision_action,
            summary=cycle.summary,
            comment=cycle.comment,
            requested_changes=list(cycle.requested_changes),
            highlighted_risks=list(cycle.highlighted_risks),
            status=cycle.status,
            latest_approval_id=cycle.latest_approval_id,
            latest_approval_status=cycle.latest_approval_status,
            resubmitted_version_number=cycle.resubmitted_version_number,
            resubmitted_at=cycle.resubmitted_at,
        )


class ProjectRetrospectiveFailureClusterResponse(BaseModel):
    """One failure-review cluster scoped to the selected project."""

    cluster_key: str
    failure_category: str
    count: int
    latest_run_created_at: datetime
    route_reason_excerpt: str | None = None
    sample_task_titles: list[str]
    run_ids: list[UUID]

    @classmethod
    def from_cluster(
        cls,
        cluster: FailureReviewCluster,
    ) -> "ProjectRetrospectiveFailureClusterResponse":
        """Convert one failure cluster into an API DTO."""

        return cls(
            cluster_key=cluster.cluster_key,
            failure_category=cluster.failure_category,
            count=cluster.count,
            latest_run_created_at=cluster.latest_run_created_at,
            route_reason_excerpt=cluster.route_reason_excerpt,
            sample_task_titles=list(cluster.sample_task_titles),
            run_ids=list(cluster.run_ids),
        )


class ProjectRetrospectiveFailureRunResponse(BaseModel):
    """One recent failed run shown in the Day12 retrospective panel."""

    run_id: UUID
    task_id: UUID
    task_title: str | None = None
    created_at: datetime
    run_status: str
    failure_category: str | None = None
    headline: str
    stages: list[str]
    review: dict[str, Any] | None = None

    @classmethod
    def from_item(
        cls,
        item: ProjectFailureRetrospectiveItem,
    ) -> "ProjectRetrospectiveFailureRunResponse":
        """Convert one failed-run retrospective item into its API DTO."""

        review_payload = None
        if item.failure_review is not None:
            review_payload = {
                "review_id": item.failure_review.review_id,
                "conclusion": item.failure_review.conclusion,
                "action_summary": item.failure_review.action_summary,
            }

        return cls(
            run_id=item.run_id,
            task_id=item.task_id,
            task_title=item.task_title,
            created_at=item.created_at,
            run_status=item.run_status.value,
            failure_category=(
                item.failure_category.value if item.failure_category is not None else None
            ),
            headline=item.headline,
            stages=list(item.stages),
            review=review_payload,
        )


class ProjectRetrospectiveResponse(BaseModel):
    """Project-scoped Day12 retrospective payload."""

    project_id: UUID
    generated_at: datetime
    summary: ProjectRetrospectiveSummaryResponse
    approval_cycles: list[ProjectRetrospectiveApprovalCycleResponse]
    failure_clusters: list[ProjectRetrospectiveFailureClusterResponse]
    recent_failures: list[ProjectRetrospectiveFailureRunResponse]


class ChangeReworkChainStepResponse(BaseModel):
    """One chain node shown in the Day12 change-rework panel."""

    step_id: str
    stage: str
    label: str
    summary: str
    occurred_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_step(
        cls,
        step: ChangeReworkChainStep,
    ) -> "ChangeReworkChainStepResponse":
        """Convert one service-level chain step into an API DTO."""

        return cls(
            step_id=step.step_id,
            stage=step.stage,
            label=step.label,
            summary=step.summary,
            occurred_at=step.occurred_at,
            metadata=dict(step.metadata),
        )


class ChangeReworkItemResponse(BaseModel):
    """One Day12 rework closure item with all backward references."""

    rework_id: str
    project_id: UUID
    chain_source: str
    status: str
    recommendation: str
    closed: bool
    occurred_at: datetime
    change_batch_id: UUID | None = None
    change_batch_title: str | None = None
    evidence_package_key: str | None = None
    deliverable_id: UUID | None = None
    deliverable_title: str | None = None
    approval_id: UUID | None = None
    approval_status: ApprovalStatus | None = None
    decision_action: ApprovalDecisionAction | None = None
    reason_summary: str
    reason_comment: str | None = None
    requested_changes: list[str]
    highlighted_risks: list[str]
    latest_failure_category: str | None = None
    verification_total_runs: int
    verification_failed_runs: int
    linked_task_ids: list[UUID]
    linked_run_ids: list[UUID]
    steps: list[ChangeReworkChainStepResponse]

    @classmethod
    def from_item(
        cls,
        item: ChangeReworkItem,
    ) -> "ChangeReworkItemResponse":
        """Convert one service-level rework item into an API DTO."""

        return cls(
            rework_id=item.rework_id,
            project_id=item.project_id,
            chain_source=item.chain_source,
            status=item.status,
            recommendation=item.recommendation,
            closed=item.closed,
            occurred_at=item.occurred_at,
            change_batch_id=item.change_batch_id,
            change_batch_title=item.change_batch_title,
            evidence_package_key=item.evidence_package_key,
            deliverable_id=item.deliverable_id,
            deliverable_title=item.deliverable_title,
            approval_id=item.approval_id,
            approval_status=item.approval_status,
            decision_action=item.decision_action,
            reason_summary=item.reason_summary,
            reason_comment=item.reason_comment,
            requested_changes=list(item.requested_changes),
            highlighted_risks=list(item.highlighted_risks),
            latest_failure_category=item.latest_failure_category,
            verification_total_runs=item.verification_total_runs,
            verification_failed_runs=item.verification_failed_runs,
            linked_task_ids=list(item.linked_task_ids),
            linked_run_ids=list(item.linked_run_ids),
            steps=[
                ChangeReworkChainStepResponse.from_step(step) for step in item.steps
            ],
        )


class ProjectChangeReworkSummaryResponse(BaseModel):
    """Top-level counters for Day12 change-rework closure."""

    total_items: int
    approval_rework_items: int
    verification_rework_items: int
    rollback_recommendations: int
    replan_recommendations: int
    open_items: int
    closed_items: int

    @classmethod
    def from_summary(
        cls,
        summary: ProjectChangeReworkSummary,
    ) -> "ProjectChangeReworkSummaryResponse":
        """Convert one service-level summary into an API DTO."""

        return cls(
            total_items=summary.total_items,
            approval_rework_items=summary.approval_rework_items,
            verification_rework_items=summary.verification_rework_items,
            rollback_recommendations=summary.rollback_recommendations,
            replan_recommendations=summary.replan_recommendations,
            open_items=summary.open_items,
            closed_items=summary.closed_items,
        )


class ProjectChangeReworkResponse(BaseModel):
    """Project-scoped Day12 rework closure payload."""

    project_id: UUID
    generated_at: datetime
    summary: ProjectChangeReworkSummaryResponse
    items: list[ChangeReworkItemResponse]

    @classmethod
    def from_snapshot(
        cls,
        snapshot: ProjectChangeReworkSnapshot,
    ) -> "ProjectChangeReworkResponse":
        """Convert one service-level snapshot into an API DTO."""

        return cls(
            project_id=snapshot.project_id,
            generated_at=snapshot.generated_at,
            summary=ProjectChangeReworkSummaryResponse.from_summary(snapshot.summary),
            items=[ChangeReworkItemResponse.from_item(item) for item in snapshot.items],
        )


class RepositoryReleaseGateDecisionResponse(BaseModel):
    """One Day14 release-gate decision row."""

    id: UUID
    change_batch_id: UUID
    action: ApprovalDecisionAction
    actor_name: str
    summary: str
    comment: str | None = None
    highlighted_risks: list[str]
    requested_changes: list[str]
    created_at: datetime

    @classmethod
    def from_decision(
        cls,
        decision: RepositoryReleaseGateDecision,
    ) -> "RepositoryReleaseGateDecisionResponse":
        """Convert one release-gate decision into an API DTO."""

        return cls(
            id=decision.id,
            change_batch_id=decision.change_batch_id,
            action=decision.action,
            actor_name=decision.actor_name,
            summary=decision.summary,
            comment=decision.comment,
            highlighted_risks=list(decision.highlighted_risks),
            requested_changes=list(decision.requested_changes),
            created_at=decision.created_at,
        )


class RepositoryReleaseChecklistItemResponse(BaseModel):
    """One Day14 release-checklist item shown in approval pages."""

    key: str
    title: str
    required: bool
    status: RepositoryReleaseChecklistItemStatus
    summary: str
    gap_reason: str | None = None
    evidence_key: str | None = None
    checked_at: datetime | None = None

    @classmethod
    def from_item(
        cls,
        item: RepositoryReleaseChecklistItem,
    ) -> "RepositoryReleaseChecklistItemResponse":
        """Convert one checklist item into an API DTO."""

        return cls(
            key=item.key,
            title=item.title,
            required=item.required,
            status=item.status,
            summary=item.summary,
            gap_reason=item.gap_reason,
            evidence_key=item.evidence_key,
            checked_at=item.checked_at,
        )


class RepositoryReleaseGateSummaryResponse(BaseModel):
    """Project-scoped Day14 release-gate summary row."""

    change_batch_id: UUID
    change_batch_title: str
    generated_at: datetime
    status: RepositoryReleaseGateStatus
    blocked: bool
    missing_item_count: int
    decision_count: int
    release_qualification_established: bool
    latest_decision: RepositoryReleaseGateDecisionResponse | None = None


class ProjectRepositoryReleaseGateInboxResponse(BaseModel):
    """Project-scoped Day14 release-gate inbox payload."""

    project_id: UUID
    generated_at: datetime
    total_batches: int
    blocked_batches: int
    pending_batches: int
    approved_batches: int
    rejected_batches: int
    changes_requested_batches: int
    items: list[RepositoryReleaseGateSummaryResponse]

    @classmethod
    def from_inbox(
        cls,
        inbox: ProjectRepositoryReleaseGateInbox,
    ) -> "ProjectRepositoryReleaseGateInboxResponse":
        """Convert one release-gate inbox snapshot into an API DTO."""

        return cls(
            project_id=inbox.project_id,
            generated_at=inbox.generated_at,
            total_batches=inbox.total_batches,
            blocked_batches=inbox.blocked_batches,
            pending_batches=inbox.pending_batches,
            approved_batches=inbox.approved_batches,
            rejected_batches=inbox.rejected_batches,
            changes_requested_batches=inbox.changes_requested_batches,
            items=[
                RepositoryReleaseGateSummaryResponse(
                    change_batch_id=item.change_batch_id,
                    change_batch_title=item.change_batch_title,
                    generated_at=item.generated_at,
                    status=item.status,
                    blocked=item.blocked,
                    missing_item_count=item.missing_item_count,
                    decision_count=item.decision_count,
                    release_qualification_established=item.release_qualification_established,
                    latest_decision=(
                        RepositoryReleaseGateDecisionResponse.from_decision(
                            item.latest_decision
                        )
                        if item.latest_decision is not None
                        else None
                    ),
                )
                for item in inbox.items
            ],
        )


class RepositoryReleaseGateDetailResponse(BaseModel):
    """Full Day14 release-gate detail for one change batch."""

    project_id: UUID
    change_batch_id: UUID
    change_batch_title: str
    generated_at: datetime
    snapshot_age_minutes: int | None = None
    required_item_count: int
    passed_item_count: int
    checklist_items: list[RepositoryReleaseChecklistItemResponse]
    missing_item_keys: list[str]
    gap_reasons: list[str]
    blocked: bool
    status: RepositoryReleaseGateStatus
    approval_status: ApprovalStatus | None = None
    release_qualification_established: bool
    git_write_actions_triggered: bool
    decision_count: int
    latest_decision: RepositoryReleaseGateDecisionResponse | None = None
    decisions: list[RepositoryReleaseGateDecisionResponse]

    @classmethod
    def from_gate(
        cls,
        gate: RepositoryReleaseGate,
    ) -> "RepositoryReleaseGateDetailResponse":
        """Convert one release-gate detail snapshot into an API DTO."""

        return cls(
            project_id=gate.project_id,
            change_batch_id=gate.change_batch_id,
            change_batch_title=gate.change_batch_title,
            generated_at=gate.generated_at,
            snapshot_age_minutes=gate.snapshot_age_minutes,
            required_item_count=gate.required_item_count,
            passed_item_count=gate.passed_item_count,
            checklist_items=[
                RepositoryReleaseChecklistItemResponse.from_item(item)
                for item in gate.checklist_items
            ],
            missing_item_keys=list(gate.missing_item_keys),
            gap_reasons=list(gate.gap_reasons),
            blocked=gate.blocked,
            status=gate.status,
            approval_status=gate.approval_status,
            release_qualification_established=gate.release_qualification_established,
            git_write_actions_triggered=gate.git_write_actions_triggered,
            decision_count=gate.decision_count,
            latest_decision=(
                RepositoryReleaseGateDecisionResponse.from_decision(gate.latest_decision)
                if gate.latest_decision is not None
                else None
            ),
            decisions=[
                RepositoryReleaseGateDecisionResponse.from_decision(item)
                for item in gate.decisions
            ],
        )


class Day15ReleaseJudgementItemResponse(BaseModel):
    """Compact Day15 release-judgement row for one change batch."""

    change_batch_id: UUID
    change_batch_title: str
    status: RepositoryReleaseGateStatus
    blocked: bool
    missing_item_count: int
    decision_count: int
    release_qualification_established: bool
    latest_decision_action: ApprovalDecisionAction | None = None
    latest_decision_summary: str | None = None


class Day15ReleaseJudgementResponse(BaseModel):
    """Project-scoped Day15 release-judgement snapshot."""

    project_id: UUID
    generated_at: datetime
    total_batches: int
    blocked_batches: int
    reviewable_batches: int
    selected_change_batch_id: UUID | None = None
    selected_change_batch_title: str | None = None
    selected_status: RepositoryReleaseGateStatus | None = None
    selected_blocked: bool
    selected_missing_item_keys: list[str]
    selected_gap_reasons: list[str]
    selected_decision_count: int
    selected_decision_actions: list[ApprovalDecisionAction]
    release_qualification_established: bool
    git_write_actions_triggered: bool
    summary: str
    items: list[Day15ReleaseJudgementItemResponse]


class ApprovalCreateRequest(BaseModel):
    """Body accepted by the approval-request creation endpoint."""

    deliverable_id: UUID
    requester_role_code: ProjectRoleCode
    request_note: str | None = Field(default=None, max_length=1_000)
    due_in_hours: float = Field(default=24, ge=0, le=24 * 14)


class ApprovalActionRequest(BaseModel):
    """Body accepted when the boss applies one approval decision."""

    action: ApprovalDecisionAction
    actor_name: str = Field(default="老板", min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    comment: str | None = Field(default=None, max_length=2_000)
    highlighted_risks: list[str] = Field(default_factory=list, max_length=10)
    requested_changes: list[str] = Field(default_factory=list, max_length=10)


class RepositoryPreflightActionRequest(BaseModel):
    """Body accepted when one Day08 manual-confirmation decision is applied."""

    action: ChangeBatchManualConfirmationAction
    actor_name: str = Field(default="老板", min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    comment: str | None = Field(default=None, max_length=2_000)
    highlighted_risks: list[str] = Field(default_factory=list, max_length=20)


class RepositoryReleaseGateActionRequest(BaseModel):
    """Body accepted when one Day14 release-gate decision is applied."""

    action: ApprovalDecisionAction
    actor_name: str = Field(default="老板", min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    comment: str | None = Field(default=None, max_length=2_000)
    highlighted_risks: list[str] = Field(default_factory=list, max_length=20)
    requested_changes: list[str] = Field(default_factory=list, max_length=20)


def get_approval_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ApprovalService:
    """Create the shared Day10 approval service dependency."""

    project_repository = ProjectRepository(session)
    return ApprovalService(
        approval_repository=ApprovalRepository(session),
        deliverable_repository=DeliverableRepository(session),
        project_repository=project_repository,
    )


def get_change_batch_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ChangeBatchService:
    """Create the shared change-batch service used by Day08 approval panels."""

    return ChangeBatchService(
        change_batch_repository=ChangeBatchRepository(session),
        change_plan_repository=ChangePlanRepository(session),
        project_repository=ProjectRepository(session),
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
        task_repository=TaskRepository(session),
        deliverable_repository=DeliverableRepository(session),
    )


def get_change_risk_guard_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ChangeRiskGuardService:
    """Create the Day08 preflight risk-guard dependency."""

    return ChangeRiskGuardService(
        change_batch_repository=ChangeBatchRepository(session),
        project_repository=ProjectRepository(session),
    )


def get_repository_release_gate_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> RepositoryReleaseGateService:
    """Create the Day14 repository release-gate dependency."""

    project_repository = ProjectRepository(session)
    repository_workspace_repository = RepositoryWorkspaceRepository(session)
    change_batch_repository = ChangeBatchRepository(session)
    commit_candidate_repository = CommitCandidateRepository(session)
    verification_run_repository = VerificationRunRepository(session)
    return RepositoryReleaseGateService(
        project_repository=project_repository,
        repository_workspace_repository=repository_workspace_repository,
        repository_snapshot_repository=RepositorySnapshotRepository(session),
        change_batch_repository=change_batch_repository,
        commit_candidate_repository=commit_candidate_repository,
        verification_run_repository=verification_run_repository,
        diff_summary_service=DiffSummaryService(
            project_repository=project_repository,
            repository_workspace_repository=repository_workspace_repository,
            change_batch_repository=change_batch_repository,
            deliverable_repository=DeliverableRepository(session),
            approval_repository=ApprovalRepository(session),
            verification_run_repository=verification_run_repository,
        ),
    )


def get_change_rework_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ChangeReworkService:
    """Create the Day12 change-rework aggregation dependency."""

    project_repository = ProjectRepository(session)
    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    run_logging_service = RunLoggingService()
    failure_review_service = FailureReviewService(
        failure_review_repository=FailureReviewRepository(),
        run_logging_service=run_logging_service,
    )
    decision_replay_service = DecisionReplayService(
        run_logging_service=run_logging_service,
        failure_review_service=failure_review_service,
    )
    approval_service = ApprovalService(
        approval_repository=ApprovalRepository(session),
        deliverable_repository=DeliverableRepository(session),
        project_repository=project_repository,
    )
    diff_summary_service = DiffSummaryService(
        project_repository=project_repository,
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
        change_batch_repository=ChangeBatchRepository(session),
        deliverable_repository=DeliverableRepository(session),
        approval_repository=ApprovalRepository(session),
        verification_run_repository=VerificationRunRepository(session),
    )
    return ChangeReworkService(
        project_repository=project_repository,
        change_batch_repository=ChangeBatchRepository(session),
        verification_run_repository=VerificationRunRepository(session),
        task_repository=task_repository,
        run_repository=run_repository,
        approval_service=approval_service,
        decision_replay_service=decision_replay_service,
        diff_summary_service=diff_summary_service,
    )


def _build_project_retrospective_payload(
    *,
    project_id: UUID,
    session: Session,
) -> ProjectRetrospectiveResponse | None:
    """Build the Day12 project retrospective payload from approvals and failures."""

    project_repository = ProjectRepository(session)
    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    approval_service = ApprovalService(
        approval_repository=ApprovalRepository(session),
        deliverable_repository=DeliverableRepository(session),
        project_repository=project_repository,
    )
    run_logging_service = RunLoggingService()
    failure_review_service = FailureReviewService(
        failure_review_repository=FailureReviewRepository(),
        run_logging_service=run_logging_service,
    )
    decision_replay_service = DecisionReplayService(
        run_logging_service=run_logging_service,
        failure_review_service=failure_review_service,
    )

    if project_repository.get_by_id(project_id) is None:
        return None

    approval_records = approval_service.get_project_inbox(project_id)
    rework_cycles = approval_service.list_project_rework_cycles(project_id) or []

    tasks = task_repository.list_by_project_id(project_id)
    task_title_map = {task.id: task.title for task in tasks}
    runs = run_repository.list_by_task_ids(list(task_title_map))
    run_ids = [run.id for run in runs]
    failure_reviews = failure_review_service.list_reviews_for_run_ids(
        run_ids=run_ids,
        limit=None,
    )
    failure_clusters = failure_review_service.list_clusters_for_run_ids(
        run_ids=run_ids,
        limit=6,
    )
    recent_failures = decision_replay_service.build_project_failure_history(
        runs=runs,
        task_titles=task_title_map,
        limit=8,
    )

    return ProjectRetrospectiveResponse(
        project_id=project_id,
        generated_at=utc_now(),
        summary=ProjectRetrospectiveSummaryResponse(
            total_approval_requests=approval_records.total_requests if approval_records else 0,
            negative_approval_cycles=len(rework_cycles),
            open_rework_cycles=sum(
                1
                for cycle in rework_cycles
                if cycle.status != "approved_after_rework"
            ),
            total_failure_reviews=len(failure_reviews),
            failure_clusters=len(failure_clusters),
        ),
        approval_cycles=[
            ProjectRetrospectiveApprovalCycleResponse.from_cycle(cycle)
            for cycle in rework_cycles[:8]
        ],
        failure_clusters=[
            ProjectRetrospectiveFailureClusterResponse.from_cluster(cluster)
            for cluster in failure_clusters
        ],
        recent_failures=[
            ProjectRetrospectiveFailureRunResponse.from_item(item)
            for item in recent_failures
        ],
    )


router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post(
    "",
    response_model=ApprovalDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create one explicit boss-approval request for a deliverable",
)
def create_approval_request(
    request: ApprovalCreateRequest,
    approval_service: Annotated[ApprovalService, Depends(get_approval_service)],
) -> ApprovalDetailResponse:
    """Create one new approval request tied to the current deliverable version."""

    try:
        detail = approval_service.request_deliverable_approval(
            deliverable_id=request.deliverable_id,
            requester_role_code=request.requester_role_code,
            request_note=request.request_note,
            due_in_hours=request.due_in_hours,
        )
    except ValueError as exc:
        message = str(exc)
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if message.startswith("Deliverable not found:")
                or message.startswith("Project not found:")
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=message,
        ) from exc

    return ApprovalDetailResponse.from_detail(detail)


@router.get(
    "/projects/{project_id}",
    response_model=ProjectApprovalInboxResponse,
    summary="Get the project-scoped boss approval inbox",
)
def get_project_approval_inbox(
    project_id: UUID,
    approval_service: Annotated[ApprovalService, Depends(get_approval_service)],
) -> ProjectApprovalInboxResponse:
    """Return the Day10 approval queue, including overdue items, for one project."""

    inbox = approval_service.get_project_inbox(project_id)
    if inbox is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return ProjectApprovalInboxResponse.from_inbox(inbox)


@router.get(
    "/projects/{project_id}/repository-preflight",
    response_model=ProjectRepositoryPreflightInboxResponse,
    summary="Get the Day08 repository-preflight manual-confirmation queue",
)
def get_project_repository_preflight_inbox(
    project_id: UUID,
    change_batch_service: Annotated[
        ChangeBatchService,
        Depends(get_change_batch_service),
    ],
) -> ProjectRepositoryPreflightInboxResponse:
    """Return the project-scoped Day08 repository-preflight results and pending queue."""

    try:
        change_batch_summaries = change_batch_service.list_change_batches(project_id)
    except ChangeBatchProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    items = [
        RepositoryPreflightApprovalSummaryResponse.from_change_batch_summary(item)
        for item in change_batch_summaries
        if item.change_batch.preflight.status != ChangeBatchPreflightStatus.NOT_STARTED
    ]
    pending_confirmations = sum(
        1
        for item in items
        if item.preflight.status == ChangeBatchPreflightStatus.BLOCKED_REQUIRES_CONFIRMATION
    )
    ready_batches = sum(
        1
        for item in items
        if item.preflight.status
        in {
            ChangeBatchPreflightStatus.READY_FOR_EXECUTION,
            ChangeBatchPreflightStatus.MANUAL_CONFIRMED,
        }
    )
    rejected_batches = sum(
        1
        for item in items
        if item.preflight.status == ChangeBatchPreflightStatus.MANUAL_REJECTED
    )

    return ProjectRepositoryPreflightInboxResponse(
        project_id=project_id,
        total_batches=len(items),
        pending_confirmations=pending_confirmations,
        ready_batches=ready_batches,
        rejected_batches=rejected_batches,
        generated_at=utc_now(),
        items=items,
    )


@router.get(
    "/repository-preflight/{change_batch_id}",
    response_model=RepositoryPreflightApprovalDetailResponse,
    summary="Get one Day08 repository-preflight detail",
)
def get_repository_preflight_detail(
    change_batch_id: UUID,
    change_batch_service: Annotated[
        ChangeBatchService,
        Depends(get_change_batch_service),
    ],
) -> RepositoryPreflightApprovalDetailResponse:
    """Return one change batch together with its Day08 preflight detail."""

    try:
        detail = change_batch_service.get_change_batch_detail(change_batch_id)
    except ChangeBatchNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return RepositoryPreflightApprovalDetailResponse.from_change_batch_detail(detail)


@router.post(
    "/repository-preflight/{change_batch_id}/actions",
    response_model=RepositoryPreflightApprovalDetailResponse,
    summary="Apply one Day08 manual-confirmation decision",
)
def apply_repository_preflight_action(
    change_batch_id: UUID,
    request: RepositoryPreflightActionRequest,
    change_risk_guard_service: Annotated[
        ChangeRiskGuardService,
        Depends(get_change_risk_guard_service),
    ],
    change_batch_service: Annotated[
        ChangeBatchService,
        Depends(get_change_batch_service),
    ],
) -> RepositoryPreflightApprovalDetailResponse:
    """Persist one Day08 manual-confirmation decision and return the latest detail."""

    try:
        change_risk_guard_service.apply_manual_confirmation(
            change_batch_id=change_batch_id,
            action=request.action,
            actor_name=request.actor_name,
            summary=request.summary,
            comment=request.comment,
            highlighted_risks=request.highlighted_risks,
        )
        detail = change_batch_service.get_change_batch_detail(change_batch_id)
    except (
        ChangeRiskGuardBatchNotFoundError,
        ChangeRiskGuardProjectNotFoundError,
        ChangeBatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        ChangeRiskGuardPreflightMissingError,
        ChangeRiskGuardManualConfirmationError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return RepositoryPreflightApprovalDetailResponse.from_change_batch_detail(detail)


@router.get(
    "/projects/{project_id}/repository-release-gate",
    response_model=ProjectRepositoryReleaseGateInboxResponse,
    summary="Get the Day14 repository release-gate inbox",
)
def get_project_repository_release_gate_inbox(
    project_id: UUID,
    repository_release_gate_service: Annotated[
        RepositoryReleaseGateService,
        Depends(get_repository_release_gate_service),
    ],
) -> ProjectRepositoryReleaseGateInboxResponse:
    """Return project-scoped Day14 release-gate summaries."""

    try:
        inbox = repository_release_gate_service.list_project_release_gates(project_id)
    except RepositoryReleaseGateProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ProjectRepositoryReleaseGateInboxResponse.from_inbox(inbox)


@router.get(
    "/repository-release-gate/{change_batch_id}",
    response_model=RepositoryReleaseGateDetailResponse,
    summary="Get one Day14 repository release-gate detail",
)
def get_repository_release_gate_detail(
    change_batch_id: UUID,
    repository_release_gate_service: Annotated[
        RepositoryReleaseGateService,
        Depends(get_repository_release_gate_service),
    ],
) -> RepositoryReleaseGateDetailResponse:
    """Return one Day14 release checklist and decision history by change batch."""

    try:
        gate = repository_release_gate_service.get_release_gate(change_batch_id)
    except (
        RepositoryReleaseGateProjectNotFoundError,
        RepositoryReleaseGateChangeBatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return RepositoryReleaseGateDetailResponse.from_gate(gate)


@router.post(
    "/repository-release-gate/{change_batch_id}/actions",
    response_model=RepositoryReleaseGateDetailResponse,
    summary="Apply one Day14 release-gate decision",
)
def apply_repository_release_gate_action(
    change_batch_id: UUID,
    request: RepositoryReleaseGateActionRequest,
    repository_release_gate_service: Annotated[
        RepositoryReleaseGateService,
        Depends(get_repository_release_gate_service),
    ],
) -> RepositoryReleaseGateDetailResponse:
    """Persist one Day14 release-gate decision and return the updated snapshot."""

    try:
        gate = repository_release_gate_service.apply_release_gate_action(
            change_batch_id=change_batch_id,
            action=request.action,
            actor_name=request.actor_name,
            summary=request.summary,
            comment=request.comment,
            highlighted_risks=request.highlighted_risks,
            requested_changes=request.requested_changes,
        )
    except (
        RepositoryReleaseGateProjectNotFoundError,
        RepositoryReleaseGateChangeBatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RepositoryReleaseGateBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RepositoryReleaseGateActionValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return RepositoryReleaseGateDetailResponse.from_gate(gate)


@router.get(
    "/projects/{project_id}/day15-release-judgement",
    response_model=Day15ReleaseJudgementResponse,
    summary="Get the Day15 release-judgement snapshot for one project",
)
def get_project_day15_release_judgement(
    project_id: UUID,
    repository_release_gate_service: Annotated[
        RepositoryReleaseGateService,
        Depends(get_repository_release_gate_service),
    ],
    change_batch_id: UUID | None = None,
) -> Day15ReleaseJudgementResponse:
    """Return one Day15 read-only release-judgement view for boss review."""

    try:
        inbox = repository_release_gate_service.list_project_release_gates(project_id)
    except RepositoryReleaseGateProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    summary_items = [
        Day15ReleaseJudgementItemResponse(
            change_batch_id=item.change_batch_id,
            change_batch_title=item.change_batch_title,
            status=item.status,
            blocked=item.blocked,
            missing_item_count=item.missing_item_count,
            decision_count=item.decision_count,
            release_qualification_established=item.release_qualification_established,
            latest_decision_action=(
                item.latest_decision.action if item.latest_decision is not None else None
            ),
            latest_decision_summary=(
                item.latest_decision.summary if item.latest_decision is not None else None
            ),
        )
        for item in inbox.items
    ]

    selected_item = None
    if change_batch_id is not None:
        selected_item = next(
            (item for item in inbox.items if item.change_batch_id == change_batch_id),
            None,
        )
        if selected_item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Change batch not found in Day15 release judgement scope: "
                    f"{change_batch_id}"
                ),
            )
    else:
        selected_item = (
            next((item for item in inbox.items if item.blocked), None)
            or next(
                (
                    item
                    for item in inbox.items
                    if item.status == RepositoryReleaseGateStatus.PENDING_APPROVAL
                ),
                None,
            )
            or next(iter(inbox.items), None)
        )

    selected_gate = (
        repository_release_gate_service.get_release_gate(selected_item.change_batch_id)
        if selected_item is not None
        else None
    )
    reviewable_batches = sum(1 for item in inbox.items if not item.blocked)

    if selected_gate is None:
        summary = "当前项目尚无可用于放行判断的变更批次。"
    elif selected_gate.blocked:
        summary = (
            "放行检查单存在缺口："
            + "；".join(selected_gate.gap_reasons or selected_gate.missing_item_keys)
        )
    else:
        summary = (
            f"当前放行状态为 {selected_gate.status.value}，"
            f"累计决策 {selected_gate.decision_count} 条。"
        )

    return Day15ReleaseJudgementResponse(
        project_id=project_id,
        generated_at=utc_now(),
        total_batches=inbox.total_batches,
        blocked_batches=inbox.blocked_batches,
        reviewable_batches=reviewable_batches,
        selected_change_batch_id=(
            selected_gate.change_batch_id if selected_gate is not None else None
        ),
        selected_change_batch_title=(
            selected_gate.change_batch_title if selected_gate is not None else None
        ),
        selected_status=selected_gate.status if selected_gate is not None else None,
        selected_blocked=selected_gate.blocked if selected_gate is not None else False,
        selected_missing_item_keys=(
            list(selected_gate.missing_item_keys) if selected_gate is not None else []
        ),
        selected_gap_reasons=(
            list(selected_gate.gap_reasons) if selected_gate is not None else []
        ),
        selected_decision_count=(
            selected_gate.decision_count if selected_gate is not None else 0
        ),
        selected_decision_actions=(
            [item.action for item in selected_gate.decisions]
            if selected_gate is not None
            else []
        ),
        release_qualification_established=(
            selected_gate.release_qualification_established
            if selected_gate is not None
            else False
        ),
        git_write_actions_triggered=(
            selected_gate.git_write_actions_triggered
            if selected_gate is not None
            else False
        ),
        summary=summary,
        items=summary_items,
    )


@router.get(
    "/projects/{project_id}/retrospective",
    response_model=ProjectRetrospectiveResponse,
    summary="Get the Day12 project retrospective summary",
)
def get_project_retrospective(
    project_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectRetrospectiveResponse:
    """Return the Day12 project retrospective across approvals and failed runs."""

    payload = _build_project_retrospective_payload(project_id=project_id, session=session)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return payload


@router.get(
    "/projects/{project_id}/change-rework",
    response_model=ProjectChangeReworkResponse,
    summary="Get the Day12 project change-rework closure snapshot",
)
def get_project_change_rework(
    project_id: UUID,
    change_rework_service: Annotated[
        ChangeReworkService,
        Depends(get_change_rework_service),
    ],
) -> ProjectChangeReworkResponse:
    """Return project-scoped plan -> verification -> reject/failure -> rework chains."""

    snapshot = change_rework_service.get_project_change_rework_snapshot(project_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return ProjectChangeReworkResponse.from_snapshot(snapshot)


@router.get(
    "/{approval_id}/history",
    response_model=ApprovalHistoryResponse,
    summary="Get the deliverable-scoped approval redo history",
)
def get_approval_history(
    approval_id: UUID,
    approval_service: Annotated[ApprovalService, Depends(get_approval_service)],
) -> ApprovalHistoryResponse:
    """Return the full submit -> decision -> redo chain of one approval."""

    try:
        history = approval_service.get_approval_history(approval_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request not found: {approval_id}",
        )

    return ApprovalHistoryResponse.from_history(history)


@router.get(
    "/{approval_id}",
    response_model=ApprovalDetailResponse,
    summary="Get one approval request and its decision replay history",
)
def get_approval_detail(
    approval_id: UUID,
    approval_service: Annotated[ApprovalService, Depends(get_approval_service)],
) -> ApprovalDetailResponse:
    """Return one approval request with its structured decision history."""

    detail = approval_service.get_approval_detail(approval_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request not found: {approval_id}",
        )

    return ApprovalDetailResponse.from_detail(detail)


@router.post(
    "/{approval_id}/actions",
    response_model=ApprovalDetailResponse,
    summary="Apply one boss decision to an approval request",
)
def apply_approval_action(
    approval_id: UUID,
    request: ApprovalActionRequest,
    approval_service: Annotated[ApprovalService, Depends(get_approval_service)],
) -> ApprovalDetailResponse:
    """Persist one structured approval decision and return the updated detail."""

    try:
        detail = approval_service.apply_approval_decision(
            approval_id=approval_id,
            action=request.action,
            actor_name=request.actor_name,
            summary=request.summary,
            comment=request.comment,
            highlighted_risks=request.highlighted_risks,
            requested_changes=request.requested_changes,
        )
    except ValueError as exc:
        message = str(exc)
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if message.startswith("Approval request not found:")
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=message,
        ) from exc

    return ApprovalDetailResponse.from_detail(detail)
