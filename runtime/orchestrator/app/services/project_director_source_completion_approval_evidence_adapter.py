"""Readonly adapter for exact persisted completion-approval evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.domain._base import ensure_utc_datetime
from app.domain.approval import (
    ApprovalDecision,
    ApprovalDecisionAction,
    ApprovalRequest,
    ApprovalStatus,
    map_approval_action_to_status,
)
from app.domain.project_director_source_completion_approval_evidence import (
    ProjectDirectorSourceCompletionApprovalEvidence,
    SOURCE_COMPLETION_APPROVAL_EVIDENCE_KIND,
    SOURCE_COMPLETION_APPROVAL_EVIDENCE_SCHEMA_VERSION,
    SourceCompletionApprovalEvidenceResolution,
)
from app.domain.project_director_source_completion_delivery_evidence import (
    ProjectDirectorSourceCompletionDeliveryEvidence,
)
from app.repositories.approval_repository import ApprovalRepository


_FORBIDDEN_ACTIONS = [
    "no_approval_request_creation_or_mutation",
    "no_approval_decision_creation_or_mutation",
    "no_approval_service_write",
    "no_task_run_or_deliverable_write",
    "no_worker_or_provider_call",
    "no_product_runtime_git_write",
]


class ProjectDirectorSourceCompletionApprovalEvidenceAdapter:
    """Reconstruct one caller-declared approval without latest selection."""

    def __init__(self, *, approval_repository: ApprovalRepository) -> None:
        self._approval_repository = approval_repository

    def resolve_required_completion_approval(
        self,
        *,
        project_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
        completion_delivery: ProjectDirectorSourceCompletionDeliveryEvidence,
        declared_approval_evidence_ids: list[UUID],
        allowed_approval_terminal_results: list[str],
    ) -> SourceCompletionApprovalEvidenceResolution:
        """Resolve one exact approved request and its sole exact decision."""

        allowed_results = list(allowed_approval_terminal_results)
        if (
            allowed_results != [ApprovalStatus.APPROVED.value]
            or len(allowed_results) != len(set(allowed_results))
        ):
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_terminal_result_unsupported"
            )
        if not declared_approval_evidence_ids:
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_evidence_missing"
            )
        if (
            len(declared_approval_evidence_ids) != 2
            or any(not isinstance(value, UUID) for value in declared_approval_evidence_ids)
            or len(set(declared_approval_evidence_ids)) != 2
        ):
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_evidence_id_invalid"
            )

        approval_request_id, approval_decision_id = declared_approval_evidence_ids
        try:
            record = self._approval_repository.get_record_by_id(approval_request_id)
        except (TypeError, ValueError, ValidationError):
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_request_invalid"
            )
        if record is None:
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_request_missing"
            )

        approval = record.approval
        if approval.id != approval_request_id:
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_evidence_conflict"
            )
        if approval.project_id != project_id:
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_project_mismatch"
            )
        if (
            completion_delivery.project_id != project_id
            or completion_delivery.source_task_id != source_task_id
            or completion_delivery.source_run_id != source_run_id
        ):
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_delivery_evidence_required"
            )
        if (
            approval.deliverable_id != completion_delivery.deliverable_id
            or approval.deliverable_version_id is None
            or approval.deliverable_version_id
            != completion_delivery.deliverable_version_id
            or approval.deliverable_version_number != completion_delivery.version_number
            or approval.deliverable_title != completion_delivery.deliverable_title
            or approval.deliverable_type.value != completion_delivery.deliverable_type
            or approval.deliverable_stage.value != completion_delivery.deliverable_stage
        ):
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_delivery_mismatch"
            )

        if not record.decisions:
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_decision_missing"
            )
        if len(record.decisions) != 1:
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_decision_conflict"
            )
        decision = record.decisions[0]
        if decision.id != approval_decision_id:
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_decision_missing"
            )
        if decision.approval_id != approval_request_id:
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_decision_invalid"
            )
        if (
            approval.status != ApprovalStatus.APPROVED
            or decision.action != ApprovalDecisionAction.APPROVE
        ):
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_not_approved"
            )
        if map_approval_action_to_status(decision.action) != approval.status:
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_decision_invalid"
            )
        if (
            approval.decided_at is None
            or approval.decided_at != decision.created_at
            or approval.latest_summary != decision.summary
            or decision.requested_changes
        ):
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_decision_invalid"
            )

        version_created_at = ensure_utc_datetime(completion_delivery.version_created_at)
        requested_at = ensure_utc_datetime(approval.requested_at)
        due_at = ensure_utc_datetime(approval.due_at)
        decided_at = ensure_utc_datetime(approval.decided_at)
        decision_created_at = ensure_utc_datetime(decision.created_at)
        if (
            version_created_at is None
            or requested_at is None
            or due_at is None
            or decided_at is None
            or decision_created_at is None
            or version_created_at > requested_at
            or requested_at > decision_created_at
            or requested_at > due_at
            or decided_at != decision_created_at
        ):
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_timeline_invalid"
            )

        request_note_sha256, request_note_bytes = self._hash_optional_text(
            approval.request_note
        )
        latest_summary_sha256, latest_summary_bytes = self._hash_optional_text(
            approval.latest_summary
        )
        decision_summary_sha256, decision_summary_bytes = self._hash_required_text(
            decision.summary
        )
        decision_comment_sha256, decision_comment_bytes = self._hash_optional_text(
            decision.comment
        )
        highlighted_risks_sha256 = self._fingerprint(decision.highlighted_risks)
        approval_fingerprint = self._build_approval_evidence_fingerprint(
            project_id=project_id,
            source_task_id=source_task_id,
            source_run_id=source_run_id,
            completion_delivery=completion_delivery,
            approval=approval,
            decision=decision,
        )
        try:
            snapshot = ProjectDirectorSourceCompletionApprovalEvidence(
                approval_evidence_kind=SOURCE_COMPLETION_APPROVAL_EVIDENCE_KIND,
                approval_request_id=approval.id,
                approval_decision_id=decision.id,
                approval_evidence_fingerprint=approval_fingerprint,
                project_id=project_id,
                source_task_id=source_task_id,
                source_run_id=source_run_id,
                deliverable_id=completion_delivery.deliverable_id,
                deliverable_version_id=completion_delivery.deliverable_version_id,
                deliverable_version_number=completion_delivery.version_number,
                deliverable_version_fingerprint=(
                    completion_delivery.deliverable_version_fingerprint
                ),
                approval_status=approval.status.value,
                approval_decision_action=decision.action.value,
                requester_role_code=approval.requester_role_code.value,
                decision_actor_name=decision.actor_name,
                requested_at=requested_at,
                due_at=due_at,
                decided_at=decided_at,
                decision_created_at=decision_created_at,
                request_note_sha256=request_note_sha256,
                request_note_bytes=request_note_bytes,
                latest_summary_sha256=latest_summary_sha256,
                latest_summary_bytes=latest_summary_bytes,
                decision_summary_sha256=decision_summary_sha256,
                decision_summary_bytes=decision_summary_bytes,
                decision_comment_sha256=decision_comment_sha256,
                decision_comment_bytes=decision_comment_bytes,
                highlighted_risks_sha256=highlighted_risks_sha256,
                requested_changes_absent=True,
                declared_approval_evidence_ids=list(
                    declared_approval_evidence_ids
                ),
                product_runtime_git_write_allowed=False,
                forbidden_actions=list(_FORBIDDEN_ACTIONS),
            )
        except (TypeError, ValueError, ValidationError):
            return SourceCompletionApprovalEvidenceResolution.blocked(
                "source_completion_approval_fingerprint_mismatch"
            )
        return SourceCompletionApprovalEvidenceResolution(
            status="resolved",
            snapshot=snapshot,
        )

    @classmethod
    def _build_approval_evidence_fingerprint(
        cls,
        *,
        project_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
        completion_delivery: ProjectDirectorSourceCompletionDeliveryEvidence,
        approval: ApprovalRequest,
        decision: ApprovalDecision,
    ) -> str:
        return cls._fingerprint(
            {
                "schema_version": SOURCE_COMPLETION_APPROVAL_EVIDENCE_SCHEMA_VERSION,
                "project_id": project_id,
                "source_task_id": source_task_id,
                "source_run_id": source_run_id,
                "deliverable_id": completion_delivery.deliverable_id,
                "deliverable_version_id": completion_delivery.deliverable_version_id,
                "deliverable_version_number": completion_delivery.version_number,
                "deliverable_version_fingerprint": (
                    completion_delivery.deliverable_version_fingerprint
                ),
                "approval_request": approval,
                "approval_decision": decision,
            }
        )

    @staticmethod
    def _hash_optional_text(value: str | None) -> tuple[str | None, int]:
        if value is None:
            return None, 0
        return ProjectDirectorSourceCompletionApprovalEvidenceAdapter._hash_required_text(
            value
        )

    @staticmethod
    def _hash_required_text(value: str) -> tuple[str, int]:
        encoded = value.encode("utf-8")
        return hashlib.sha256(encoded).hexdigest(), len(encoded)

    @classmethod
    def _fingerprint(cls, payload: Any) -> str:
        canonical = json.dumps(
            cls._canonicalize(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _canonicalize(cls, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return cls._canonicalize(value.model_dump(mode="python"))
        if isinstance(value, dict):
            return {str(key): cls._canonicalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._canonicalize(item) for item in value]
        if isinstance(value, UUID):
            return str(value).lower()
        if isinstance(value, datetime):
            normalized = ensure_utc_datetime(value)
            if normalized is None:
                raise ValueError("fingerprint datetime is required")
            return normalized.isoformat().replace("+00:00", "Z")
        if isinstance(value, Enum):
            return value.value
        return value


__all__ = ("ProjectDirectorSourceCompletionApprovalEvidenceAdapter",)
