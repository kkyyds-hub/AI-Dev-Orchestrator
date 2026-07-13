"""Immutable P24 completion-approval evidence for one exact version."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime


SOURCE_COMPLETION_APPROVAL_EVIDENCE_SCHEMA_VERSION = (
    "p24-b-source-completion-approval-evidence.v1"
)
SOURCE_COMPLETION_APPROVAL_EVIDENCE_KIND = "approved_deliverable_version"

SourceCompletionApprovalBlockedReason = Literal[
    "source_completion_approval_evidence_missing",
    "source_completion_approval_evidence_id_invalid",
    "source_completion_approval_evidence_conflict",
    "source_completion_approval_terminal_result_unsupported",
    "source_completion_approval_delivery_evidence_required",
    "source_completion_approval_request_missing",
    "source_completion_approval_request_invalid",
    "source_completion_approval_project_mismatch",
    "source_completion_approval_delivery_mismatch",
    "source_completion_approval_decision_missing",
    "source_completion_approval_decision_conflict",
    "source_completion_approval_decision_invalid",
    "source_completion_approval_not_approved",
    "source_completion_approval_timeline_invalid",
    "source_completion_approval_fingerprint_mismatch",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorSourceCompletionApprovalEvidence(DomainModel):
    """Readonly snapshot reconstructed from one exact approval and decision."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[
        "p24-b-source-completion-approval-evidence.v1"
    ] = SOURCE_COMPLETION_APPROVAL_EVIDENCE_SCHEMA_VERSION
    approval_evidence_kind: Literal["approved_deliverable_version"] = (
        SOURCE_COMPLETION_APPROVAL_EVIDENCE_KIND
    )

    approval_request_id: UUID
    approval_decision_id: UUID
    approval_evidence_fingerprint: str = Field(min_length=64, max_length=64)

    project_id: UUID
    source_task_id: UUID
    source_run_id: UUID

    deliverable_id: UUID
    deliverable_version_id: UUID
    deliverable_version_number: int = Field(ge=1)
    deliverable_version_fingerprint: str = Field(min_length=64, max_length=64)

    approval_status: Literal["approved"] = "approved"
    approval_decision_action: Literal["approve"] = "approve"
    requester_role_code: str = Field(min_length=1, max_length=100)
    decision_actor_name: str = Field(min_length=1, max_length=100)

    requested_at: datetime
    due_at: datetime
    decided_at: datetime
    decision_created_at: datetime

    request_note_sha256: str | None = Field(default=None, max_length=64)
    request_note_bytes: int = Field(ge=0)
    latest_summary_sha256: str | None = Field(default=None, max_length=64)
    latest_summary_bytes: int = Field(ge=0)
    decision_summary_sha256: str = Field(min_length=64, max_length=64)
    decision_summary_bytes: int = Field(ge=1)
    decision_comment_sha256: str | None = Field(default=None, max_length=64)
    decision_comment_bytes: int = Field(ge=0)
    highlighted_risks_sha256: str = Field(min_length=64, max_length=64)
    requested_changes_absent: Literal[True] = True

    declared_approval_evidence_ids: list[UUID]
    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: list[str]

    @field_validator(
        "approval_evidence_fingerprint",
        "deliverable_version_fingerprint",
        "decision_summary_sha256",
        "highlighted_risks_sha256",
        mode="after",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("approval evidence hashes must be lowercase SHA-256")
        return value

    @field_validator(
        "request_note_sha256",
        "latest_summary_sha256",
        "decision_comment_sha256",
        mode="after",
    )
    @classmethod
    def require_optional_sha256(cls, value: str | None) -> str | None:
        if value is not None and not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("approval evidence hashes must be lowercase SHA-256")
        return value

    @field_validator(
        "requested_at",
        "due_at",
        "decided_at",
        "decision_created_at",
        mode="after",
    )
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("approval evidence datetime is required")
        return normalized

    @model_validator(mode="after")
    def validate_approval_evidence(
        self,
    ) -> "ProjectDirectorSourceCompletionApprovalEvidence":
        if self.declared_approval_evidence_ids != [
            self.approval_request_id,
            self.approval_decision_id,
        ]:
            raise ValueError("approval evidence IDs must preserve exact declared order")
        if self.approval_request_id == self.approval_decision_id:
            raise ValueError("approval evidence IDs must be distinct")
        optional_hash_pairs = (
            (self.request_note_sha256, self.request_note_bytes),
            (self.latest_summary_sha256, self.latest_summary_bytes),
            (self.decision_comment_sha256, self.decision_comment_bytes),
        )
        if any((digest is None) != (size == 0) for digest, size in optional_hash_pairs):
            raise ValueError("optional approval text hashes must match byte counts")
        if self.decided_at != self.decision_created_at:
            raise ValueError("approval decision timestamps must match")
        if self.requested_at > self.due_at or self.requested_at > self.decided_at:
            raise ValueError("approval evidence timeline is invalid")
        if (
            not self.forbidden_actions
            or len(self.forbidden_actions) != len(set(self.forbidden_actions))
        ):
            raise ValueError("approval evidence forbidden actions must be unique")
        return self


class SourceCompletionApprovalEvidenceResolution(DomainModel):
    """Fail-closed result for exact declared completion-approval IDs."""

    model_config = ConfigDict(frozen=True)

    status: Literal["resolved", "blocked"]
    snapshot: ProjectDirectorSourceCompletionApprovalEvidence | None = None
    blocked_reasons: list[SourceCompletionApprovalBlockedReason] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_resolution(self) -> "SourceCompletionApprovalEvidenceResolution":
        if self.status == "resolved":
            if self.snapshot is None or self.blocked_reasons:
                raise ValueError("resolved approval evidence requires only a snapshot")
        elif self.snapshot is not None or not self.blocked_reasons:
            raise ValueError("blocked approval evidence requires only stable reasons")
        if len(self.blocked_reasons) != len(set(self.blocked_reasons)):
            raise ValueError("completion approval blocked reasons must be unique")
        return self

    @classmethod
    def blocked(
        cls,
        *reasons: SourceCompletionApprovalBlockedReason,
    ) -> "SourceCompletionApprovalEvidenceResolution":
        return cls(
            status="blocked",
            snapshot=None,
            blocked_reasons=list(dict.fromkeys(reasons)),
        )


__all__ = (
    "ProjectDirectorSourceCompletionApprovalEvidence",
    "SOURCE_COMPLETION_APPROVAL_EVIDENCE_KIND",
    "SOURCE_COMPLETION_APPROVAL_EVIDENCE_SCHEMA_VERSION",
    "SourceCompletionApprovalBlockedReason",
    "SourceCompletionApprovalEvidenceResolution",
)
