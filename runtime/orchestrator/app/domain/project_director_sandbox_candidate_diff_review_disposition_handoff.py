"""Append-only disposition handoff contract for Project Director P21-D-C3."""

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


DispositionHandoffStatus = Literal["prepared", "blocked"]
DispositionHandoffKind = Literal[
    "automatic_continuation",
    "bounded_automatic_rework",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult(
    DomainModel
):
    """P21-D-C3 handoff result without continuation or rework execution."""

    handoff_status: DispositionHandoffStatus
    handoff_id: UUID | None = None

    source_consumption_message_id: UUID
    source_consumption_id: UUID | None = None
    source_consumption_preflight_message_id: UUID | None = None
    source_disposition_message_id: UUID | None = None
    source_review_message_id: UUID | None = None
    source_diff_message_id: UUID | None = None
    disposition_id: UUID | None = None
    disposition_type: ReviewDispositionType | None = None
    disposition_reason: str = ""

    handoff_kind: DispositionHandoffKind | None = None

    review_result_fingerprint: str = Field(default="", max_length=64)
    revalidated_review_result_fingerprint: str = Field(default="", max_length=64)
    reviewed_diff_sha256: str = Field(default="", max_length=64)
    persisted_source_diff_sha256: str = Field(default="", max_length=64)
    current_diff_sha256: str = Field(default="", max_length=64)
    review_prompt_sha256: str = Field(default="", max_length=64)

    reviewed_scope_paths: list[str] = Field(default_factory=list)
    persisted_source_scope_paths: list[str] = Field(default_factory=list)
    current_scope_paths: list[str] = Field(default_factory=list)

    workspace_path: str = Field(default="", max_length=2_000)
    workspace_path_within_root: bool = False

    source_consumption_validated: bool = False
    replay_check_completed: bool = False
    prior_handoff_detected: bool = False

    prior_rework_handoff_count: int = Field(default=0, ge=0)
    rework_attempt_number: int = Field(default=0, ge=0)
    rework_attempt_limit: int = Field(default=1, ge=1)
    bounded_rework_budget_exhausted: bool = False
    rework_non_convergence_detected: bool = False

    continuation_handoff_prepared: bool = False
    rework_handoff_prepared: bool = False

    blocked_reasons: list[str] = Field(default_factory=list)
    prepared_at: datetime | None = None

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
            raise ValueError("disposition handoff may not execute or write")
        return value

    @model_validator(mode="after")
    def validate_handoff_state(
        self,
    ) -> "ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult":
        if self.rework_attempt_limit != 1:
            raise ValueError("disposition handoff rework limit must remain one")
        if self.handoff_status == "blocked":
            if self.handoff_id is not None or self.prepared_at is not None:
                raise ValueError("blocked handoff may not be prepared")
            if self.handoff_kind is not None:
                raise ValueError("blocked handoff may not expose a handoff kind")
            if self.continuation_handoff_prepared or self.rework_handoff_prepared:
                raise ValueError("blocked handoff may not expose prepared work")
            if not self.blocked_reasons:
                raise ValueError("blocked handoff requires a reason")
            replay_reason_present = "handoff_already_prepared" in self.blocked_reasons
            if replay_reason_present != self.prior_handoff_detected:
                raise ValueError("blocked handoff replay contract is invalid")
            if self.prior_handoff_detected and not self.replay_check_completed:
                raise ValueError("blocked handoff replay check must be complete")
            budget_reasons_present = any(
                reason in self.blocked_reasons
                for reason in (
                    "bounded_rework_budget_exhausted",
                    "rework_non_convergence",
                )
            )
            if (
                self.bounded_rework_budget_exhausted
                != self.rework_non_convergence_detected
            ):
                raise ValueError("rework budget exhaustion requires non-convergence")
            if (
                self.bounded_rework_budget_exhausted
                and self.prior_rework_handoff_count < 1
            ):
                raise ValueError("rework budget exhaustion requires a prior handoff")
            if budget_reasons_present != self.bounded_rework_budget_exhausted:
                raise ValueError("rework budget reasons and flags must match")
            if self.bounded_rework_budget_exhausted and (
                self.disposition_type != "AUTO_REWORK"
                or "bounded_rework_budget_exhausted" not in self.blocked_reasons
                or "rework_non_convergence" not in self.blocked_reasons
                or not self.replay_check_completed
                or self.prior_handoff_detected
            ):
                raise ValueError("rework budget exhaustion contract is invalid")
            return self

        required_ids = (
            self.handoff_id,
            self.source_consumption_id,
            self.source_consumption_preflight_message_id,
            self.source_disposition_message_id,
            self.source_review_message_id,
            self.source_diff_message_id,
            self.disposition_id,
        )
        if any(value is None for value in required_ids):
            raise ValueError("prepared handoff requires complete evidence bindings")
        if self.disposition_type not in ("AUTO_CONTINUE", "AUTO_REWORK"):
            raise ValueError("prepared handoff requires an automatic disposition")
        if not self.disposition_reason:
            raise ValueError("prepared handoff requires a disposition reason")
        if not all(
            _LOWER_HEX_SHA256.match(value)
            for value in (
                self.review_result_fingerprint,
                self.revalidated_review_result_fingerprint,
                self.reviewed_diff_sha256,
                self.persisted_source_diff_sha256,
                self.current_diff_sha256,
                self.review_prompt_sha256,
            )
        ):
            raise ValueError("prepared handoff requires valid fingerprints")
        if (
            self.review_result_fingerprint
            != self.revalidated_review_result_fingerprint
        ):
            raise ValueError("prepared handoff requires matching review fingerprints")
        if len(
            {
                self.reviewed_diff_sha256,
                self.persisted_source_diff_sha256,
                self.current_diff_sha256,
            }
        ) != 1:
            raise ValueError("prepared handoff requires matching diff fingerprints")
        if (
            not self.reviewed_scope_paths
            or self.reviewed_scope_paths != self.persisted_source_scope_paths
            or self.reviewed_scope_paths != self.current_scope_paths
        ):
            raise ValueError("prepared handoff requires matching ordered scopes")
        if not self.workspace_path or not self.workspace_path_within_root:
            raise ValueError("prepared handoff requires a trusted workspace")
        if (
            not self.source_consumption_validated
            or not self.replay_check_completed
            or self.prior_handoff_detected
        ):
            raise ValueError("prepared handoff requires validated unreplayed consumption")
        if (
            self.bounded_rework_budget_exhausted
            or self.rework_non_convergence_detected
            or self.blocked_reasons
        ):
            raise ValueError("prepared handoff may not be blocked")
        if (
            self.prepared_at is None
            or self.prepared_at.tzinfo is None
            or self.prepared_at.utcoffset() is None
        ):
            raise ValueError("prepared handoff requires a timezone-aware timestamp")

        if self.disposition_type == "AUTO_CONTINUE":
            if (
                self.handoff_kind != "automatic_continuation"
                or not self.continuation_handoff_prepared
                or self.rework_handoff_prepared
                or self.rework_attempt_number != 0
            ):
                raise ValueError("automatic continuation handoff mapping is invalid")
            return self

        if (
            self.handoff_kind != "bounded_automatic_rework"
            or self.continuation_handoff_prepared
            or not self.rework_handoff_prepared
            or self.prior_rework_handoff_count != 0
            or self.rework_attempt_number != 1
            or self.rework_attempt_limit != 1
        ):
            raise ValueError("bounded automatic rework handoff mapping is invalid")
        return self


__all__ = (
    "DispositionHandoffKind",
    "DispositionHandoffStatus",
    "ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult",
)
