"""Unified P23-D3 protected-transition auto-advance result contract."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.domain._base import DomainModel


ProtectedTransitionAutoAdvanceStatus = Literal[
    "waiting_for_human",
    "blocked",
    "recovery_required",
    "worker_not_invoked",
    "worker_returned",
    "worker_raised",
    "bounded_rework_outcome_recorded",
    "bounded_rework_outcome_replayed",
]


class ProjectDirectorProtectedTransitionAutoAdvanceResult(DomainModel):
    """Normalized view over the existing P22 through P23-D2 evidence chain."""

    auto_advance_status: ProtectedTransitionAutoAdvanceStatus
    current_step: str = Field(min_length=1, max_length=100)

    session_id: UUID
    project_id: UUID | None = None
    source_task_id: UUID
    source_review_message_id: UUID

    source_p22_summary_message_id: UUID | None = None
    source_dispatch_intent_message_id: UUID | None = None
    source_dispatch_consumption_preflight_message_id: UUID | None = None
    source_dispatch_consumption_message_id: UUID | None = None
    source_p25_package_message_id: UUID | None = None
    source_p25_attempt_reservation_message_id: UUID | None = None
    source_p25_invocation_claim_message_id: UUID | None = None
    source_p25_invocation_outcome_message_id: UUID | None = None
    source_worker_start_reservation_message_id: UUID | None = None
    source_worker_invocation_claim_message_id: UUID | None = None
    source_worker_invocation_outcome_message_id: UUID | None = None

    route: Literal[
        "none",
        "human_escalation",
        "automatic_continuation",
        "bounded_automatic_rework",
    ] = "none"
    disposition_type: Literal[
        "AUTO_CONTINUE",
        "AUTO_REWORK",
        "ESCALATE_TO_HUMAN",
    ] | None = None
    dispatch_kind: Literal["auto_continue", "auto_rework"] | None = None
    target_task_strategy: Literal[
        "source_task_continue",
        "source_task_rework",
    ] | None = None
    run_id: UUID | None = None

    worker_invocation_claimed: bool = False
    worker_call_attempted: bool = False
    worker_returned: bool = False
    worker_raised: bool = False
    worker_outcome_status: Literal[
        "not_invoked",
        "returned",
        "raised",
    ] | None = None
    continuation_started: bool = False
    rework_started: bool = False
    human_recovery_required: bool = False
    worker_reported_git_write_activity: bool = False
    p25_execution_status: Literal["outcome_recorded", "outcome_replayed"] | None = None
    p25_recovery_required: bool = False
    p25_human_escalation_required: bool = False

    resumed_from_existing_evidence: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)
    exception_summary: str | None = Field(default=None, max_length=500)

    d1_task_claimed: bool = False
    d1_run_created: bool = False

    coordinator_created_task: bool = False
    coordinator_created_run: bool = False
    coordinator_routed_task: bool = False
    coordinator_claimed_task: bool = False
    coordinator_called_worker_directly: bool = False

    product_runtime_git_write_allowed: bool = False
    ai_project_director_total_loop: Literal["Partial"] = "Partial"

    @model_validator(mode="after")
    def validate_auto_advance(self) -> "ProjectDirectorProtectedTransitionAutoAdvanceResult":
        if any(
            (
                self.coordinator_created_task,
                self.coordinator_created_run,
                self.coordinator_routed_task,
                self.coordinator_claimed_task,
                self.coordinator_called_worker_directly,
                self.product_runtime_git_write_allowed,
            )
        ):
            raise ValueError("D3 cannot create, route, claim, call Worker directly, or allow Git write")
        if self.continuation_started and self.rework_started:
            raise ValueError("continuation and rework cannot both start")
        if self.disposition_type == "AUTO_CONTINUE" and self.rework_started:
            raise ValueError("AUTO_CONTINUE cannot start rework")
        if self.disposition_type == "AUTO_REWORK" and self.continuation_started:
            raise ValueError("AUTO_REWORK cannot start continuation")
        if self.worker_reported_git_write_activity and (
            not self.human_recovery_required
            or "worker_result_git_boundary_violation" not in self.blocked_reasons
        ):
            raise ValueError("reported Git activity requires explicit human recovery")

        status = self.auto_advance_status
        if status == "waiting_for_human":
            p23_ids = (
                self.source_dispatch_intent_message_id,
                self.source_dispatch_consumption_preflight_message_id,
                self.source_dispatch_consumption_message_id,
                self.source_p25_package_message_id,
                self.source_p25_attempt_reservation_message_id,
                self.source_p25_invocation_claim_message_id,
                self.source_p25_invocation_outcome_message_id,
                self.source_worker_start_reservation_message_id,
                self.source_worker_invocation_claim_message_id,
                self.source_worker_invocation_outcome_message_id,
            )
            if (
                self.route != "human_escalation"
                or self.source_p22_summary_message_id is None
                or any(item is not None for item in p23_ids)
                or self.worker_call_attempted
                or self.continuation_started
                or self.rework_started
                or self.human_recovery_required
                or self.p25_execution_status is not None
                or self.p25_recovery_required
                or self.p25_human_escalation_required
                or self.blocked_reasons
            ):
                raise ValueError("waiting_for_human evidence is inconsistent")
        elif status == "blocked":
            if (
                self.worker_invocation_claimed
                or self.worker_call_attempted
                or self.continuation_started
                or self.rework_started
                or not self.blocked_reasons
            ):
                raise ValueError("blocked status must precede Worker invocation claim")
        elif status == "recovery_required":
            if not self.human_recovery_required or not self.blocked_reasons:
                raise ValueError("recovery_required needs reasons and human recovery")
        elif status == "worker_not_invoked":
            if (
                self.source_worker_invocation_claim_message_id is None
                or self.source_worker_invocation_outcome_message_id is None
                or self.worker_outcome_status != "not_invoked"
                or not self.worker_invocation_claimed
                or self.worker_call_attempted
                or self.worker_returned
                or self.worker_raised
                or self.continuation_started
                or self.rework_started
                or self.p25_execution_status is not None
            ):
                raise ValueError("worker_not_invoked requires its durable B2 outcome")
        elif status == "worker_returned":
            if (
                self.source_worker_invocation_claim_message_id is None
                or self.source_worker_invocation_outcome_message_id is None
                or self.worker_outcome_status != "returned"
                or not self.worker_invocation_claimed
                or not self.worker_call_attempted
                or not self.worker_returned
                or self.worker_raised
                or self.p25_execution_status is not None
            ):
                raise ValueError("worker_returned requires its durable B2 outcome")
        elif status in {
            "bounded_rework_outcome_recorded",
            "bounded_rework_outcome_replayed",
        }:
            if (
                self.disposition_type != "AUTO_REWORK"
                or self.source_dispatch_consumption_message_id is None
                or self.source_p25_package_message_id is None
                or self.source_p25_attempt_reservation_message_id is None
                or self.source_p25_invocation_claim_message_id is None
                or self.source_p25_invocation_outcome_message_id is None
                or self.p25_execution_status
                != (
                    "outcome_recorded"
                    if status == "bounded_rework_outcome_recorded"
                    else "outcome_replayed"
                )
                or self.continuation_started
                or not self.rework_started
                or self.worker_invocation_claimed
                or self.worker_call_attempted
                or self.worker_returned
                or self.worker_raised
                or self.source_worker_start_reservation_message_id is not None
                or self.source_worker_invocation_claim_message_id is not None
                or self.source_worker_invocation_outcome_message_id is not None
            ):
                raise ValueError("bounded rework D3 status requires exact P25 lineage")
            if self.p25_human_escalation_required and not self.p25_recovery_required:
                raise ValueError("bounded rework human escalation requires recovery")
        elif (
            self.source_worker_invocation_claim_message_id is None
            or self.source_worker_invocation_outcome_message_id is None
            or self.worker_outcome_status != "raised"
            or not self.worker_invocation_claimed
            or not self.worker_call_attempted
            or self.worker_returned
            or not self.worker_raised
            or not self.human_recovery_required
            or self.p25_execution_status is not None
        ):
            raise ValueError("worker_raised requires durable recovery evidence")
        return self


__all__ = (
    "ProjectDirectorProtectedTransitionAutoAdvanceResult",
    "ProtectedTransitionAutoAdvanceStatus",
)
