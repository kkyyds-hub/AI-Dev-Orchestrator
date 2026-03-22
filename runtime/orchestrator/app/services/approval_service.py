"""Business services for the V3 Day10 boss approval gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from app.domain._base import utc_now
from app.domain.approval import (
    ApprovalDecision,
    ApprovalDecisionAction,
    ApprovalRequest,
    ApprovalStatus,
    map_approval_action_to_status,
)
from app.domain.project import ProjectStage
from app.domain.project_role import ProjectRoleCode
from app.repositories.approval_repository import ApprovalRecord, ApprovalRepository
from app.repositories.deliverable_repository import DeliverableRepository
from app.repositories.project_repository import ProjectRepository


@dataclass(slots=True, frozen=True)
class ApprovalQueueItem:
    """One approval queue row with the latest structured decision summary."""

    approval: ApprovalRequest
    latest_decision: ApprovalDecision | None
    overdue: bool


@dataclass(slots=True, frozen=True)
class ApprovalDetail:
    """One approval request together with its full decision replay history."""

    approval: ApprovalRequest
    decisions: list[ApprovalDecision]
    overdue: bool


@dataclass(slots=True, frozen=True)
class ProjectApprovalInbox:
    """Project-scoped approval queue view surfaced on the boss console."""

    project_id: UUID
    total_requests: int
    pending_requests: int
    overdue_requests: int
    completed_requests: int
    generated_at: datetime
    approvals: list[ApprovalQueueItem]


@dataclass(slots=True, frozen=True)
class ApprovalStageGateItem:
    """One approval blocker that currently prevents a stage transition."""

    approval: ApprovalRequest
    overdue: bool
    reason: str


@dataclass(slots=True, frozen=True)
class ApprovalStageGate:
    """Stage-gate snapshot derived from explicit deliverable approvals."""

    project_id: UUID
    stage: ProjectStage
    can_advance: bool
    blocking_reasons: list[str]
    blocking_items: list[ApprovalStageGateItem]
    pending_requests: int
    overdue_requests: int


@dataclass(slots=True, frozen=True)
class ApprovalTimelineEntry:
    """One approval request or decision projected onto the Day11 timeline."""

    approval: ApprovalRequest
    event_kind: str
    occurred_at: datetime
    overdue: bool
    decision: ApprovalDecision | None = None


@dataclass(slots=True, frozen=True)
class ApprovalHistoryStep:
    """One replayable step across approval requests, decisions and redo submissions."""

    id: str
    event_kind: str
    occurred_at: datetime
    deliverable_version_number: int
    approval_id: UUID | None
    decision_id: UUID | None
    approval_status: ApprovalStatus | None
    decision_action: ApprovalDecisionAction | None
    actor_name: str | None
    requester_role_code: ProjectRoleCode | None
    author_role_code: ProjectRoleCode | None
    summary: str
    comment: str | None
    request_note: str | None
    requested_changes: list[str]
    highlighted_risks: list[str]
    is_rework: bool


@dataclass(slots=True, frozen=True)
class ApprovalHistory:
    """One deliverable-scoped approval / redo history surfaced by Day12."""

    project_id: UUID
    deliverable_id: UUID
    deliverable_title: str
    deliverable_stage: ProjectStage
    current_version_number: int
    latest_approval_id: UUID | None
    latest_approval_status: ApprovalStatus | None
    rework_status: str
    total_requests: int
    negative_decision_count: int
    rework_round_count: int
    steps: list[ApprovalHistoryStep]


@dataclass(slots=True, frozen=True)
class ApprovalReworkCycle:
    """One negative approval cycle plus its redo / resubmission state."""

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
    comment: str | None
    requested_changes: list[str]
    highlighted_risks: list[str]
    status: str
    latest_approval_id: UUID | None
    latest_approval_status: ApprovalStatus | None
    resubmitted_version_number: int | None
    resubmitted_at: datetime | None


class ApprovalService:
    """Handle approval-request creation, boss decisions and stage gate snapshots."""

    def __init__(
        self,
        *,
        approval_repository: ApprovalRepository,
        deliverable_repository: DeliverableRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self.approval_repository = approval_repository
        self.deliverable_repository = deliverable_repository
        self.project_repository = project_repository

    def request_deliverable_approval(
        self,
        *,
        deliverable_id: UUID,
        requester_role_code: ProjectRoleCode,
        request_note: str | None = None,
        due_in_hours: float = 24,
    ) -> ApprovalDetail:
        """Create one explicit boss-approval request for a deliverable head."""

        deliverable_record = self.deliverable_repository.get_record_by_id(deliverable_id)
        if deliverable_record is None:
            raise ValueError(f"Deliverable not found: {deliverable_id}")
        if not deliverable_record.versions:
            raise ValueError("Deliverable has no persisted version snapshot to approve.")
        if self.project_repository.get_by_id(deliverable_record.deliverable.project_id) is None:
            raise ValueError(
                f"Project not found: {deliverable_record.deliverable.project_id}"
            )
        if due_in_hours < 0:
            raise ValueError("Approval due_in_hours cannot be negative.")

        latest_record = self.approval_repository.get_latest_record_by_deliverable_id(
            deliverable_id
        )
        current_version = deliverable_record.versions[0]

        if (
            latest_record is not None
            and latest_record.approval.deliverable_version_number
            == current_version.version_number
        ):
            if latest_record.approval.status == ApprovalStatus.PENDING_APPROVAL:
                raise ValueError(
                    "Current deliverable version is already waiting for boss approval."
                )

            raise ValueError(
                "Current deliverable version already has an approval decision. "
                "Submit a new deliverable version before requesting approval again."
            )

        requested_at = utc_now()
        approval = ApprovalRequest(
            project_id=deliverable_record.deliverable.project_id,
            deliverable_id=deliverable_record.deliverable.id,
            deliverable_version_id=current_version.id,
            deliverable_title=deliverable_record.deliverable.title,
            deliverable_type=deliverable_record.deliverable.type,
            deliverable_stage=deliverable_record.deliverable.stage,
            deliverable_version_number=current_version.version_number,
            requester_role_code=requester_role_code,
            request_note=request_note,
            status=ApprovalStatus.PENDING_APPROVAL,
            requested_at=requested_at,
            due_at=requested_at + timedelta(hours=due_in_hours),
        )
        persisted_record = self.approval_repository.create_request(approval)
        return self._to_detail(persisted_record)

    def get_project_inbox(self, project_id: UUID) -> ProjectApprovalInbox | None:
        """Return the Day10 approval inbox for one project."""

        if self.project_repository.get_by_id(project_id) is None:
            return None

        records = self.approval_repository.list_records_by_project_id(project_id)
        queue_items = [self._to_queue_item(record) for record in records]
        return ProjectApprovalInbox(
            project_id=project_id,
            total_requests=len(queue_items),
            pending_requests=sum(
                1
                for item in queue_items
                if item.approval.status == ApprovalStatus.PENDING_APPROVAL
            ),
            overdue_requests=sum(1 for item in queue_items if item.overdue),
            completed_requests=sum(
                1
                for item in queue_items
                if item.approval.status != ApprovalStatus.PENDING_APPROVAL
            ),
            generated_at=utc_now(),
            approvals=queue_items,
        )

    def list_project_timeline_entries(
        self,
        project_id: UUID,
    ) -> list[ApprovalTimelineEntry] | None:
        """Flatten approval requests and decisions into timeline-friendly entries."""

        if self.project_repository.get_by_id(project_id) is None:
            return None

        records = self.approval_repository.list_records_by_project_id(project_id)
        timeline_entries: list[ApprovalTimelineEntry] = []
        for record in records:
            overdue = self._is_overdue(record.approval)
            timeline_entries.append(
                ApprovalTimelineEntry(
                    approval=record.approval,
                    event_kind="request",
                    occurred_at=record.approval.requested_at,
                    overdue=overdue,
                )
            )
            for decision in record.decisions:
                timeline_entries.append(
                    ApprovalTimelineEntry(
                        approval=record.approval,
                        event_kind="decision",
                        occurred_at=decision.created_at,
                        overdue=overdue,
                        decision=decision,
                    )
                )

        timeline_entries.sort(key=lambda item: item.occurred_at, reverse=True)
        return timeline_entries

    def get_approval_detail(self, approval_id: UUID) -> ApprovalDetail | None:
        """Return one approval request together with its replayable decision history."""

        record = self.approval_repository.get_record_by_id(approval_id)
        if record is None:
            return None

        return self._to_detail(record)

    def get_approval_history(self, approval_id: UUID) -> ApprovalHistory | None:
        """Return the deliverable-scoped approval / redo history of one approval."""

        record = self.approval_repository.get_record_by_id(approval_id)
        if record is None:
            return None

        deliverable_record = self.deliverable_repository.get_record_by_id(
            record.approval.deliverable_id
        )
        if deliverable_record is None:
            raise ValueError(
                f"Deliverable not found for approval history: {record.approval.deliverable_id}"
            )

        history_records = self.approval_repository.list_records_by_deliverable_id(
            deliverable_record.deliverable.id
        )
        latest_record = history_records[-1] if history_records else None
        rework_cycles = self._build_rework_cycles_for_deliverable(
            deliverable_record=deliverable_record,
            records=history_records,
        )

        return ApprovalHistory(
            project_id=deliverable_record.deliverable.project_id,
            deliverable_id=deliverable_record.deliverable.id,
            deliverable_title=deliverable_record.deliverable.title,
            deliverable_stage=deliverable_record.deliverable.stage,
            current_version_number=deliverable_record.deliverable.current_version_number,
            latest_approval_id=(
                latest_record.approval.id if latest_record is not None else None
            ),
            latest_approval_status=(
                latest_record.approval.status if latest_record is not None else None
            ),
            rework_status=self._resolve_history_rework_status(
                deliverable_record=deliverable_record,
                records=history_records,
            ),
            total_requests=len(history_records),
            negative_decision_count=sum(
                1
                for history_record in history_records
                if self._is_negative_record(history_record)
            ),
            rework_round_count=len(rework_cycles),
            steps=self._build_history_steps(
                deliverable_record=deliverable_record,
                records=history_records,
            ),
        )

    def apply_approval_decision(
        self,
        *,
        approval_id: UUID,
        action: ApprovalDecisionAction,
        actor_name: str = "老板",
        summary: str,
        comment: str | None = None,
        highlighted_risks: list[str] | None = None,
        requested_changes: list[str] | None = None,
    ) -> ApprovalDetail:
        """Persist one structured boss decision and update the approval status."""

        record = self.approval_repository.get_record_by_id(approval_id)
        if record is None:
            raise ValueError(f"Approval request not found: {approval_id}")
        if record.approval.status != ApprovalStatus.PENDING_APPROVAL:
            raise ValueError("Approval request is already closed.")

        decision = ApprovalDecision(
            approval_id=approval_id,
            action=action,
            actor_name=actor_name,
            summary=summary,
            comment=comment,
            highlighted_risks=highlighted_risks or [],
            requested_changes=requested_changes or [],
            created_at=utc_now(),
        )
        updated_record = self.approval_repository.add_decision(
            approval_id=approval_id,
            decision=decision,
            status=map_approval_action_to_status(action),
        )
        return self._to_detail(updated_record)

    def list_project_rework_cycles(
        self,
        project_id: UUID,
    ) -> list[ApprovalReworkCycle] | None:
        """Return all negative approval cycles of one project."""

        if self.project_repository.get_by_id(project_id) is None:
            return None

        deliverable_records = {
            record.deliverable.id: record
            for record in self.deliverable_repository.list_records_by_project_id(project_id)
        }
        records_by_deliverable: dict[UUID, list[ApprovalRecord]] = {}
        for record in self.approval_repository.list_records_by_project_id(project_id):
            records_by_deliverable.setdefault(record.approval.deliverable_id, []).append(record)

        cycles: list[ApprovalReworkCycle] = []
        for deliverable_id, records in records_by_deliverable.items():
            deliverable_record = deliverable_records.get(deliverable_id)
            if deliverable_record is None:
                continue

            cycles.extend(
                self._build_rework_cycles_for_deliverable(
                    deliverable_record=deliverable_record,
                    records=records,
                )
            )

        cycles.sort(key=lambda item: item.decided_at, reverse=True)
        return cycles

    def build_stage_gate(
        self,
        *,
        project_id: UUID,
        stage: ProjectStage,
    ) -> ApprovalStageGate:
        """Return whether current-stage approvals still block the next stage."""

        records = self.approval_repository.list_records_by_project_stage(
            project_id=project_id,
            stage=stage,
        )
        if not records:
            return ApprovalStageGate(
                project_id=project_id,
                stage=stage,
                can_advance=True,
                blocking_reasons=[],
                blocking_items=[],
                pending_requests=0,
                overdue_requests=0,
            )

        latest_records = self._build_latest_records_by_deliverable(records)
        deliverable_records = {
            record.deliverable.id: record
            for record in self.deliverable_repository.list_records_by_project_id(project_id)
        }

        blocking_items: list[ApprovalStageGateItem] = []
        pending_requests = 0
        overdue_requests = 0
        now = utc_now()

        for deliverable_id, latest_record in latest_records.items():
            deliverable_record = deliverable_records.get(deliverable_id)
            if deliverable_record is None:
                continue

            current_version_number = deliverable_record.deliverable.current_version_number
            stale_version = (
                current_version_number > latest_record.approval.deliverable_version_number
            )
            overdue = self._is_overdue(latest_record.approval, reference_time=now)

            if latest_record.approval.status == ApprovalStatus.PENDING_APPROVAL:
                pending_requests += 1
                if overdue:
                    overdue_requests += 1

            reason = self._build_stage_gate_reason(
                approval=latest_record.approval,
                overdue=overdue,
                stale_version=stale_version,
                current_version_number=current_version_number,
            )
            if reason is None:
                continue

            blocking_items.append(
                ApprovalStageGateItem(
                    approval=latest_record.approval,
                    overdue=overdue,
                    reason=reason,
                )
            )

        return ApprovalStageGate(
            project_id=project_id,
            stage=stage,
            can_advance=not blocking_items,
            blocking_reasons=[item.reason for item in blocking_items],
            blocking_items=blocking_items,
            pending_requests=pending_requests,
            overdue_requests=overdue_requests,
        )

    def _build_history_steps(
        self,
        *,
        deliverable_record,
        records: list[ApprovalRecord],
    ) -> list[ApprovalHistoryStep]:
        """Build a chronological approval / redo history for one deliverable."""

        ordered_records = sorted(records, key=lambda item: item.approval.requested_at)
        ordered_versions = sorted(
            deliverable_record.versions,
            key=lambda item: (item.version_number, item.created_at),
        )
        negative_records = [
            record for record in ordered_records if self._is_negative_record(record)
        ]

        steps: list[ApprovalHistoryStep] = []
        for version in ordered_versions:
            if version.version_number <= 1:
                continue

            previous_negative = self._find_previous_negative_record(
                version_number=version.version_number,
                occurred_at=version.created_at,
                negative_records=negative_records,
            )
            if previous_negative is None:
                continue

            steps.append(
                ApprovalHistoryStep(
                    id=f"deliverable-version:{version.id}",
                    event_kind="rework_version_submitted",
                    occurred_at=version.created_at,
                    deliverable_version_number=version.version_number,
                    approval_id=None,
                    decision_id=None,
                    approval_status=None,
                    decision_action=None,
                    actor_name=None,
                    requester_role_code=None,
                    author_role_code=version.author_role_code,
                    summary=version.summary,
                    comment=None,
                    request_note=None,
                    requested_changes=[],
                    highlighted_risks=[],
                    is_rework=True,
                )
            )

        for record in ordered_records:
            previous_negative = self._find_previous_negative_record(
                version_number=record.approval.deliverable_version_number,
                occurred_at=record.approval.requested_at,
                negative_records=negative_records,
            )
            steps.append(
                ApprovalHistoryStep(
                    id=f"approval-request:{record.approval.id}",
                    event_kind="approval_requested",
                    occurred_at=record.approval.requested_at,
                    deliverable_version_number=record.approval.deliverable_version_number,
                    approval_id=record.approval.id,
                    decision_id=None,
                    approval_status=ApprovalStatus.PENDING_APPROVAL,
                    decision_action=None,
                    actor_name=None,
                    requester_role_code=record.approval.requester_role_code,
                    author_role_code=None,
                    summary=record.approval.request_note
                    or "Approval requested for this deliverable version.",
                    comment=None,
                    request_note=record.approval.request_note,
                    requested_changes=[],
                    highlighted_risks=[],
                    is_rework=previous_negative is not None,
                )
            )

            for decision in record.decisions:
                previous_negative_for_decision = self._find_previous_negative_record(
                    version_number=record.approval.deliverable_version_number,
                    occurred_at=decision.created_at,
                    negative_records=negative_records,
                    current_approval_id=record.approval.id,
                )
                steps.append(
                    ApprovalHistoryStep(
                        id=f"approval-decision:{decision.id}",
                        event_kind="approval_decided",
                        occurred_at=decision.created_at,
                        deliverable_version_number=record.approval.deliverable_version_number,
                        approval_id=record.approval.id,
                        decision_id=decision.id,
                        approval_status=map_approval_action_to_status(decision.action),
                        decision_action=decision.action,
                        actor_name=decision.actor_name,
                        requester_role_code=None,
                        author_role_code=None,
                        summary=decision.summary,
                        comment=decision.comment,
                        request_note=None,
                        requested_changes=list(decision.requested_changes),
                        highlighted_risks=list(decision.highlighted_risks),
                        is_rework=previous_negative_for_decision is not None,
                    )
                )

        priority_order = {
            "rework_version_submitted": 0,
            "approval_requested": 1,
            "approval_decided": 2,
        }
        steps.sort(
            key=lambda item: (
                item.occurred_at,
                priority_order.get(item.event_kind, 99),
                item.id,
            )
        )
        return steps

    def _build_rework_cycles_for_deliverable(
        self,
        *,
        deliverable_record,
        records: list[ApprovalRecord],
    ) -> list[ApprovalReworkCycle]:
        """Build all negative approval cycles for one deliverable."""

        ordered_records = sorted(records, key=lambda item: item.approval.requested_at)
        ordered_versions = sorted(
            deliverable_record.versions,
            key=lambda item: (item.version_number, item.created_at),
        )
        cycles: list[ApprovalReworkCycle] = []

        for record in ordered_records:
            latest_decision = self._get_latest_decision(record)
            if latest_decision is None or latest_decision.action not in {
                ApprovalDecisionAction.REJECT,
                ApprovalDecisionAction.REQUEST_CHANGES,
            }:
                continue

            higher_records = [
                item
                for item in ordered_records
                if item.approval.deliverable_version_number
                > record.approval.deliverable_version_number
            ]
            latest_higher_record = higher_records[-1] if higher_records else None

            resubmitted_version = next(
                (
                    version
                    for version in ordered_versions
                    if version.version_number > record.approval.deliverable_version_number
                ),
                None,
            )

            cycle_status = self._resolve_cycle_status(
                deliverable_record=deliverable_record,
                rejected_record=record,
                latest_higher_record=latest_higher_record,
            )

            cycles.append(
                ApprovalReworkCycle(
                    cycle_id=f"{record.approval.id}:{latest_decision.id}",
                    deliverable_id=record.approval.deliverable_id,
                    deliverable_title=record.approval.deliverable_title,
                    deliverable_stage=record.approval.deliverable_stage,
                    approval_id=record.approval.id,
                    deliverable_version_number=record.approval.deliverable_version_number,
                    current_version_number=deliverable_record.deliverable.current_version_number,
                    decided_at=latest_decision.created_at,
                    decision_action=latest_decision.action,
                    summary=latest_decision.summary,
                    comment=latest_decision.comment,
                    requested_changes=list(latest_decision.requested_changes),
                    highlighted_risks=list(latest_decision.highlighted_risks),
                    status=cycle_status,
                    latest_approval_id=(
                        latest_higher_record.approval.id
                        if latest_higher_record is not None
                        else None
                    ),
                    latest_approval_status=(
                        latest_higher_record.approval.status
                        if latest_higher_record is not None
                        else None
                    ),
                    resubmitted_version_number=(
                        resubmitted_version.version_number
                        if resubmitted_version is not None
                        else None
                    ),
                    resubmitted_at=(
                        latest_higher_record.approval.requested_at
                        if latest_higher_record is not None
                        else (
                            resubmitted_version.created_at
                            if resubmitted_version is not None
                            else None
                        )
                    ),
                )
            )

        cycles.sort(key=lambda item: item.decided_at, reverse=True)
        return cycles

    def _to_queue_item(self, record: ApprovalRecord) -> ApprovalQueueItem:
        """Build one approval queue row from a persisted record."""

        latest_decision = record.decisions[-1] if record.decisions else None
        return ApprovalQueueItem(
            approval=record.approval,
            latest_decision=latest_decision,
            overdue=self._is_overdue(record.approval),
        )

    def _to_detail(self, record: ApprovalRecord) -> ApprovalDetail:
        """Convert one repository record into an approval detail object."""

        return ApprovalDetail(
            approval=record.approval,
            decisions=list(record.decisions),
            overdue=self._is_overdue(record.approval),
        )

    @staticmethod
    def _build_latest_records_by_deliverable(
        records: list[ApprovalRecord],
    ) -> dict[UUID, ApprovalRecord]:
        """Keep only the latest approval request per deliverable."""

        latest_records: dict[UUID, ApprovalRecord] = {}
        for record in records:
            current_record = latest_records.get(record.approval.deliverable_id)
            if (
                current_record is None
                or record.approval.requested_at > current_record.approval.requested_at
            ):
                latest_records[record.approval.deliverable_id] = record

        return latest_records

    @staticmethod
    def _get_latest_decision(record: ApprovalRecord) -> ApprovalDecision | None:
        """Return the latest stored decision of one approval record."""

        return record.decisions[-1] if record.decisions else None

    @staticmethod
    def _is_negative_record(record: ApprovalRecord) -> bool:
        """Return whether the latest decision requests redo or rejects the version."""

        latest_decision = ApprovalService._get_latest_decision(record)
        return latest_decision is not None and latest_decision.action in {
            ApprovalDecisionAction.REJECT,
            ApprovalDecisionAction.REQUEST_CHANGES,
        }

    @staticmethod
    def _find_previous_negative_record(
        *,
        version_number: int,
        occurred_at: datetime,
        negative_records: list[ApprovalRecord],
        current_approval_id: UUID | None = None,
    ) -> ApprovalRecord | None:
        """Return the latest negative approval that precedes the given event."""

        previous_negative_records = [
            record
            for record in negative_records
            if record.approval.deliverable_version_number < version_number
            and (
                ApprovalService._get_latest_decision(record) is not None
                and ApprovalService._get_latest_decision(record).created_at <= occurred_at
            )
            and record.approval.id != current_approval_id
        ]
        if not previous_negative_records:
            return None

        previous_negative_records.sort(
            key=lambda item: (
                item.approval.deliverable_version_number,
                ApprovalService._get_latest_decision(item).created_at,
            )
        )
        return previous_negative_records[-1]

    @staticmethod
    def _resolve_cycle_status(
        *,
        deliverable_record,
        rejected_record: ApprovalRecord,
        latest_higher_record: ApprovalRecord | None,
    ) -> str:
        """Resolve the current redo status of one negative approval cycle."""

        rejected_version = rejected_record.approval.deliverable_version_number
        current_version = deliverable_record.deliverable.current_version_number

        if latest_higher_record is None:
            if current_version > rejected_version:
                return "reworking"
            return "rework_required"

        if latest_higher_record.approval.status == ApprovalStatus.APPROVED:
            return "approved_after_rework"
        if latest_higher_record.approval.status == ApprovalStatus.PENDING_APPROVAL:
            return "resubmitted_pending_approval"
        if current_version > latest_higher_record.approval.deliverable_version_number:
            return "reworking"
        return "rework_required"

    @staticmethod
    def _resolve_history_rework_status(
        *,
        deliverable_record,
        records: list[ApprovalRecord],
    ) -> str:
        """Resolve the Day12 redo status shown at the top of the history panel."""

        if not records:
            return "clean"

        latest_record = sorted(records, key=lambda item: item.approval.requested_at)[-1]
        current_version = deliverable_record.deliverable.current_version_number
        has_negative_history = any(
            ApprovalService._is_negative_record(record) for record in records
        )

        if latest_record.approval.status == ApprovalStatus.PENDING_APPROVAL:
            return "resubmitted" if has_negative_history else "pending_approval"
        if latest_record.approval.status == ApprovalStatus.APPROVED:
            return "approved_after_rework" if has_negative_history else "clean"
        if latest_record.approval.status in {
            ApprovalStatus.REJECTED,
            ApprovalStatus.CHANGES_REQUESTED,
        }:
            if current_version > latest_record.approval.deliverable_version_number:
                return "reworking"
            return "rework_required"
        return "clean"

    @staticmethod
    def _is_overdue(
        approval: ApprovalRequest,
        *,
        reference_time: datetime | None = None,
    ) -> bool:
        """Return whether one pending approval has exceeded its due time."""

        effective_reference_time = reference_time or utc_now()
        return (
            approval.status == ApprovalStatus.PENDING_APPROVAL
            and approval.due_at < effective_reference_time
        )

    @staticmethod
    def _build_stage_gate_reason(
        *,
        approval: ApprovalRequest,
        overdue: bool,
        stale_version: bool,
        current_version_number: int,
    ) -> str | None:
        """Choose one stable stage-blocking reason for an approval snapshot."""

        title = approval.deliverable_title

        if stale_version:
            return (
                f"关键交付件《{title}》已更新到 v{current_version_number}，"
                "需要重新提交老板审批后才能推进下一阶段。"
            )

        if approval.status == ApprovalStatus.PENDING_APPROVAL:
            overdue_suffix = "，且已超时" if overdue else ""
            return (
                f"关键交付件《{title}》v{approval.deliverable_version_number} "
                f"仍在等待老板审批{overdue_suffix}。"
            )

        if approval.status == ApprovalStatus.REJECTED:
            return (
                f"关键交付件《{title}》v{approval.deliverable_version_number} "
                "已被老板驳回，需先处理审批结论。"
            )

        if approval.status == ApprovalStatus.CHANGES_REQUESTED:
            return (
                f"关键交付件《{title}》v{approval.deliverable_version_number} "
                "被要求补充信息，需先完成修改并重新审批。"
            )

        return None
