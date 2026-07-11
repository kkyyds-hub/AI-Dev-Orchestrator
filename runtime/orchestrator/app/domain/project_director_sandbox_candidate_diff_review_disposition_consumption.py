"""Fresh disposition consumption contract for Project Director P21-D-C2."""

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


DispositionConsumptionStatus = Literal["consumed", "blocked"]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
    DomainModel
):
    """P21-D-C2 audit result without continuation or rework execution."""

    consumption_status: DispositionConsumptionStatus
    consumption_id: UUID | None = None
    source_consumption_preflight_message_id: UUID
    source_disposition_message_id: UUID | None = None
    source_review_message_id: UUID | None = None
    source_diff_message_id: UUID | None = None
    disposition_id: UUID | None = None
    disposition_type: ReviewDispositionType | None = None
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
    source_diff_revalidated: bool = False
    current_diff_regenerated: bool = False
    evidence_fresh: bool = False
    disposition_consumed: bool = False
    continuation_eligible: bool = False
    rework_eligible: bool = False
    replay_check_completed: bool = False
    prior_consumption_detected: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)
    consumed_at: datetime | None = None

    continuation_started: bool = False
    rework_started: bool = False
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
            raise ValueError("disposition consumption may not execute or write")
        return value

    @model_validator(mode="after")
    def validate_consumption_state(
        self,
    ) -> "ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult":
        if self.consumption_status == "blocked":
            if self.evidence_fresh or self.disposition_consumed:
                raise ValueError("blocked consumption may not consume fresh evidence")
            if self.continuation_eligible or self.rework_eligible:
                raise ValueError("blocked consumption may not expose eligibility")
            if not self.blocked_reasons:
                raise ValueError("blocked consumption requires a reason")
            return self

        required_ids = (
            self.consumption_id,
            self.source_disposition_message_id,
            self.source_review_message_id,
            self.source_diff_message_id,
            self.disposition_id,
        )
        if any(value is None for value in required_ids):
            raise ValueError("consumed disposition requires complete evidence bindings")
        if self.disposition_type not in ("AUTO_CONTINUE", "AUTO_REWORK"):
            raise ValueError("consumed disposition requires an automatic type")
        if not all(
            _LOWER_HEX_SHA256.match(value)
            for value in (
                self.review_result_fingerprint,
                self.revalidated_review_result_fingerprint,
                self.reviewed_diff_sha256,
                self.persisted_source_diff_sha256,
                self.current_diff_sha256,
            )
        ):
            raise ValueError("consumed disposition requires valid fingerprints")
        if (
            self.review_result_fingerprint
            != self.revalidated_review_result_fingerprint
        ):
            raise ValueError("consumed disposition requires matching review fingerprints")
        if len(
            {
                self.reviewed_diff_sha256,
                self.persisted_source_diff_sha256,
                self.current_diff_sha256,
            }
        ) != 1:
            raise ValueError("consumed disposition requires matching diff fingerprints")
        if (
            not self.reviewed_scope_paths
            or self.reviewed_scope_paths != self.persisted_source_scope_paths
            or self.reviewed_scope_paths != self.current_scope_paths
        ):
            raise ValueError("consumed disposition requires matching ordered scopes")
        if not self.workspace_path or not self.workspace_path_within_root:
            raise ValueError("consumed disposition requires a trusted workspace")
        required_true_flags = (
            self.source_diff_revalidated,
            self.current_diff_regenerated,
            self.evidence_fresh,
            self.disposition_consumed,
            self.replay_check_completed,
        )
        if not all(required_true_flags) or self.prior_consumption_detected:
            raise ValueError("consumed disposition requires fresh unreplayed evidence")
        if self.blocked_reasons:
            raise ValueError("consumed disposition may not be blocked")
        expected_eligibility = (
            self.disposition_type == "AUTO_CONTINUE",
            self.disposition_type == "AUTO_REWORK",
        )
        if (
            self.continuation_eligible,
            self.rework_eligible,
        ) != expected_eligibility:
            raise ValueError("consumption eligibility must match disposition type")
        if (
            self.consumed_at is None
            or self.consumed_at.tzinfo is None
            or self.consumed_at.utcoffset() is None
        ):
            raise ValueError("consumed disposition requires a timezone-aware timestamp")
        return self


__all__ = (
    "DispositionConsumptionStatus",
    "ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult",
)
