"""Single-source human escalation package contract for Project Director P21-D-D1."""

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
from app.domain.project_director_sandbox_candidate_diff_review_output import (
    ProjectDirectorSandboxCandidateDiffReviewFinding,
)


HumanEscalationPackageStatus = Literal["prepared", "blocked"]
HumanEscalationScope = Literal["single_source_review"]
ProposedHumanDecisionScope = Literal[
    "resolve_single_source_review_escalation"
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult(
    DomainModel
):
    """Append-only P21-D-D1 package without a human decision or execution."""

    package_status: HumanEscalationPackageStatus
    escalation_package_id: UUID | None = None

    source_disposition_message_id: UUID
    source_review_message_id: UUID | None = None
    source_preflight_message_id: UUID | None = None
    source_diff_message_id: UUID | None = None
    disposition_id: UUID | None = None
    disposition_type: ReviewDispositionType | None = None
    disposition_reason: str = ""

    review_result_fingerprint: str = Field(default="", max_length=64)
    revalidated_review_result_fingerprint: str = Field(default="", max_length=64)
    aggregate_evidence_fingerprint: str = Field(default="", max_length=64)

    escalation_triggers: list[str] = Field(default_factory=list)
    escalation_scope: HumanEscalationScope | None = None
    related_task_ids: list[UUID] = Field(default_factory=list)
    related_review_message_ids: list[UUID] = Field(default_factory=list)
    unresolved_blocking_findings: list[
        ProjectDirectorSandboxCandidateDiffReviewFinding
    ] = Field(default_factory=list)
    risk_summary: str = Field(default="", max_length=2_000)
    proposed_human_decision_scope: ProposedHumanDecisionScope | None = None

    source_review_validated: bool = False
    replay_check_completed: bool = False
    prior_escalation_package_detected: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)
    package_created_at: datetime | None = None

    continuation_started: bool = False
    rework_started: bool = False
    human_escalation_package_created: bool = False
    human_decision_recorded: bool = False
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
        "continuation_started",
        "rework_started",
        "human_decision_recorded",
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
            raise ValueError("human escalation package may not execute or write")
        return value

    @model_validator(mode="after")
    def validate_package_state(
        self,
    ) -> "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult":
        if self.package_status == "blocked":
            if (
                self.escalation_package_id is not None
                or self.package_created_at is not None
            ):
                raise ValueError("blocked escalation package may not be created")
            if self.human_escalation_package_created:
                raise ValueError("blocked escalation package may not report creation")
            if self.aggregate_evidence_fingerprint:
                raise ValueError(
                    "blocked escalation package may not expose an aggregate fingerprint"
                )
            if not self.blocked_reasons:
                raise ValueError("blocked escalation package requires a reason")
            return self

        if self.escalation_package_id is None or self.package_created_at is None:
            raise ValueError(
                "prepared escalation package requires identity and timestamp"
            )
        if self.package_created_at.tzinfo is None:
            raise ValueError(
                "prepared escalation package timestamp must be timezone-aware"
            )
        if self.disposition_type != "ESCALATE_TO_HUMAN":
            raise ValueError(
                "prepared escalation package requires human escalation disposition"
            )
        if (
            self.source_review_message_id is None
            or self.source_preflight_message_id is None
            or self.source_diff_message_id is None
            or self.disposition_id is None
        ):
            raise ValueError(
                "prepared escalation package requires exact source bindings"
            )
        if not _LOWER_HEX_SHA256.match(self.review_result_fingerprint):
            raise ValueError(
                "prepared escalation package requires a review fingerprint"
            )
        if not _LOWER_HEX_SHA256.match(
            self.revalidated_review_result_fingerprint
        ):
            raise ValueError(
                "prepared escalation package requires revalidated evidence"
            )
        if self.review_result_fingerprint != self.revalidated_review_result_fingerprint:
            raise ValueError(
                "prepared escalation package requires matching review fingerprints"
            )
        if not _LOWER_HEX_SHA256.match(self.aggregate_evidence_fingerprint):
            raise ValueError("prepared escalation package requires aggregate evidence")
        if self.escalation_triggers != ["high_review_risk"]:
            raise ValueError(
                "prepared escalation package requires the exact escalation trigger"
            )
        if self.escalation_scope != "single_source_review":
            raise ValueError("prepared escalation package requires single-source scope")
        if len(self.related_task_ids) != 1 or len(self.related_review_message_ids) != 1:
            raise ValueError(
                "prepared escalation package requires one task and one review"
            )
        if self.related_review_message_ids[0] != self.source_review_message_id:
            raise ValueError("prepared escalation package review binding must be exact")
        if not self.risk_summary:
            raise ValueError("prepared escalation package requires a risk summary")
        if (
            self.proposed_human_decision_scope
            != "resolve_single_source_review_escalation"
        ):
            raise ValueError(
                "prepared escalation package requires bounded decision scope"
            )
        if not self.source_review_validated:
            raise ValueError(
                "prepared escalation package requires validated review evidence"
            )
        if not self.replay_check_completed or self.prior_escalation_package_detected:
            raise ValueError(
                "prepared escalation package requires a clean replay check"
            )
        if not self.human_escalation_package_created:
            raise ValueError(
                "prepared escalation package must report append-only creation"
            )
        if self.blocked_reasons:
            raise ValueError("prepared escalation package may not be blocked")
        return self


__all__ = (
    "HumanEscalationPackageStatus",
    "HumanEscalationScope",
    "ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult",
    "ProposedHumanDecisionScope",
)
