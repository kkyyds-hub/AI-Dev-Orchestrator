"""Persistence helpers for V3 Day10 approval requests and decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db_tables import ApprovalDecisionTable, ApprovalRequestTable
from app.domain._base import ensure_utc_datetime
from app.domain.approval import ApprovalDecision, ApprovalRequest, ApprovalStatus
from app.domain.project import ProjectStage


@dataclass(slots=True, frozen=True)
class ApprovalRecord:
    """One approval request together with its ordered decision history."""

    approval: ApprovalRequest
    decisions: list[ApprovalDecision]


class ApprovalRepository:
    """Encapsulate approval-related database operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_request(self, approval: ApprovalRequest) -> ApprovalRecord:
        """Persist one new approval request and return the stored record."""

        approval_row = ApprovalRequestTable(
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
        )

        self.session.add(approval_row)
        self.session.commit()

        persisted_record = self.get_record_by_id(approval.id)
        if persisted_record is None:
            raise ValueError(
                f"Approval request not found after persistence: {approval.id}"
            )

        return persisted_record

    def add_decision(
        self,
        *,
        approval_id: UUID,
        decision: ApprovalDecision,
        status: ApprovalStatus,
    ) -> ApprovalRecord:
        """Append one structured decision and close/update the approval request."""

        approval_row = self.session.get(ApprovalRequestTable, approval_id)
        if approval_row is None:
            raise ValueError(f"Approval request not found: {approval_id}")

        approval_row.status = status
        approval_row.latest_summary = decision.summary
        approval_row.decided_at = decision.created_at
        approval_row.decisions.append(self._build_decision_row(decision))
        self.session.commit()

        persisted_record = self.get_record_by_id(approval_id)
        if persisted_record is None:
            raise ValueError(
                f"Approval request not found after decision append: {approval_id}"
            )

        return persisted_record

    def get_record_by_id(self, approval_id: UUID) -> ApprovalRecord | None:
        """Return one approval request plus its structured decision history."""

        statement = (
            select(ApprovalRequestTable)
            .options(selectinload(ApprovalRequestTable.decisions))
            .where(ApprovalRequestTable.id == approval_id)
        )
        approval_row = self.session.execute(statement).scalar_one_or_none()
        if approval_row is None:
            return None

        return self._to_record(approval_row)

    def get_latest_record_by_deliverable_id(
        self,
        deliverable_id: UUID,
    ) -> ApprovalRecord | None:
        """Return the latest approval request stored for one deliverable."""

        statement = (
            select(ApprovalRequestTable)
            .options(selectinload(ApprovalRequestTable.decisions))
            .where(ApprovalRequestTable.deliverable_id == deliverable_id)
            .order_by(ApprovalRequestTable.requested_at.desc())
        )
        approval_row = self.session.execute(statement).scalars().first()
        if approval_row is None:
            return None

        return self._to_record(approval_row)

    def list_records_by_project_id(self, project_id: UUID) -> list[ApprovalRecord]:
        """Return all approval requests of one project ordered by latest request time."""

        statement = (
            select(ApprovalRequestTable)
            .options(selectinload(ApprovalRequestTable.decisions))
            .where(ApprovalRequestTable.project_id == project_id)
            .order_by(ApprovalRequestTable.requested_at.desc())
        )
        approval_rows = self.session.execute(statement).scalars().all()
        return [self._to_record(approval_row) for approval_row in approval_rows]

    def list_records_by_deliverable_id(
        self,
        deliverable_id: UUID,
    ) -> list[ApprovalRecord]:
        """Return all approval requests of one deliverable ordered by request time."""

        statement = (
            select(ApprovalRequestTable)
            .options(selectinload(ApprovalRequestTable.decisions))
            .where(ApprovalRequestTable.deliverable_id == deliverable_id)
            .order_by(ApprovalRequestTable.requested_at.asc())
        )
        approval_rows = self.session.execute(statement).scalars().all()
        return [self._to_record(approval_row) for approval_row in approval_rows]

    def list_records_by_project_stage(
        self,
        *,
        project_id: UUID,
        stage: ProjectStage,
    ) -> list[ApprovalRecord]:
        """Return approval requests of one project stage ordered by request time."""

        statement = (
            select(ApprovalRequestTable)
            .options(selectinload(ApprovalRequestTable.decisions))
            .where(
                ApprovalRequestTable.project_id == project_id,
                ApprovalRequestTable.deliverable_stage == stage,
            )
            .order_by(ApprovalRequestTable.requested_at.desc())
        )
        approval_rows = self.session.execute(statement).scalars().all()
        return [self._to_record(approval_row) for approval_row in approval_rows]

    @staticmethod
    def _build_decision_row(decision: ApprovalDecision) -> ApprovalDecisionTable:
        """Convert one domain decision into its ORM row."""

        return ApprovalDecisionTable(
            id=decision.id,
            approval_id=decision.approval_id,
            action=decision.action,
            actor_name=decision.actor_name,
            summary=decision.summary,
            comment=decision.comment,
            highlighted_risks_json=ApprovalRepository._serialize_string_list(
                decision.highlighted_risks
            ),
            requested_changes_json=ApprovalRepository._serialize_string_list(
                decision.requested_changes
            ),
            created_at=decision.created_at,
        )

    def _to_record(self, approval_row: ApprovalRequestTable) -> ApprovalRecord:
        """Convert one ORM row bundle into domain objects."""

        decisions = sorted(
            (self._to_decision(decision_row) for decision_row in approval_row.decisions),
            key=lambda item: item.created_at,
        )
        return ApprovalRecord(
            approval=self._to_approval(approval_row),
            decisions=decisions,
        )

    @staticmethod
    def _to_approval(approval_row: ApprovalRequestTable) -> ApprovalRequest:
        """Convert one approval request row into its domain model."""

        return ApprovalRequest(
            id=approval_row.id,
            project_id=approval_row.project_id,
            deliverable_id=approval_row.deliverable_id,
            deliverable_version_id=approval_row.deliverable_version_id,
            deliverable_title=approval_row.deliverable_title,
            deliverable_type=approval_row.deliverable_type,
            deliverable_stage=approval_row.deliverable_stage,
            deliverable_version_number=approval_row.deliverable_version_number,
            requester_role_code=approval_row.requester_role_code,
            request_note=approval_row.request_note,
            status=approval_row.status,
            requested_at=ensure_utc_datetime(approval_row.requested_at),
            due_at=ensure_utc_datetime(approval_row.due_at),
            decided_at=ensure_utc_datetime(approval_row.decided_at),
            latest_summary=approval_row.latest_summary,
        )

    @staticmethod
    def _to_decision(decision_row: ApprovalDecisionTable) -> ApprovalDecision:
        """Convert one stored decision row into its domain model."""

        return ApprovalDecision(
            id=decision_row.id,
            approval_id=decision_row.approval_id,
            action=decision_row.action,
            actor_name=decision_row.actor_name,
            summary=decision_row.summary,
            comment=decision_row.comment,
            highlighted_risks=ApprovalRepository._deserialize_string_list(
                decision_row.highlighted_risks_json
            ),
            requested_changes=ApprovalRepository._deserialize_string_list(
                decision_row.requested_changes_json
            ),
            created_at=ensure_utc_datetime(decision_row.created_at),
        )

    @staticmethod
    def _serialize_string_list(items: list[str]) -> str:
        """Store one string list as JSON text in SQLite."""

        return json.dumps(items, ensure_ascii=False)

    @staticmethod
    def _deserialize_string_list(raw_value: str | None) -> list[str]:
        """Read one JSON-encoded string list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for item in decoded_value:
            if not isinstance(item, str):
                continue

            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_items:
                continue

            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)

        return normalized_items
