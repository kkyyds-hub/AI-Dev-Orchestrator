"""Repository release-gate and draft-chain response schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.approval import ApprovalDecisionAction, ApprovalStatus
from app.domain.change_batch import ChangeBatchPreflightStatus
from app.domain.commit_candidate import CommitCandidateStatus
from app.services.repository_release_gate_service import (
    ProjectRepositoryReleaseGateInbox,
    RepositoryReleaseChecklistItem,
    RepositoryReleaseChecklistItemStatus,
    RepositoryReleaseGate,
    RepositoryReleaseGateDecision,
    RepositoryReleaseGateStatus,
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
    """One Day14 release-checklist item shown in detail views."""

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
    """Project-scoped Day14 release-gate inbox summary."""

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


class RepositoryDay15FlowStepStatus(StrEnum):
    """Progress status used by the Day15 minimum closed-loop demo timeline."""

    COMPLETED = "completed"
    PENDING = "pending"
    BLOCKED = "blocked"


class RepositoryDay15FlowStatus(StrEnum):
    """Overall status of the Day15 minimum closed-loop demo."""

    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    READY_FOR_REVIEW = "ready_for_review"


class RepositoryDay15FlowStepResponse(BaseModel):
    """One Day15 step row aggregated from Day01-Day14 capabilities."""

    key: str
    title: str
    status: RepositoryDay15FlowStepStatus
    summary: str
    evidence_key: str | None = None


class RepositoryDay15FlowResponse(BaseModel):
    """Project-scoped Day15 minimum closed-loop demo snapshot."""

    project_id: UUID
    project_name: str
    generated_at: datetime
    selected_change_batch_id: UUID | None = None
    selected_change_batch_title: str | None = None
    overall_status: RepositoryDay15FlowStatus
    completed_step_count: int
    total_step_count: int
    blocked_step_count: int
    change_plan_count: int
    change_batch_count: int
    release_status: RepositoryReleaseGateStatus | None = None
    release_qualification_established: bool
    git_write_actions_triggered: bool
    steps: list[RepositoryDay15FlowStepResponse]


class RepositoryDraftChainReadbackResponse(BaseModel):
    """Safe CL-12 readback for the review-only repository draft chain."""

    project_id: UUID
    project_name: str
    generated_at: datetime
    review_only: bool = True
    safe_runtime_path: bool = True
    selected_change_batch_id: UUID | None = None
    selected_change_batch_title: str | None = None
    change_plan_count: int
    change_batch_count: int
    preflight_status: ChangeBatchPreflightStatus | None = None
    preflight_ready_for_execution: bool = False
    commit_candidate_present: bool = False
    commit_candidate_id: UUID | None = None
    commit_candidate_status: CommitCandidateStatus | None = None
    commit_candidate_current_version: int | None = None
    commit_candidate_revision_count: int = 0
    commit_candidate_related_file_count: int = 0
    commit_candidate_evidence_package_key: str | None = None
    commit_candidate_review_only: bool = True
    release_status: RepositoryReleaseGateStatus | None = None
    release_blocked: bool = False
    release_missing_item_keys: list[str] = Field(default_factory=list)
    release_qualification_established: bool = False
    git_write_actions_triggered: bool = False
    apply_local_triggered: bool = False
    git_commit_triggered: bool = False
    forbidden_actions: list[str] = Field(
        default_factory=lambda: [
            "POST /repositories/change-batches/{change_batch_id}/apply-local",
            "POST /repositories/change-batches/{change_batch_id}/git-commit",
        ],
    )
    day15_flow: RepositoryDay15FlowResponse
