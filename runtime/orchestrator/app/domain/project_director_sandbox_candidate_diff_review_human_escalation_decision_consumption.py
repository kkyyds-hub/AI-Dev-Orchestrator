"""Atomic human escalation decision consumption contract for P21-D-D4."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_decision import (
    HumanEscalationDecisionAction,
)


HumanEscalationDecisionConsumptionStatus = Literal["consumed", "blocked"]
HumanEscalationDecisionTransitionKind = Literal[
    "CONTINUE_GUARDRAIL",
    "BOUNDED_REWORK_GUARDRAIL",
    "TERMINAL_REJECTION",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult(
    DomainModel
):
    """One append-only D4 consumption result without transition execution."""

    consumption_status: HumanEscalationDecisionConsumptionStatus
    consumption_id: UUID | None = None
    source_preflight_message_id: UUID
    preflight_id: UUID | None = None
    source_decision_message_id: UUID | None = None
    decision_id: UUID | None = None
    source_package_message_id: UUID | None = None
    escalation_package_id: UUID | None = None

    decision_action: HumanEscalationDecisionAction | None = None
    decision_confirmation_fingerprint: str = Field(default="", max_length=64)
    revalidated_decision_confirmation_fingerprint: str = Field(
        default="",
        max_length=64,
    )
    aggregate_evidence_fingerprint: str = Field(default="", max_length=64)
    consumption_evidence_fingerprint: str = Field(default="", max_length=64)
    decision_created_at: datetime | None = None
    decision_expires_at: datetime | None = None
    preflight_evaluated_at: datetime | None = None
    consumed_at: datetime | None = None

    source_preflight_validated: bool = False
    source_decision_validated: bool = False
    decision_fingerprint_revalidated: bool = False
    exact_preflight_decision_binding_validated: bool = False
    replay_check_completed: bool = False

    decision_active_at_consumption: bool = False
    decision_expired: bool = False
    decision_revoked: bool = False
    prior_consumption_detected: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)

    transition_kind: HumanEscalationDecisionTransitionKind | None = None
    continuation_guardrail_eligible: bool = False
    bounded_rework_guardrail_eligible: bool = False
    terminal_rejection: bool = False
    gate_allows_protected_transition_guardrail: bool = False

    decision_consumption_started: bool = False
    decision_consumed: bool = False
    continuation_started: bool = False
    rework_started: bool = False
    approval_request_created: bool = False
    legacy_approval_decision_created: bool = False
    main_project_file_written: bool = False
    sandbox_file_written: bool = False
    manifest_file_written: bool = False
    diff_file_written: bool = False
    patch_applied: bool = False
    git_write_performed: bool = False
    worktree_created: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    gate_allows_write: bool = False

    ai_project_director_total_loop: Literal["Partial"] = "Partial"

    @field_validator(
        "decision_created_at",
        "decision_expires_at",
        "preflight_evaluated_at",
        "consumed_at",
    )
    @classmethod
    def require_timezone_aware_timestamp(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("D4 consumption timestamps must be timezone-aware")
        return value

    @field_validator(
        "continuation_started",
        "rework_started",
        "approval_request_created",
        "legacy_approval_decision_created",
        "main_project_file_written",
        "sandbox_file_written",
        "manifest_file_written",
        "diff_file_written",
        "patch_applied",
        "git_write_performed",
        "worktree_created",
        "worker_started",
        "task_created",
        "run_created",
        "gate_allows_write",
        mode="after",
    )
    @classmethod
    def reject_forbidden_side_effect_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError("D4 consumption may not execute transitions or write")
        return value

    @model_validator(mode="after")
    def validate_consumption_state(
        self,
    ) -> "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult":
        if self.consumption_status == "blocked":
            if self.consumption_id is not None or self.consumed_at is not None:
                raise ValueError("blocked consumption may not create a record")
            if self.decision_consumption_started or self.decision_consumed:
                raise ValueError("blocked consumption may not consume a decision")
            if self.gate_allows_protected_transition_guardrail:
                raise ValueError("blocked consumption may not allow a transition guardrail")
            if not self.blocked_reasons:
                raise ValueError("blocked consumption requires a reason")
            return self

        required_identity = (
            self.consumption_id,
            self.preflight_id,
            self.source_decision_message_id,
            self.decision_id,
            self.source_package_message_id,
            self.escalation_package_id,
        )
        if any(value is None for value in required_identity):
            raise ValueError("consumed result requires exact source identity")
        required_timestamps = (
            self.decision_created_at,
            self.decision_expires_at,
            self.preflight_evaluated_at,
            self.consumed_at,
        )
        if any(value is None for value in required_timestamps):
            raise ValueError("consumed result requires exact timestamps")
        if self.consumed_at >= self.decision_expires_at:
            raise ValueError("consumed_at must be earlier than decision_expires_at")
        if not _LOWER_HEX_SHA256.match(self.aggregate_evidence_fingerprint):
            raise ValueError("consumed result requires aggregate evidence fingerprint")
        if not _LOWER_HEX_SHA256.match(self.decision_confirmation_fingerprint):
            raise ValueError("consumed result requires decision fingerprint")
        if (
            self.decision_confirmation_fingerprint
            != self.revalidated_decision_confirmation_fingerprint
        ):
            raise ValueError("consumed result requires matching decision fingerprints")
        if not _LOWER_HEX_SHA256.match(self.consumption_evidence_fingerprint):
            raise ValueError("consumed result requires consumption evidence fingerprint")
        if not all(
            (
                self.source_preflight_validated,
                self.source_decision_validated,
                self.decision_fingerprint_revalidated,
                self.exact_preflight_decision_binding_validated,
                self.replay_check_completed,
                self.decision_active_at_consumption,
                self.decision_consumption_started,
                self.decision_consumed,
            )
        ):
            raise ValueError("consumed result requires complete validation and consumption")
        if self.decision_expired or self.decision_revoked or self.prior_consumption_detected:
            raise ValueError("consumed result requires one active unused decision")
        expected_transition = {
            "APPROVE_CONTINUE": (
                "CONTINUE_GUARDRAIL",
                True,
                False,
                False,
                True,
            ),
            "REQUEST_REWORK": (
                "BOUNDED_REWORK_GUARDRAIL",
                False,
                True,
                False,
                True,
            ),
            "REJECT": (
                "TERMINAL_REJECTION",
                False,
                False,
                True,
                False,
            ),
        }.get(self.decision_action)
        actual_transition = (
            self.transition_kind,
            self.continuation_guardrail_eligible,
            self.bounded_rework_guardrail_eligible,
            self.terminal_rejection,
            self.gate_allows_protected_transition_guardrail,
        )
        if expected_transition != actual_transition:
            raise ValueError("consumed transition must match the decision action")
        if self.blocked_reasons:
            raise ValueError("consumed result may not contain blocked reasons")
        return self


__all__ = (
    "HumanEscalationDecisionConsumptionStatus",
    "HumanEscalationDecisionTransitionKind",
    "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult",
)
