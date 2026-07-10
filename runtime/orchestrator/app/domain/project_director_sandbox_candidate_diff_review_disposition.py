"""Automated readonly review disposition contract for Project Director P21-D-B."""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel


ReviewDispositionStatus = Literal["computed", "blocked"]
ReviewDispositionType = Literal[
    "AUTO_CONTINUE",
    "AUTO_REWORK",
    "ESCALATE_TO_HUMAN",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorSandboxCandidateDiffReviewDispositionResult(DomainModel):
    """Deterministic P21-D-B decision without downstream execution side effects."""

    disposition_status: ReviewDispositionStatus
    disposition_type: ReviewDispositionType | None = None
    source_review_message_id: UUID
    review_result_fingerprint: str = Field(default="", max_length=64)
    disposition_reason: str = ""
    escalation_triggers: list[str] = Field(default_factory=list)
    evaluated_trigger_kinds: list[str] = Field(default_factory=list)
    deferred_trigger_kinds: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)

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
            raise ValueError("review disposition may not execute or authorize writes")
        return value

    @model_validator(mode="after")
    def validate_disposition_state(
        self,
    ) -> "ProjectDirectorSandboxCandidateDiffReviewDispositionResult":
        if self.disposition_status == "computed":
            if self.disposition_type is None:
                raise ValueError("computed review disposition requires a type")
            if not _LOWER_HEX_SHA256.match(self.review_result_fingerprint):
                raise ValueError("computed review disposition requires a fingerprint")
            if not self.disposition_reason:
                raise ValueError("computed review disposition requires a reason")
            if self.blocked_reasons:
                raise ValueError("computed review disposition may not be blocked")
        elif self.disposition_type is not None or self.review_result_fingerprint:
            raise ValueError("blocked review disposition may not contain a decision")
        return self


__all__ = (
    "ProjectDirectorSandboxCandidateDiffReviewDispositionResult",
    "ReviewDispositionStatus",
    "ReviewDispositionType",
)
