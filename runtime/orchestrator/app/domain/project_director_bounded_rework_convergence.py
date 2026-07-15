"""Immutable P25-I-B bounded rework convergence decision contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeAlias
from uuid import UUID, uuid5

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_bounded_rework_candidate_diff import (
    CandidateDiffStatus,
)
from app.domain.project_director_bounded_rework_contract import (
    P25_BOUNDED_REWORK_ATTEMPT_LIMIT,
    ProjectDirectorBoundedReworkAuthorityEnvelope,
    compute_p25_contract_sha256,
    normalize_utc_datetime,
    require_optional_sha256,
    require_sha256,
)


P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SCHEMA_VERSION = (
    "p25-i-b-convergence-decision.v1"
)
P25_BOUNDED_REWORK_CONVERGENCE_DECISION_REPLAY_SCHEMA_VERSION = (
    "p25-i-b-convergence-decision-replay.v1"
)
P25_BOUNDED_REWORK_CONVERGENCE_DECISION_NAMESPACE = UUID(
    "b0f9aa99-30b7-54eb-92af-b78e576f37c0"
)

BoundedReworkConvergenceDecisionType: TypeAlias = Literal[
    "CONVERGED",
    "NEXT_ATTEMPT_ELIGIBLE",
    "ESCALATE_TO_HUMAN",
]
BoundedReworkConvergenceDecisionReason: TypeAlias = Literal[
    "review_converged",
    "changed_blocking_findings",
    "empty_diff",
    "unchanged_diff",
    "repeated_review_semantic_fingerprint",
    "repeated_canonical_blocking_findings",
    "attempt_limit_exhausted",
    "high_review_risk",
]


class ProjectDirectorBoundedReworkConvergenceDecision(DomainModel):
    """One deterministic terminal or next-attempt eligibility decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-i-b-convergence-decision.v1"] = (
        P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SCHEMA_VERSION
    )
    decision_id: UUID
    decision_fingerprint: str = Field(min_length=64, max_length=64)
    decision_replay_key: str = Field(min_length=64, max_length=64)
    created_at: datetime
    decision_type: BoundedReworkConvergenceDecisionType
    decision_reason: BoundedReworkConvergenceDecisionReason

    authority: ProjectDirectorBoundedReworkAuthorityEnvelope

    source_package_id: UUID
    source_package_fingerprint: str = Field(min_length=64, max_length=64)
    source_attempt_id: UUID
    source_executor_outcome_id: UUID

    source_candidate_diff_message_id: UUID
    source_candidate_diff_id: UUID
    source_candidate_diff_fingerprint: str = Field(min_length=64, max_length=64)
    source_candidate_diff_replay_key: str = Field(min_length=64, max_length=64)
    candidate_diff_status: CandidateDiffStatus

    source_review_outcome_message_id: UUID | None = None
    source_review_outcome_id: UUID | None = None
    source_review_outcome_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    source_review_outcome_replay_key: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    source_review_result_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    current_review_semantic_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )

    source_p22_summary_message_id: UUID | None = None
    source_human_escalation_package_message_id: UUID | None = None

    current_rework_attempt_index: int = Field(ge=0, lt=3)
    rework_attempt_limit: int
    next_rework_attempt_index: int | None = Field(default=None, ge=1, lt=3)

    previous_diff_sha256: str = Field(min_length=64, max_length=64)
    current_diff_sha256: str = Field(min_length=64, max_length=64)
    previous_review_semantic_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    previous_blocking_findings_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    current_blocking_findings_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )

    diff_changed: bool
    review_semantics_changed: bool | None = None
    blocking_findings_changed: bool | None = None

    converged: bool
    next_attempt_eligible: bool
    human_escalation_required: bool
    automatic_processing_terminal: bool

    next_p23_intent_created: Literal[False] = False
    next_p23_consumption_created: Literal[False] = False
    next_package_created: Literal[False] = False
    next_reservation_created: Literal[False] = False
    next_claim_created: Literal[False] = False
    executor_called: Literal[False] = False
    reviewer_called: Literal[False] = False
    provider_called: Literal[False] = False
    task_created: Literal[False] = False
    run_created: Literal[False] = False
    worker_started: Literal[False] = False
    main_project_file_written: Literal[False] = False
    sandbox_file_written: Literal[False] = False
    patch_applied: Literal[False] = False
    git_write_performed: Literal[False] = False
    product_runtime_git_write_allowed: Literal[False] = False
    ai_project_director_total_loop: Literal["Partial"] = "Partial"

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value, label="P25-I-B decision created_at")

    @field_validator(
        "decision_fingerprint",
        "decision_replay_key",
        "source_package_fingerprint",
        "source_candidate_diff_fingerprint",
        "source_candidate_diff_replay_key",
        "previous_diff_sha256",
        "current_diff_sha256",
        "previous_review_semantic_fingerprint",
        "previous_blocking_findings_fingerprint",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return require_sha256(value, label="P25-I-B decision hash")

    @field_validator(
        "source_review_outcome_fingerprint",
        "source_review_outcome_replay_key",
        "source_review_result_fingerprint",
        "current_review_semantic_fingerprint",
        "current_blocking_findings_fingerprint",
    )
    @classmethod
    def validate_optional_hashes(cls, value: str | None) -> str | None:
        return require_optional_sha256(value, label="P25-I-B optional decision hash")

    @model_validator(mode="after")
    def validate_decision(self) -> "ProjectDirectorBoundedReworkConvergenceDecision":
        if (
            self.source_candidate_diff_message_id != self.source_candidate_diff_id
            or (
                self.source_review_outcome_message_id is not None
                and self.source_review_outcome_message_id
                != self.source_review_outcome_id
            )
            or self.authority.source_task_id != self.authority.target_task_id
        ):
            raise ValueError("P25-I-B decision lineage identities conflict")
        if self.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT:
            raise ValueError("P25-I-B decision attempt limit must equal three")
        if self.diff_changed != (self.current_diff_sha256 != self.previous_diff_sha256):
            raise ValueError("P25-I-B diff progress flag does not match hashes")

        review_values = (
            self.source_review_outcome_message_id,
            self.source_review_outcome_id,
            self.source_review_outcome_fingerprint,
            self.source_review_outcome_replay_key,
            self.source_review_result_fingerprint,
            self.current_review_semantic_fingerprint,
            self.source_p22_summary_message_id,
            self.current_blocking_findings_fingerprint,
            self.review_semantics_changed,
            self.blocking_findings_changed,
        )
        if self.candidate_diff_status == "generated":
            if any(value is None for value in review_values):
                raise ValueError("generated P25-I-B decisions require fresh review and P22")
            assert self.current_review_semantic_fingerprint is not None
            assert self.current_blocking_findings_fingerprint is not None
            if self.review_semantics_changed != (
                self.current_review_semantic_fingerprint
                != self.previous_review_semantic_fingerprint
            ):
                raise ValueError("P25-I-B review semantic progress flag is invalid")
            if self.blocking_findings_changed != (
                self.current_blocking_findings_fingerprint
                != self.previous_blocking_findings_fingerprint
            ):
                raise ValueError("P25-I-B finding progress flag is invalid")
        elif any(value is not None for value in review_values):
            raise ValueError("non-convergence diff cannot forge review or P22 lineage")

        if self.decision_replay_key != self.compute_replay_key(
            source_candidate_diff_replay_key=self.source_candidate_diff_replay_key,
            source_review_outcome_replay_key=(
                self.source_review_outcome_replay_key
            ),
            source_p22_summary_message_id=self.source_p22_summary_message_id,
            current_rework_attempt_index=self.current_rework_attempt_index,
        ):
            raise ValueError("P25-I-B decision replay key does not match")
        if self.decision_id != uuid5(
            P25_BOUNDED_REWORK_CONVERGENCE_DECISION_NAMESPACE,
            self.decision_replay_key,
        ):
            raise ValueError("P25-I-B decision identity is not deterministic")
        if self.decision_fingerprint != self.compute_fingerprint():
            raise ValueError("P25-I-B decision fingerprint does not match")

        if self.decision_type == "CONVERGED":
            self._validate_converged()
        elif self.decision_type == "NEXT_ATTEMPT_ELIGIBLE":
            self._validate_next_attempt()
        else:
            self._validate_escalation()
        return self

    def _validate_converged(self) -> None:
        if (
            self.candidate_diff_status != "generated"
            or self.decision_reason != "review_converged"
            or (self.converged, self.next_attempt_eligible)
            != (True, False)
            or self.human_escalation_required
            or not self.automatic_processing_terminal
            or self.next_rework_attempt_index is not None
            or self.source_human_escalation_package_message_id is not None
        ):
            raise ValueError("P25-I-B CONVERGED state is invalid")

    def _validate_next_attempt(self) -> None:
        if (
            self.candidate_diff_status != "generated"
            or self.decision_reason != "changed_blocking_findings"
            or self.converged
            or not self.next_attempt_eligible
            or self.human_escalation_required
            or self.automatic_processing_terminal
            or not self.diff_changed
            or self.review_semantics_changed is not True
            or self.blocking_findings_changed is not True
            or self.next_rework_attempt_index
            != self.current_rework_attempt_index + 1
            or self.next_rework_attempt_index >= self.rework_attempt_limit
            or self.source_human_escalation_package_message_id is not None
        ):
            raise ValueError("P25-I-B NEXT_ATTEMPT_ELIGIBLE state is invalid")

    def _validate_escalation(self) -> None:
        if self.decision_reason not in {
            "empty_diff",
            "unchanged_diff",
            "repeated_review_semantic_fingerprint",
            "repeated_canonical_blocking_findings",
            "attempt_limit_exhausted",
            "high_review_risk",
        }:
            raise ValueError("P25-I-B escalation reason is invalid")
        if (
            self.converged
            or self.next_attempt_eligible
            or not self.human_escalation_required
            or not self.automatic_processing_terminal
            or self.next_rework_attempt_index is not None
        ):
            raise ValueError("P25-I-B ESCALATE_TO_HUMAN state is invalid")
        if self.decision_reason in {"empty_diff", "unchanged_diff"}:
            if (
                self.candidate_diff_status != "non_convergence"
                or self.source_human_escalation_package_message_id is not None
                or (
                    self.decision_reason == "unchanged_diff"
                    and self.diff_changed
                )
            ):
                raise ValueError("P25-I-B diff non-convergence state is invalid")
        elif self.candidate_diff_status != "generated":
            raise ValueError("P25-I-B reviewed escalation requires generated diff")
        if (
            self.decision_reason == "repeated_review_semantic_fingerprint"
            and (
                not self.diff_changed
                or self.review_semantics_changed is not False
            )
        ):
            raise ValueError("P25-I-B repeated review semantic state is invalid")
        if (
            self.decision_reason == "repeated_canonical_blocking_findings"
            and (
                not self.diff_changed
                or self.review_semantics_changed is not True
                or self.blocking_findings_changed is not False
            )
        ):
            raise ValueError("P25-I-B repeated finding state is invalid")
        if (
            self.decision_reason == "attempt_limit_exhausted"
            and (
                not self.diff_changed
                or self.review_semantics_changed is not True
                or self.blocking_findings_changed is not True
                or self.current_rework_attempt_index + 1
                < self.rework_attempt_limit
            )
        ):
            raise ValueError("P25-I-B attempt exhaustion state is invalid")
        if self.decision_reason == "high_review_risk":
            if self.source_human_escalation_package_message_id is None:
                raise ValueError("P25-I-B high-risk escalation requires P22 package")
        elif self.source_human_escalation_package_message_id is not None:
            raise ValueError("only high-risk escalation may bind an existing package")

    @staticmethod
    def compute_replay_key(
        *,
        source_candidate_diff_replay_key: str,
        source_review_outcome_replay_key: str | None,
        source_p22_summary_message_id: UUID | None,
        current_rework_attempt_index: int,
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "schema_version": (
                    P25_BOUNDED_REWORK_CONVERGENCE_DECISION_REPLAY_SCHEMA_VERSION
                ),
                "source_candidate_diff_replay_key": source_candidate_diff_replay_key,
                "source_review_outcome_replay_key": source_review_outcome_replay_key,
                "source_p22_summary_message_id": source_p22_summary_message_id,
                "current_rework_attempt_index": current_rework_attempt_index,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p25_contract_sha256(
            self.model_dump(
                mode="python",
                exclude={"decision_id", "decision_fingerprint", "created_at"},
            )
        )


__all__ = (
    "BoundedReworkConvergenceDecisionReason",
    "BoundedReworkConvergenceDecisionType",
    "P25_BOUNDED_REWORK_CONVERGENCE_DECISION_NAMESPACE",
    "P25_BOUNDED_REWORK_CONVERGENCE_DECISION_REPLAY_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_CONVERGENCE_DECISION_SCHEMA_VERSION",
    "ProjectDirectorBoundedReworkConvergenceDecision",
)
