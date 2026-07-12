"""Project Director P23-D2-B2 exact Worker invocation evidence contracts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


ProtectedTransitionWorkerInvocationClaimStatus = Literal["claimed"]
ProtectedTransitionWorkerInvocationOutcomeStatus = Literal[
    "not_invoked",
    "returned",
    "raised",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorProtectedTransitionWorkerInvocationClaimResult(DomainModel):
    """Unique durable claim consumed before the exact Worker call."""

    claim_status: ProtectedTransitionWorkerInvocationClaimStatus
    claim_id: UUID
    claim_fingerprint: str = Field(min_length=64, max_length=64)
    claim_token: str = Field(min_length=1, max_length=200)

    session_id: UUID
    project_id: UUID
    source_task_id: UUID
    target_task_id: UUID
    run_id: UUID

    source_reservation_message_id: UUID
    source_reservation_id: UUID
    source_reservation_fingerprint: str = Field(min_length=64, max_length=64)
    source_reservation_token: str = Field(min_length=1, max_length=200)
    source_consumption_message_id: UUID
    source_consumption_fingerprint: str = Field(min_length=64, max_length=64)
    source_preflight_message_id: UUID
    source_intent_message_id: UUID
    source_freshness_message_id: UUID

    disposition_type: Literal["AUTO_CONTINUE", "AUTO_REWORK"]
    dispatch_kind: Literal["auto_continue", "auto_rework"]
    target_task_strategy: Literal["source_task_continue", "source_task_rework"]

    review_result_fingerprint: str = Field(min_length=64, max_length=64)
    review_semantic_fingerprint: str = Field(min_length=64, max_length=64)
    current_freshness_fingerprint: str = Field(min_length=64, max_length=64)
    current_diff_sha256: str = Field(min_length=64, max_length=64)
    current_scope_paths: list[str]
    workspace_path: str = Field(min_length=1, max_length=2_000)
    workspace_path_within_root: bool

    task_status_before: str
    run_status_before: str
    agent_session_absent: bool

    budget_guard_allowed: bool
    budget_pressure_level: str
    budget_strategy_action: str
    budget_strategy_code: str
    budget_policy_source: str
    retry_limit_reached: bool

    rework_attempt_index: int = Field(ge=0)
    rework_attempt_limit: int = Field(ge=1)

    worker_invocation_claimed: bool
    worker_called: bool = False
    agent_session_created: bool = False
    runtime_started: bool = False
    continuation_started: bool = False
    rework_started: bool = False
    task_created: bool = False
    run_created: bool = False
    task_claimed_in_this_phase: bool = False
    task_routed_in_this_phase: bool = False
    product_runtime_git_write_allowed: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", mode="after")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value) or utc_now()

    @field_validator(
        "claim_fingerprint",
        "source_reservation_fingerprint",
        "source_consumption_fingerprint",
        "review_result_fingerprint",
        "review_semantic_fingerprint",
        "current_freshness_fingerprint",
        "current_diff_sha256",
        mode="after",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.match(value):
            raise ValueError("claim fingerprints must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_claim(self) -> "ProjectDirectorProtectedTransitionWorkerInvocationClaimResult":
        if (
            self.source_reservation_id != self.source_reservation_message_id
            or self.target_task_id != self.source_task_id
        ):
            raise ValueError("claim must bind the exact reservation and source Task")
        expected_dispatch = {
            "AUTO_CONTINUE": ("auto_continue", "source_task_continue"),
            "AUTO_REWORK": ("auto_rework", "source_task_rework"),
        }[self.disposition_type]
        if (self.dispatch_kind, self.target_task_strategy) != expected_dispatch:
            raise ValueError("claim disposition mapping is invalid")
        forbidden_true = (
            self.worker_called,
            self.agent_session_created,
            self.runtime_started,
            self.continuation_started,
            self.rework_started,
            self.task_created,
            self.run_created,
            self.task_claimed_in_this_phase,
            self.task_routed_in_this_phase,
            self.product_runtime_git_write_allowed,
        )
        if (
            self.task_status_before != "running"
            or self.run_status_before != "running"
            or not self.agent_session_absent
            or not self.budget_guard_allowed
            or self.retry_limit_reached
            or not self.worker_invocation_claimed
            or any(forbidden_true)
            or not self.current_scope_paths
            or not self.workspace_path_within_root
        ):
            raise ValueError("claimed state violates exact invocation eligibility")
        return self


class ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult(DomainModel):
    """Durable normalized outcome for one consumed invocation claim."""

    outcome_status: ProtectedTransitionWorkerInvocationOutcomeStatus
    outcome_id: UUID
    outcome_fingerprint: str = Field(min_length=64, max_length=64)
    session_id: UUID
    project_id: UUID
    source_task_id: UUID
    run_id: UUID

    source_claim_message_id: UUID
    source_claim_id: UUID
    source_claim_fingerprint: str = Field(min_length=64, max_length=64)
    source_claim_token: str = Field(min_length=1, max_length=200)
    source_reservation_message_id: UUID
    source_reservation_fingerprint: str = Field(min_length=64, max_length=64)
    source_consumption_message_id: UUID

    disposition_type: Literal["AUTO_CONTINUE", "AUTO_REWORK"]
    dispatch_kind: Literal["auto_continue", "auto_rework"]
    target_task_strategy: Literal["source_task_continue", "source_task_rework"]

    worker_call_attempted: bool
    worker_returned: bool
    worker_raised: bool
    worker_result_contract_valid: bool
    worker_result_claimed: bool | None = None
    worker_result_message: str | None = Field(default=None, max_length=2_000)
    worker_execution_mode: str | None = Field(default=None, max_length=100)
    worker_failure_category: str | None = Field(default=None, max_length=100)
    worker_quality_gate_passed: bool | None = None
    worker_result_summary: str | None = Field(default=None, max_length=2_000)

    reserved_snapshot_present: bool
    reserved_snapshot_exact_task_id: UUID | None = None
    reserved_snapshot_exact_run_id: UUID | None = None
    reserved_snapshot_exact_binding_validated: bool = False
    reserved_snapshot_task_routed: bool = False
    reserved_snapshot_task_claimed_in_this_cycle: bool = False
    reserved_snapshot_run_created_in_this_cycle: bool = False
    reserved_snapshot_budget_rechecked: bool = False
    reserved_snapshot_existing_run_reused: bool = False
    reserved_snapshot_shared_execution_seam_used: bool = False
    reserved_snapshot_blocked_reasons: list[str] = Field(default_factory=list)

    task_status_after: str | None = None
    run_status_after: str | None = None
    agent_session_id: UUID | None = None
    agent_session_status: str | None = None
    runtime_handle_id: str | None = Field(default=None, max_length=200)

    continuation_started: bool = False
    rework_started: bool = False
    native_process_started: bool = False
    human_recovery_required: bool = False
    exception_type: str | None = Field(default=None, max_length=200)
    exception_summary: str | None = Field(default=None, max_length=500)
    worker_reported_git_write_activity: bool = False
    product_runtime_git_write_allowed: bool = False
    replay_check_completed: bool
    resumed_from_existing_outcome: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    blocked_reasons: list[str] = Field(default_factory=list)

    @field_validator("created_at", mode="after")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value) or utc_now()

    @field_validator(
        "outcome_fingerprint",
        "source_claim_fingerprint",
        "source_reservation_fingerprint",
        mode="after",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.match(value):
            raise ValueError("outcome fingerprints must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_outcome(self) -> "ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult":
        if self.source_claim_id != self.source_claim_message_id:
            raise ValueError("outcome must bind the exact invocation claim")
        if self.product_runtime_git_write_allowed or not self.replay_check_completed:
            raise ValueError("outcome cannot authorize Git write and must scan replay history")
        if self.continuation_started and self.rework_started:
            raise ValueError("continuation and rework cannot both start")
        if self.outcome_status == "not_invoked":
            if (
                self.worker_call_attempted
                or self.worker_returned
                or self.worker_raised
                or self.continuation_started
                or self.rework_started
                or self.native_process_started
                or not self.blocked_reasons
            ):
                raise ValueError("not_invoked outcome has contradictory execution evidence")
        elif self.outcome_status == "returned":
            if (
                not self.worker_call_attempted
                or not self.worker_returned
                or self.worker_raised
                or self.exception_type is not None
                or self.exception_summary is not None
                or (
                    not self.reserved_snapshot_present
                    and (
                        self.worker_result_contract_valid
                        or not self.human_recovery_required
                    )
                )
            ):
                raise ValueError("returned outcome requires a normalized Worker snapshot")
        else:
            if (
                not self.worker_call_attempted
                or self.worker_returned
                or not self.worker_raised
                or not self.exception_type
                or not self.exception_summary
                or not self.human_recovery_required
            ):
                raise ValueError("raised outcome requires safe exception recovery evidence")
        return self


__all__ = (
    "ProjectDirectorProtectedTransitionWorkerInvocationClaimResult",
    "ProjectDirectorProtectedTransitionWorkerInvocationOutcomeResult",
    "ProtectedTransitionWorkerInvocationClaimStatus",
    "ProtectedTransitionWorkerInvocationOutcomeStatus",
)
