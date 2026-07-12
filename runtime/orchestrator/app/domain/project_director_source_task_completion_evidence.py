"""Immutable P24 source-Task completion evidence contracts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime
from app.domain.project_director_source_execution_authority import (
    SourceExecutionAuthorityKind,
)


SOURCE_TASK_COMPLETION_EVIDENCE_SCHEMA_VERSION = (
    "p24-b-source-task-completion-evidence.v1"
)

SourceTaskCompletionAxisRequirement = Literal["required", "not_required"]
SourceTaskCompletionAxisSatisfactionStatus = Literal[
    "satisfied",
    "not_required_by_policy",
]
SourceTaskCompletionEvidenceStatus = Literal[
    "evidence_recorded",
    "evidence_replayed",
    "evidence_revalidated",
    "blocked",
]
SourceTaskCompletionBlockedReason = Literal[
    "source_completion_authority_missing",
    "source_completion_authority_invalid",
    "source_completion_authority_task_run_mismatch",
    "source_completion_policy_missing",
    "source_completion_policy_invalid",
    "source_completion_policy_task_mismatch",
    "source_completion_task_missing",
    "source_completion_run_missing",
    "source_completion_task_run_mismatch",
    "source_completion_task_not_completed",
    "source_completion_task_human_state_pending",
    "source_completion_task_paused",
    "source_completion_run_not_succeeded",
    "source_completion_run_not_finished",
    "source_completion_run_quality_gate_missing",
    "source_completion_run_quality_gate_failed",
    "source_completion_run_failure_category_present",
    "source_completion_terminal_state_mismatch",
    "source_completion_quality_gate_missing",
    "source_completion_quality_gate_failed",
    "source_completion_quality_gate_mismatch",
    "source_completion_agent_session_missing",
    "source_completion_agent_session_mismatch",
    "source_completion_agent_session_conflict",
    "source_completion_review_evidence_adapter_unavailable",
    "source_completion_verification_evidence_kind_unsupported",
    "source_completion_delivery_evidence_adapter_unavailable",
    "source_completion_approval_evidence_adapter_unavailable",
    "source_completion_axis_unsatisfied",
    "source_completion_evidence_missing",
    "source_completion_evidence_schema_mismatch",
    "source_completion_evidence_fingerprint_mismatch",
    "source_completion_evidence_replay_conflict",
    "source_completion_evidence_lineage_invalid",
    "source_completion_git_boundary_violation",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorSourceTaskCompletionEvidence(DomainModel):
    """Append-only certificate for one exact successful source Task and Run."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["p24-b-source-task-completion-evidence.v1"] = (
        SOURCE_TASK_COMPLETION_EVIDENCE_SCHEMA_VERSION
    )

    source_completion_evidence_id: UUID
    source_completion_evidence_fingerprint: str = Field(min_length=64, max_length=64)
    source_completion_evidence_replay_key: str = Field(min_length=64, max_length=64)
    created_at: datetime

    session_id: UUID
    project_id: UUID
    plan_version_id: UUID
    plan_version_no: int = Field(ge=1)
    task_creation_record_id: UUID

    source_task_id: UUID
    source_success_run_id: UUID

    source_execution_authority_kind: SourceExecutionAuthorityKind
    source_execution_authority_id: UUID
    source_execution_authority_fingerprint: str = Field(min_length=64, max_length=64)
    source_reservation_id: UUID
    source_claim_id: UUID
    source_outcome_id: UUID
    source_outcome_fingerprint: str = Field(min_length=64, max_length=64)

    completion_policy_id: UUID
    completion_policy_version: int = Field(ge=1)
    completion_policy_fingerprint: str = Field(min_length=64, max_length=64)

    terminal_task_status: Literal["completed"] = "completed"
    terminal_task_human_status: Literal["none", "resolved"]
    task_paused_reason_absent: Literal[True] = True
    terminal_run_status: Literal["succeeded"] = "succeeded"
    run_finished_at: datetime
    run_quality_gate_passed: Literal[True] = True
    run_failure_category_absent: Literal[True] = True
    quality_gate_passed: Literal[True] = True

    authority_task_status_after: str = Field(min_length=1, max_length=100)
    authority_run_status_after: str = Field(min_length=1, max_length=100)
    authority_agent_session_id: UUID | None = None
    authority_agent_session_status: str | None = Field(default=None, max_length=100)
    agent_session_phase: str | None = Field(default=None, max_length=100)
    runtime_terminal: Literal[True] = True

    review_requirement: SourceTaskCompletionAxisRequirement
    review_satisfaction_status: SourceTaskCompletionAxisSatisfactionStatus
    review_evidence_kind: str = Field(min_length=1, max_length=100)
    review_evidence_ids: list[UUID]

    verification_requirement: SourceTaskCompletionAxisRequirement
    verification_satisfaction_status: SourceTaskCompletionAxisSatisfactionStatus
    verification_evidence_kind: str = Field(min_length=1, max_length=100)
    verification_evidence_ids: list[UUID]

    delivery_requirement: SourceTaskCompletionAxisRequirement
    delivery_satisfaction_status: SourceTaskCompletionAxisSatisfactionStatus
    delivery_evidence_kind: str = Field(min_length=1, max_length=100)
    delivery_evidence_ids: list[UUID]

    approval_requirement: SourceTaskCompletionAxisRequirement
    approval_satisfaction_status: SourceTaskCompletionAxisSatisfactionStatus
    approval_evidence_kind: str = Field(min_length=1, max_length=100)
    approval_evidence_ids: list[UUID]

    completion_status: Literal["completed"] = "completed"
    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: list[str]

    @field_validator("created_at", "run_finished_at", mode="after")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("completion evidence datetime is required")
        return normalized

    @field_validator(
        "source_completion_evidence_fingerprint",
        "source_completion_evidence_replay_key",
        "source_execution_authority_fingerprint",
        "source_outcome_fingerprint",
        "completion_policy_fingerprint",
        mode="after",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("completion evidence hashes must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_completion_evidence(self) -> "ProjectDirectorSourceTaskCompletionEvidence":
        axis_values = (
            (
                self.review_requirement,
                self.review_satisfaction_status,
                self.review_evidence_kind,
                self.review_evidence_ids,
            ),
            (
                self.verification_requirement,
                self.verification_satisfaction_status,
                self.verification_evidence_kind,
                self.verification_evidence_ids,
            ),
            (
                self.delivery_requirement,
                self.delivery_satisfaction_status,
                self.delivery_evidence_kind,
                self.delivery_evidence_ids,
            ),
            (
                self.approval_requirement,
                self.approval_satisfaction_status,
                self.approval_evidence_kind,
                self.approval_evidence_ids,
            ),
        )
        for requirement, status, evidence_kind, evidence_ids in axis_values:
            if not evidence_ids or len(evidence_ids) != len(set(evidence_ids)):
                raise ValueError("completion axes require unique non-empty evidence IDs")
            if requirement == "not_required":
                if (
                    status != "not_required_by_policy"
                    or evidence_kind != "human_owner_policy_decision"
                ):
                    raise ValueError("not-required axes require owner policy evidence")
            elif status != "satisfied":
                raise ValueError("required axes must be satisfied")
        if self.authority_agent_session_id is None:
            if (
                self.authority_agent_session_status is not None
                or self.agent_session_phase is not None
            ):
                raise ValueError("agent-session facts require an exact session ID")
        elif (
            not self.authority_agent_session_status
            or not self.agent_session_phase
        ):
            raise ValueError("agent-session ID requires durable terminal facts")
        if (
            not self.forbidden_actions
            or len(self.forbidden_actions) != len(set(self.forbidden_actions))
        ):
            raise ValueError("completion evidence forbidden actions must be unique")
        return self


class SourceTaskCompletionEvidenceResult(DomainModel):
    """Fail-closed result of evidence issuance, replay, or revalidation."""

    model_config = ConfigDict(frozen=True)

    status: SourceTaskCompletionEvidenceStatus
    evidence: ProjectDirectorSourceTaskCompletionEvidence | None = None
    blocked_reasons: list[SourceTaskCompletionBlockedReason] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> "SourceTaskCompletionEvidenceResult":
        if self.status == "blocked":
            if self.evidence is not None or not self.blocked_reasons:
                raise ValueError("blocked completion result requires reasons and no evidence")
        elif self.evidence is None or self.blocked_reasons:
            raise ValueError("successful completion result requires unblocked evidence")
        if len(self.blocked_reasons) != len(set(self.blocked_reasons)):
            raise ValueError("completion blocked reasons must be unique")
        return self

    @classmethod
    def blocked(
        cls,
        *reasons: SourceTaskCompletionBlockedReason,
    ) -> "SourceTaskCompletionEvidenceResult":
        return cls(
            status="blocked",
            evidence=None,
            blocked_reasons=list(dict.fromkeys(reasons)),
        )


__all__ = (
    "ProjectDirectorSourceTaskCompletionEvidence",
    "SOURCE_TASK_COMPLETION_EVIDENCE_SCHEMA_VERSION",
    "SourceTaskCompletionBlockedReason",
    "SourceTaskCompletionEvidenceResult",
)
