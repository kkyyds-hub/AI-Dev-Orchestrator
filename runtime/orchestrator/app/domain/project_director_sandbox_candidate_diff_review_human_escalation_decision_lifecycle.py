"""Decision lifecycle guard contracts for Project Director P21-D-D3."""

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


HumanEscalationDecisionRevocationStatus = Literal["revoked", "blocked"]
HumanEscalationDecisionConsumptionPreflightStatus = Literal["ready", "blocked"]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class _ProjectDirectorHumanEscalationDecisionLifecycleSafetyResult(DomainModel):
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
        "decision_consumption_started",
        "decision_consumed",
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
            raise ValueError("D3 lifecycle guard may not consume, execute, or write")
        return value


class ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult(
    _ProjectDirectorHumanEscalationDecisionLifecycleSafetyResult
):
    """Append-only D3 revocation result without downstream side effects."""

    revocation_status: HumanEscalationDecisionRevocationStatus
    revocation_id: UUID | None = None
    source_decision_message_id: UUID
    decision_id: UUID | None = None
    source_package_message_id: UUID | None = None
    escalation_package_id: UUID | None = None
    decision_confirmation_fingerprint: str = Field(default="", max_length=64)
    revalidated_decision_confirmation_fingerprint: str = Field(
        default="",
        max_length=64,
    )

    revoke_actor_type: Literal["human"] = "human"
    revoke_actor: str = Field(default="", max_length=200)
    revoke_client_request_id: str = Field(default="", max_length=200)
    revoked_at: datetime | None = None

    source_decision_validated: bool = False
    decision_fingerprint_revalidated: bool = False
    replay_check_completed: bool = False
    prior_revocation_detected: bool = False
    decision_revoked: bool = False
    decision_expired: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)

    @field_validator("revoke_actor", "revoke_client_request_id", mode="before")
    @classmethod
    def normalize_revoke_identity(cls, value: object) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip()

    @field_validator("revoked_at")
    @classmethod
    def require_aware_revoked_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("revoked_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_revocation_state(
        self,
    ) -> "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult":
        if self.revocation_status == "blocked":
            if self.revocation_id is not None or self.revoked_at is not None:
                raise ValueError("blocked revocation may not create a record")
            if self.decision_revoked and not self.prior_revocation_detected:
                raise ValueError("blocked revocation may only report prior revocation")
            if not self.blocked_reasons:
                raise ValueError("blocked revocation requires a reason")
            return self

        if (
            self.revocation_id is None
            or self.decision_id is None
            or self.source_package_message_id is None
            or self.escalation_package_id is None
            or self.revoked_at is None
        ):
            raise ValueError("revoked result requires exact identity and timestamp")
        if not self.revoke_actor or not self.revoke_client_request_id:
            raise ValueError("revoked result requires normalized human identity")
        if not _LOWER_HEX_SHA256.match(self.decision_confirmation_fingerprint):
            raise ValueError("revoked result requires decision fingerprint")
        if (
            self.decision_confirmation_fingerprint
            != self.revalidated_decision_confirmation_fingerprint
        ):
            raise ValueError("revoked result requires matching decision fingerprints")
        if not (
            self.source_decision_validated
            and self.decision_fingerprint_revalidated
            and self.replay_check_completed
        ):
            raise ValueError("revoked result requires validated source and replay")
        if self.prior_revocation_detected or not self.decision_revoked:
            raise ValueError("revoked result requires a new revocation")
        if self.decision_expired or self.decision_consumed:
            raise ValueError("expired or consumed decision may not be revoked")
        if self.blocked_reasons:
            raise ValueError("revoked result may not contain blocked reasons")
        return self


class ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult(
    _ProjectDirectorHumanEscalationDecisionLifecycleSafetyResult
):
    """D3 consumption eligibility result without actual decision consumption."""

    preflight_status: HumanEscalationDecisionConsumptionPreflightStatus
    preflight_id: UUID | None = None
    source_decision_message_id: UUID
    decision_id: UUID | None = None
    source_package_message_id: UUID | None = None
    escalation_package_id: UUID | None = None
    decision_action: HumanEscalationDecisionAction | None = None
    decision_confirmation_fingerprint: str = Field(default="", max_length=64)
    revalidated_decision_confirmation_fingerprint: str = Field(
        default="",
        max_length=64,
    )

    decision_created_at: datetime | None = None
    decision_expires_at: datetime | None = None
    evaluated_at: datetime | None = None

    source_decision_validated: bool = False
    decision_fingerprint_revalidated: bool = False
    replay_check_completed: bool = False
    decision_active: bool = False
    decision_expired: bool = False
    decision_revoked: bool = False
    prior_consumption_preflight_detected: bool = False

    continuation_eligible: bool = False
    rework_eligible: bool = False
    rejection_terminal: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)

    @field_validator("decision_created_at", "decision_expires_at", "evaluated_at")
    @classmethod
    def require_aware_lifecycle_timestamp(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("D3 lifecycle timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_preflight_state(
        self,
    ) -> "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult":
        if self.preflight_status == "blocked":
            if self.preflight_id is not None:
                raise ValueError("blocked preflight may not create a record")
            if self.decision_active:
                raise ValueError("blocked preflight may not report an active decision")
            if (
                self.continuation_eligible
                or self.rework_eligible
                or self.rejection_terminal
            ):
                raise ValueError("blocked preflight may not expose eligibility")
            if not self.blocked_reasons:
                raise ValueError("blocked preflight requires a reason")
            return self

        if (
            self.preflight_id is None
            or self.decision_id is None
            or self.source_package_message_id is None
            or self.escalation_package_id is None
            or self.decision_created_at is None
            or self.decision_expires_at is None
            or self.evaluated_at is None
        ):
            raise ValueError("ready preflight requires exact identity and timestamps")
        if not _LOWER_HEX_SHA256.match(self.decision_confirmation_fingerprint):
            raise ValueError("ready preflight requires decision fingerprint")
        if (
            self.decision_confirmation_fingerprint
            != self.revalidated_decision_confirmation_fingerprint
        ):
            raise ValueError("ready preflight requires matching decision fingerprints")
        if not (
            self.source_decision_validated
            and self.decision_fingerprint_revalidated
            and self.replay_check_completed
        ):
            raise ValueError("ready preflight requires validated source and replay")
        if (
            not self.decision_active
            or self.decision_expired
            or self.decision_revoked
            or self.decision_consumed
            or self.prior_consumption_preflight_detected
        ):
            raise ValueError("ready preflight requires one active unused decision")
        expected_eligibility = {
            "APPROVE_CONTINUE": (True, False, False),
            "REQUEST_REWORK": (False, True, False),
            "REJECT": (False, False, True),
        }.get(self.decision_action)
        if expected_eligibility != (
            self.continuation_eligible,
            self.rework_eligible,
            self.rejection_terminal,
        ):
            raise ValueError("ready preflight eligibility must match decision action")
        if self.blocked_reasons:
            raise ValueError("ready preflight may not contain blocked reasons")
        return self


__all__ = (
    "HumanEscalationDecisionConsumptionPreflightStatus",
    "HumanEscalationDecisionRevocationStatus",
    "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionPreflightResult",
    "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult",
)
