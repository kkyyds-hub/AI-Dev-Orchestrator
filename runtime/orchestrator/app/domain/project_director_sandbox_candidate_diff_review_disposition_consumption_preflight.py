"""Disposition consumption preflight contract for Project Director P21-D-C1."""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_sandbox_candidate_diff_review_disposition import (
    ReviewDispositionType,
)


DispositionConsumptionPreflightStatus = Literal["ready", "blocked"]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult(
    DomainModel
):
    """Trusted eligibility result that never consumes or executes a disposition."""

    preflight_status: DispositionConsumptionPreflightStatus
    source_disposition_message_id: UUID
    source_review_message_id: UUID | None = None
    disposition_id: UUID | None = None
    disposition_type: ReviewDispositionType | None = None
    review_result_fingerprint: str = Field(default="", max_length=64)
    revalidated_review_result_fingerprint: str = Field(default="", max_length=64)
    continuation_eligible: bool = False
    rework_eligible: bool = False
    replay_check_completed: bool = False
    prior_preflight_detected: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)

    continuation_started: bool = False
    rework_started: bool = False
    disposition_consumed: bool = False
    human_escalation_package_created: bool = False
    human_decision_recorded: bool = False
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
        "continuation_started",
        "rework_started",
        "disposition_consumed",
        "human_escalation_package_created",
        "human_decision_recorded",
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
            raise ValueError("consumption preflight may not execute or authorize writes")
        return value

    @model_validator(mode="after")
    def validate_preflight_state(
        self,
    ) -> "ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult":
        if self.preflight_status == "blocked":
            if self.continuation_eligible or self.rework_eligible:
                raise ValueError("blocked preflight may not expose consumption eligibility")
            if not self.blocked_reasons:
                raise ValueError("blocked preflight requires a reason")
            return self

        if self.disposition_type not in ("AUTO_CONTINUE", "AUTO_REWORK"):
            raise ValueError("ready preflight requires an automatic disposition")
        if self.source_review_message_id is None or self.disposition_id is None:
            raise ValueError("ready preflight requires disposition and review bindings")
        if not _LOWER_HEX_SHA256.match(self.review_result_fingerprint):
            raise ValueError("ready preflight requires a persisted review fingerprint")
        if not _LOWER_HEX_SHA256.match(
            self.revalidated_review_result_fingerprint
        ):
            raise ValueError("ready preflight requires a revalidated review fingerprint")
        if (
            self.review_result_fingerprint
            != self.revalidated_review_result_fingerprint
        ):
            raise ValueError("ready preflight requires matching review fingerprints")
        if not self.replay_check_completed or self.prior_preflight_detected:
            raise ValueError("ready preflight requires a completed clean replay check")
        if self.blocked_reasons:
            raise ValueError("ready preflight may not be blocked")
        expected_eligibility = (
            self.disposition_type == "AUTO_CONTINUE",
            self.disposition_type == "AUTO_REWORK",
        )
        if (
            self.continuation_eligible,
            self.rework_eligible,
        ) != expected_eligibility:
            raise ValueError("ready preflight eligibility must match disposition type")
        return self


__all__ = (
    "DispositionConsumptionPreflightStatus",
    "ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightResult",
)
