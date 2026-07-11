"""Unified protected-transition evidence freshness contract for P21-D-E."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_sandbox_candidate_diff_review_disposition import (
    ReviewDispositionType,
)
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_decision import (
    HumanEscalationDecisionAction,
)


ProtectedTransitionFreshnessStatus = Literal["ready", "blocked"]
ProtectedTransitionAuthority = Literal[
    "AUTOMATED_DISPOSITION",
    "HUMAN_ESCALATION_DECISION",
]
ProtectedTransitionKind = Literal[
    "CONTINUE_GUARDRAIL",
    "BOUNDED_REWORK_GUARDRAIL",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorProtectedTransitionEvidenceFreshnessResult(DomainModel):
    """One append-only final freshness gate without transition execution."""

    freshness_status: ProtectedTransitionFreshnessStatus
    freshness_validation_id: UUID | None = None
    source_transition_message_id: UUID
    source_transition_record_id: UUID | None = None
    source_task_id: UUID
    transition_authority: ProtectedTransitionAuthority | None = None
    transition_kind: ProtectedTransitionKind | None = None
    validated_at: datetime | None = None

    source_handoff_message_id: UUID | None = None
    handoff_id: UUID | None = None
    source_disposition_consumption_message_id: UUID | None = None
    disposition_consumption_id: UUID | None = None
    source_disposition_message_id: UUID | None = None
    disposition_id: UUID | None = None
    disposition_type: ReviewDispositionType | None = None

    source_human_consumption_message_id: UUID | None = None
    human_consumption_id: UUID | None = None
    source_decision_message_id: UUID | None = None
    decision_id: UUID | None = None
    source_package_message_id: UUID | None = None
    escalation_package_id: UUID | None = None
    decision_action: HumanEscalationDecisionAction | None = None
    decision_expires_at: datetime | None = None

    source_review_message_id: UUID | None = None
    source_diff_message_id: UUID | None = None
    review_result_fingerprint: str = Field(default="", max_length=64)
    revalidated_review_result_fingerprint: str = Field(default="", max_length=64)
    reviewed_diff_sha256: str = Field(default="", max_length=64)
    persisted_source_diff_sha256: str = Field(default="", max_length=64)
    current_diff_sha256: str = Field(default="", max_length=64)
    reviewed_scope_paths: list[str] = Field(default_factory=list)
    persisted_source_scope_paths: list[str] = Field(default_factory=list)
    current_scope_paths: list[str] = Field(default_factory=list)
    workspace_path: str = Field(default="", max_length=2_000)
    workspace_path_within_root: bool = False

    aggregate_evidence_fingerprint: str = Field(default="", max_length=64)
    revalidated_aggregate_evidence_fingerprint: str = Field(
        default="",
        max_length=64,
    )
    decision_confirmation_fingerprint: str = Field(default="", max_length=64)
    revalidated_decision_confirmation_fingerprint: str = Field(
        default="",
        max_length=64,
    )
    decision_consumption_evidence_fingerprint: str = Field(
        default="",
        max_length=64,
    )
    revalidated_decision_consumption_evidence_fingerprint: str = Field(
        default="",
        max_length=64,
    )

    source_transition_validated: bool = False
    source_review_validated: bool = False
    review_result_fingerprint_revalidated: bool = False
    source_diff_revalidated: bool = False
    current_workspace_revalidated: bool = False
    current_diff_regenerated: bool = False
    ordered_scope_revalidated: bool = False
    aggregate_evidence_fingerprint_revalidated: bool = False
    decision_fingerprint_revalidated: bool = False
    decision_consumption_fingerprint_revalidated: bool = False
    decision_not_expired_at_freshness_check: bool = False
    decision_not_revoked_after_consumption: bool = False
    single_decision_consumption_validated: bool = False
    evidence_fresh: bool = False
    replay_check_completed: bool = False
    prior_freshness_validation_detected: bool = False
    continuation_guardrail_eligible: bool = False
    bounded_rework_guardrail_eligible: bool = False
    gate_allows_protected_transition_guardrail: bool = False
    gate_allows_write: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)
    freshness_evidence_fingerprint: str = Field(default="", max_length=64)

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
    ai_project_director_total_loop: Literal["Partial"] = "Partial"

    @field_validator("validated_at", "decision_expires_at")
    @classmethod
    def require_timezone_aware_timestamp(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("freshness timestamps must be timezone-aware")
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
            raise ValueError("freshness gate may not execute transitions or write")
        return value

    @model_validator(mode="after")
    def validate_freshness_state(
        self,
    ) -> "ProjectDirectorProtectedTransitionEvidenceFreshnessResult":
        if self.freshness_status == "blocked":
            if self.freshness_validation_id is not None:
                raise ValueError("blocked freshness gate may not create a record")
            if self.gate_allows_protected_transition_guardrail or self.evidence_fresh:
                raise ValueError("blocked freshness gate may not allow transition")
            if not self.blocked_reasons:
                raise ValueError("blocked freshness gate requires a reason")
            return self

        if (
            self.freshness_validation_id is None
            or self.source_transition_record_id is None
            or self.transition_authority is None
            or self.transition_kind is None
            or self.validated_at is None
            or self.source_review_message_id is None
            or self.source_diff_message_id is None
        ):
            raise ValueError("ready freshness gate requires exact identity")
        if not all(
            (
                self.source_transition_validated,
                self.source_review_validated,
                self.review_result_fingerprint_revalidated,
                self.source_diff_revalidated,
                self.current_workspace_revalidated,
                self.current_diff_regenerated,
                self.ordered_scope_revalidated,
                self.evidence_fresh,
                self.replay_check_completed,
                self.gate_allows_protected_transition_guardrail,
                self.workspace_path_within_root,
            )
        ):
            raise ValueError("ready freshness gate requires complete revalidation")
        if self.prior_freshness_validation_detected or self.blocked_reasons:
            raise ValueError("ready freshness gate requires an unreplayed source")
        if not _LOWER_HEX_SHA256.match(self.review_result_fingerprint):
            raise ValueError("ready freshness gate requires review fingerprint")
        if self.review_result_fingerprint != self.revalidated_review_result_fingerprint:
            raise ValueError("ready freshness gate requires matching review fingerprints")
        diff_hashes = (
            self.reviewed_diff_sha256,
            self.persisted_source_diff_sha256,
            self.current_diff_sha256,
        )
        if not all(_LOWER_HEX_SHA256.match(value) for value in diff_hashes):
            raise ValueError("ready freshness gate requires diff fingerprints")
        if len(set(diff_hashes)) != 1:
            raise ValueError("ready freshness gate requires matching diff fingerprints")
        if (
            not self.reviewed_scope_paths
            or self.reviewed_scope_paths != self.persisted_source_scope_paths
            or self.reviewed_scope_paths != self.current_scope_paths
        ):
            raise ValueError("ready freshness gate requires matching ordered scopes")
        if not self.workspace_path:
            raise ValueError("ready freshness gate requires trusted workspace path")
        expected_eligibility = {
            "CONTINUE_GUARDRAIL": (True, False),
            "BOUNDED_REWORK_GUARDRAIL": (False, True),
        }[self.transition_kind]
        if expected_eligibility != (
            self.continuation_guardrail_eligible,
            self.bounded_rework_guardrail_eligible,
        ):
            raise ValueError("freshness eligibility must match transition kind")
        if not _LOWER_HEX_SHA256.match(self.freshness_evidence_fingerprint):
            raise ValueError("ready freshness gate requires evidence fingerprint")

        if self.transition_authority == "AUTOMATED_DISPOSITION":
            if any(
                value is None
                for value in (
                    self.source_handoff_message_id,
                    self.handoff_id,
                    self.source_disposition_consumption_message_id,
                    self.disposition_consumption_id,
                    self.source_disposition_message_id,
                    self.disposition_id,
                    self.disposition_type,
                )
            ):
                raise ValueError("automatic freshness gate requires C2/C3 identity")
            if any(
                value is not None
                for value in (
                    self.source_human_consumption_message_id,
                    self.human_consumption_id,
                    self.source_decision_message_id,
                    self.decision_id,
                    self.source_package_message_id,
                    self.escalation_package_id,
                    self.decision_action,
                    self.decision_expires_at,
                )
            ):
                raise ValueError("automatic freshness gate may not forge human identity")
            if any(
                (
                    self.aggregate_evidence_fingerprint,
                    self.revalidated_aggregate_evidence_fingerprint,
                    self.decision_confirmation_fingerprint,
                    self.revalidated_decision_confirmation_fingerprint,
                    self.decision_consumption_evidence_fingerprint,
                    self.revalidated_decision_consumption_evidence_fingerprint,
                )
            ):
                raise ValueError("automatic freshness gate may not forge human fingerprints")
            if any(
                (
                    self.aggregate_evidence_fingerprint_revalidated,
                    self.decision_fingerprint_revalidated,
                    self.decision_consumption_fingerprint_revalidated,
                    self.decision_not_expired_at_freshness_check,
                    self.decision_not_revoked_after_consumption,
                    self.single_decision_consumption_validated,
                )
            ):
                raise ValueError("automatic freshness gate may not report human checks")
            return self

        if any(
            value is None
            for value in (
                self.source_human_consumption_message_id,
                self.human_consumption_id,
                self.source_decision_message_id,
                self.decision_id,
                self.source_package_message_id,
                self.escalation_package_id,
                self.decision_action,
                self.decision_expires_at,
            )
        ):
            raise ValueError("human freshness gate requires D1/D2/D4 identity")
        if any(
            value is not None
            for value in (
                self.source_handoff_message_id,
                self.handoff_id,
                self.source_disposition_consumption_message_id,
                self.disposition_consumption_id,
                self.source_disposition_message_id,
                self.disposition_id,
                self.disposition_type,
            )
        ):
            raise ValueError("human freshness gate may not forge automatic identity")
        fingerprint_pairs = (
            (
                self.aggregate_evidence_fingerprint,
                self.revalidated_aggregate_evidence_fingerprint,
            ),
            (
                self.decision_confirmation_fingerprint,
                self.revalidated_decision_confirmation_fingerprint,
            ),
            (
                self.decision_consumption_evidence_fingerprint,
                self.revalidated_decision_consumption_evidence_fingerprint,
            ),
        )
        if not all(
            _LOWER_HEX_SHA256.match(stored)
            and stored == revalidated
            for stored, revalidated in fingerprint_pairs
        ):
            raise ValueError("human freshness gate requires matching fingerprints")
        if not all(
            (
                self.aggregate_evidence_fingerprint_revalidated,
                self.decision_fingerprint_revalidated,
                self.decision_consumption_fingerprint_revalidated,
                self.decision_not_expired_at_freshness_check,
                self.decision_not_revoked_after_consumption,
                self.single_decision_consumption_validated,
            )
        ):
            raise ValueError("human freshness gate requires current decision checks")
        return self


__all__ = (
    "ProjectDirectorProtectedTransitionEvidenceFreshnessResult",
    "ProtectedTransitionAuthority",
    "ProtectedTransitionFreshnessStatus",
    "ProtectedTransitionKind",
)
