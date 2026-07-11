"""Structured human escalation decision contract for Project Director P21-D-D2."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel


HumanEscalationDecisionStatus = Literal["recorded", "blocked"]
HumanEscalationDecisionScope = Literal[
    "resolve_single_source_review_escalation"
]
HumanEscalationDecisionAction = Literal[
    "APPROVE_CONTINUE",
    "REQUEST_REWORK",
    "REJECT",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult(
    DomainModel
):
    """Append-only D2 decision record without consumption or execution."""

    decision_status: HumanEscalationDecisionStatus
    decision_id: UUID | None = None
    source_package_message_id: UUID
    escalation_package_id: UUID | None = None

    source_disposition_message_id: UUID | None = None
    source_review_message_id: UUID | None = None
    source_preflight_message_id: UUID | None = None
    source_diff_message_id: UUID | None = None
    disposition_id: UUID | None = None
    aggregate_evidence_fingerprint: str = Field(default="", max_length=64)

    decision_scope: HumanEscalationDecisionScope | None = None
    decision_action: HumanEscalationDecisionAction | None = None
    actor_type: Literal["human"] = "human"
    actor: str = Field(default="", max_length=200)
    client_request_id: str = Field(default="", max_length=200)
    decision_created_at: datetime | None = None
    decision_expires_at: datetime | None = None
    decision_confirmation_fingerprint: str = Field(default="", max_length=64)

    source_package_validated: bool = False
    aggregate_evidence_fingerprint_revalidated: bool = False
    replay_check_completed: bool = False
    prior_decision_detected: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)

    human_escalation_package_created: bool = False
    human_decision_recorded: bool = False

    decision_consumption_started: bool = False
    decision_consumed: bool = False
    decision_revoked: bool = False
    decision_expired: bool = False
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

    @field_validator("actor", "client_request_id", mode="before")
    @classmethod
    def normalize_identity_text(cls, value: object) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip()

    @field_validator("decision_created_at", "decision_expires_at")
    @classmethod
    def require_timezone_aware_datetime(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("human escalation decision timestamps must be timezone-aware")
        return value

    @field_validator(
        "decision_consumption_started",
        "decision_consumed",
        "decision_revoked",
        "decision_expired",
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
            raise ValueError("human escalation decision may not consume or execute")
        return value

    @model_validator(mode="after")
    def validate_decision_state(
        self,
    ) -> "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult":
        if self.decision_status == "blocked":
            if self.decision_id is not None or self.decision_created_at is not None:
                raise ValueError("blocked human escalation decision may not be created")
            if self.decision_confirmation_fingerprint:
                raise ValueError("blocked decision may not expose a confirmation fingerprint")
            if self.human_decision_recorded:
                raise ValueError("blocked decision may not report a human decision")
            if not self.blocked_reasons:
                raise ValueError("blocked human escalation decision requires a reason")
            return self

        if self.decision_id is None or self.escalation_package_id is None:
            raise ValueError("recorded decision requires exact decision and package identity")
        if any(
            value is None
            for value in (
                self.source_disposition_message_id,
                self.source_review_message_id,
                self.source_preflight_message_id,
                self.source_diff_message_id,
                self.disposition_id,
            )
        ):
            raise ValueError("recorded decision requires all exact source identifiers")
        if not _LOWER_HEX_SHA256.match(self.aggregate_evidence_fingerprint):
            raise ValueError("recorded decision requires aggregate evidence fingerprint")
        if self.decision_scope != "resolve_single_source_review_escalation":
            raise ValueError("recorded decision requires the bounded decision scope")
        if self.decision_action not in (
            "APPROVE_CONTINUE",
            "REQUEST_REWORK",
            "REJECT",
        ):
            raise ValueError("recorded decision action is invalid")
        if self.actor_type != "human" or not self.actor or not self.client_request_id:
            raise ValueError("recorded decision requires normalized human identity")
        if self.decision_created_at is None or self.decision_expires_at is None:
            raise ValueError("recorded decision requires created and expiry timestamps")
        if self.decision_expires_at <= self.decision_created_at:
            raise ValueError("decision_expires_at must be later than decision_created_at")
        if not _LOWER_HEX_SHA256.match(self.decision_confirmation_fingerprint):
            raise ValueError("recorded decision requires confirmation fingerprint")
        if not self.source_package_validated:
            raise ValueError("recorded decision requires a validated D1 package")
        if not self.aggregate_evidence_fingerprint_revalidated:
            raise ValueError("recorded decision requires revalidated aggregate evidence")
        if not self.replay_check_completed or self.prior_decision_detected:
            raise ValueError("recorded decision requires a clean replay check")
        if not self.human_escalation_package_created or not self.human_decision_recorded:
            raise ValueError("recorded decision requires package and decision state")
        if self.blocked_reasons:
            raise ValueError("recorded decision may not contain blocked reasons")
        return self


__all__ = (
    "HumanEscalationDecisionAction",
    "HumanEscalationDecisionScope",
    "HumanEscalationDecisionStatus",
    "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionResult",
)
