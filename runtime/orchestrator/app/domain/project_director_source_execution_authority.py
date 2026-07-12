"""Generic persisted execution-authority contracts for Project Director."""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel


SOURCE_EXECUTION_AUTHORITY_SCHEMA_VERSION = "p24-source-execution-authority.v1"

SourceExecutionAuthorityKind = Literal[
    "p23_protected_transition",
    "p24_cross_task_continuation",
]
SourceExecutionAuthorityBlockedReason = Literal[
    "source_execution_authority_missing",
    "source_execution_authority_kind_unsupported",
    "source_execution_authority_adapter_unavailable",
    "source_execution_authority_schema_mismatch",
    "source_execution_authority_fingerprint_mismatch",
    "source_execution_authority_task_run_mismatch",
    "source_execution_authority_lineage_invalid",
    "source_execution_authority_outcome_not_returned",
    "source_execution_authority_result_contract_invalid",
    "source_execution_authority_recovery_required",
    "source_execution_authority_blocked",
    "source_execution_authority_git_boundary_violation",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SourceExecutionAuthoritySnapshot(DomainModel):
    """Immutable, authority-neutral proof of one exact persisted invocation."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["p24-source-execution-authority.v1"] = (
        SOURCE_EXECUTION_AUTHORITY_SCHEMA_VERSION
    )

    authority_kind: SourceExecutionAuthorityKind
    authority_id: UUID
    authority_fingerprint: str = Field(min_length=64, max_length=64)

    reservation_id: UUID
    reservation_fingerprint: str = Field(min_length=64, max_length=64)
    claim_id: UUID
    claim_fingerprint: str = Field(min_length=64, max_length=64)
    outcome_id: UUID
    outcome_schema_version: str = Field(min_length=1, max_length=100)
    outcome_fingerprint: str = Field(min_length=64, max_length=64)

    session_id: UUID
    project_id: UUID
    task_id: UUID
    run_id: UUID

    outcome_status: Literal["returned"]
    worker_result_contract_valid: bool
    recovery_required: bool
    blocked_reasons: list[str] = Field(default_factory=list)
    worker_reported_git_write_activity: bool
    product_runtime_git_write_allowed: bool

    source_review_id: UUID | None = None
    source_review_outcome: str | None = Field(default=None, max_length=100)
    source_transition_evidence_ids: list[UUID]

    @field_validator(
        "authority_fingerprint",
        "reservation_fingerprint",
        "claim_fingerprint",
        "outcome_fingerprint",
        mode="after",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("execution authority fingerprints must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_trusted_snapshot(self) -> "SourceExecutionAuthoritySnapshot":
        lineage_ids = (
            self.authority_id,
            self.reservation_id,
            self.claim_id,
            self.outcome_id,
        )
        if len(set(lineage_ids)) != len(lineage_ids):
            raise ValueError("execution authority lineage records must be distinct")
        if (
            not self.source_transition_evidence_ids
            or len(set(self.source_transition_evidence_ids))
            != len(self.source_transition_evidence_ids)
        ):
            raise ValueError("transition evidence IDs must be non-empty and unique")
        if self.source_review_id is None and self.source_review_outcome is not None:
            raise ValueError("review outcome requires an exact source review ID")
        if (
            not self.worker_result_contract_valid
            or self.recovery_required
            or self.blocked_reasons
            or self.worker_reported_git_write_activity
            or self.product_runtime_git_write_allowed
        ):
            raise ValueError("execution authority snapshot is not a trusted success")
        return self


class SourceExecutionAuthorityResolution(DomainModel):
    """Fail-closed result of resolving one persisted execution authority."""

    model_config = ConfigDict(frozen=True)

    snapshot: SourceExecutionAuthoritySnapshot | None = None
    resolved: bool = False
    blocked_reasons: list[SourceExecutionAuthorityBlockedReason] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_resolution(self) -> "SourceExecutionAuthorityResolution":
        if self.resolved:
            if self.snapshot is None or self.blocked_reasons:
                raise ValueError("resolved authority requires one unblocked snapshot")
        elif self.snapshot is not None or not self.blocked_reasons:
            raise ValueError("blocked authority requires reasons and no snapshot")
        if len(set(self.blocked_reasons)) != len(self.blocked_reasons):
            raise ValueError("authority blocked reasons must be unique")
        return self

    @classmethod
    def success(
        cls,
        snapshot: SourceExecutionAuthoritySnapshot,
    ) -> "SourceExecutionAuthorityResolution":
        return cls(snapshot=snapshot, resolved=True, blocked_reasons=[])

    @classmethod
    def blocked(
        cls,
        *reasons: SourceExecutionAuthorityBlockedReason,
    ) -> "SourceExecutionAuthorityResolution":
        return cls(
            snapshot=None,
            resolved=False,
            blocked_reasons=list(dict.fromkeys(reasons)),
        )


__all__ = (
    "SOURCE_EXECUTION_AUTHORITY_SCHEMA_VERSION",
    "SourceExecutionAuthorityBlockedReason",
    "SourceExecutionAuthorityKind",
    "SourceExecutionAuthorityResolution",
    "SourceExecutionAuthoritySnapshot",
)
