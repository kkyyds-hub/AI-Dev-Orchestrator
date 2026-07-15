"""Immutable P25-I-C2 bounded rework terminal escalation package."""

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
    require_trimmed_text,
    validate_unique_paths,
)


P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SCHEMA_VERSION = (
    "p25-i-c2-terminal-escalation-package.v1"
)
P25_BOUNDED_REWORK_TERMINAL_ESCALATION_REPLAY_SCHEMA_VERSION = (
    "p25-i-c2-terminal-escalation-package-replay.v1"
)
P25_BOUNDED_REWORK_TERMINAL_ESCALATION_NAMESPACE = UUID(
    "e767d5d3-794d-5c50-82ee-71079f67ed83"
)

BoundedReworkTerminalEscalationReason: TypeAlias = Literal[
    "empty_diff",
    "unchanged_diff",
    "repeated_review_semantic_fingerprint",
    "repeated_canonical_blocking_findings",
    "attempt_limit_exhausted",
]
TerminalEscalationFindingSource: TypeAlias = Literal[
    "prior_review",
    "current_review",
]


class ProjectDirectorBoundedReworkTerminalEscalationFinding(DomainModel):
    """Canonical unresolved finding without review prose or raw output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_source: TerminalEscalationFindingSource
    severity: Literal["medium", "high"]
    title: str = Field(min_length=1, max_length=200)
    evidence_paths: tuple[str, ...] = Field(min_length=1, max_length=12)
    recommended_action: str = Field(min_length=1, max_length=500)

    @field_validator("title", "recommended_action")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return require_trimmed_text(value, label="terminal escalation finding")

    @field_validator("evidence_paths")
    @classmethod
    def validate_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        values = validate_unique_paths(values, allow_empty=False)
        if values != tuple(sorted(values)):
            raise ValueError("terminal escalation finding paths must be sorted")
        return values


class ProjectDirectorBoundedReworkTerminalEscalationPackage(DomainModel):
    """One deterministic terminal package awaiting a future human decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-i-c2-terminal-escalation-package.v1"] = (
        P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SCHEMA_VERSION
    )
    terminal_escalation_package_id: UUID
    package_fingerprint: str = Field(min_length=64, max_length=64)
    package_replay_key: str = Field(min_length=64, max_length=64)
    created_at: datetime
    package_status: Literal["prepared"] = "prepared"

    authority: ProjectDirectorBoundedReworkAuthorityEnvelope

    source_convergence_decision_message_id: UUID
    source_convergence_decision_id: UUID
    source_convergence_decision_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    source_convergence_decision_replay_key: str = Field(
        min_length=64,
        max_length=64,
    )
    decision_reason: BoundedReworkTerminalEscalationReason

    source_package_id: UUID
    source_package_fingerprint: str = Field(min_length=64, max_length=64)
    source_attempt_id: UUID
    source_executor_outcome_id: UUID

    source_candidate_diff_message_id: UUID
    source_candidate_diff_id: UUID
    source_candidate_diff_fingerprint: str = Field(min_length=64, max_length=64)
    candidate_diff_status: CandidateDiffStatus
    candidate_non_convergence_reason: Literal[
        "empty_diff",
        "unchanged_diff",
    ] | None = None

    source_review_outcome_message_id: UUID | None = None
    source_review_outcome_id: UUID | None = None
    source_review_outcome_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    source_review_result_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    source_p22_summary_message_id: UUID | None = None

    current_rework_attempt_index: int = Field(ge=0, lt=3)
    rework_attempt_limit: int
    previous_diff_sha256: str = Field(min_length=64, max_length=64)
    current_diff_sha256: str = Field(min_length=64, max_length=64)
    previous_review_semantic_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    current_review_semantic_fingerprint: str | None = Field(
        default=None,
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

    unresolved_blocking_findings: tuple[
        ProjectDirectorBoundedReworkTerminalEscalationFinding,
        ...,
    ] = Field(min_length=1)
    risk_summary: str = Field(min_length=1, max_length=500)
    escalation_scope: Literal["bounded_rework_terminal"] = (
        "bounded_rework_terminal"
    )
    proposed_human_decision_scope: Literal[
        "resolve_bounded_rework_terminal_escalation"
    ] = "resolve_bounded_rework_terminal_escalation"

    human_decision_recorded: Literal[False] = False
    approval_request_created: Literal[False] = False
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
    automatic_processing_terminal: Literal[True] = True
    ai_project_director_total_loop: Literal["Partial"] = "Partial"

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(
            value,
            label="P25-I-C2 terminal escalation created_at",
        )

    @field_validator(
        "package_fingerprint",
        "package_replay_key",
        "source_convergence_decision_fingerprint",
        "source_convergence_decision_replay_key",
        "source_package_fingerprint",
        "source_candidate_diff_fingerprint",
        "previous_diff_sha256",
        "current_diff_sha256",
        "previous_review_semantic_fingerprint",
        "previous_blocking_findings_fingerprint",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return require_sha256(value, label="P25-I-C2 terminal escalation hash")

    @field_validator(
        "source_review_outcome_fingerprint",
        "source_review_result_fingerprint",
        "current_review_semantic_fingerprint",
        "current_blocking_findings_fingerprint",
    )
    @classmethod
    def validate_optional_hashes(cls, value: str | None) -> str | None:
        return require_optional_sha256(
            value,
            label="P25-I-C2 optional terminal escalation hash",
        )

    @model_validator(mode="after")
    def validate_package(
        self,
    ) -> "ProjectDirectorBoundedReworkTerminalEscalationPackage":
        if (
            self.source_convergence_decision_message_id
            != self.source_convergence_decision_id
            or self.source_candidate_diff_message_id
            != self.source_candidate_diff_id
            or (
                self.source_review_outcome_message_id is not None
                and self.source_review_outcome_message_id
                != self.source_review_outcome_id
            )
            or self.authority.source_task_id != self.authority.target_task_id
            or self.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT
        ):
            raise ValueError("P25-I-C2 terminal escalation lineage is invalid")
        if self.package_replay_key != self.compute_replay_key(
            source_convergence_decision_replay_key=(
                self.source_convergence_decision_replay_key
            ),
            decision_reason=self.decision_reason,
        ):
            raise ValueError("P25-I-C2 terminal escalation replay key is invalid")
        if self.terminal_escalation_package_id != uuid5(
            P25_BOUNDED_REWORK_TERMINAL_ESCALATION_NAMESPACE,
            self.package_replay_key,
        ):
            raise ValueError("P25-I-C2 terminal escalation identity is invalid")
        if self.package_fingerprint != self.compute_fingerprint():
            raise ValueError("P25-I-C2 terminal escalation fingerprint is invalid")
        if self.risk_summary != self.build_risk_summary(
            reason=self.decision_reason,
            attempt_index=self.current_rework_attempt_index,
            attempt_limit=self.rework_attempt_limit,
        ):
            raise ValueError("P25-I-C2 terminal escalation risk summary is invalid")

        finding_hashes = tuple(
            compute_p25_contract_sha256(finding.model_dump(mode="python"))
            for finding in self.unresolved_blocking_findings
        )
        if (
            len(finding_hashes) != len(set(finding_hashes))
            or finding_hashes != tuple(sorted(finding_hashes))
        ):
            raise ValueError("P25-I-C2 terminal findings must be unique and sorted")

        review_values = (
            self.source_review_outcome_message_id,
            self.source_review_outcome_id,
            self.source_review_outcome_fingerprint,
            self.source_review_result_fingerprint,
            self.source_p22_summary_message_id,
            self.current_review_semantic_fingerprint,
            self.current_blocking_findings_fingerprint,
        )
        if self.candidate_diff_status == "non_convergence":
            if any(value is not None for value in review_values):
                raise ValueError("non-convergence escalation cannot bind fresh review")
            if any(
                finding.finding_source != "prior_review"
                for finding in self.unresolved_blocking_findings
            ):
                raise ValueError("non-convergence escalation requires prior findings")
        else:
            if any(value is None for value in review_values):
                raise ValueError("generated escalation requires fresh review and P22")
            if (
                self.candidate_non_convergence_reason is not None
                or self.current_diff_sha256 == self.previous_diff_sha256
            ):
                raise ValueError("generated escalation requires a changed diff")
            if any(
                finding.finding_source != "current_review"
                for finding in self.unresolved_blocking_findings
            ):
                raise ValueError("generated escalation requires current findings")

        if self.decision_reason == "empty_diff":
            if (
                self.candidate_diff_status != "non_convergence"
                or self.candidate_non_convergence_reason != "empty_diff"
            ):
                raise ValueError("empty-diff escalation facts are invalid")
        elif self.decision_reason == "unchanged_diff":
            if (
                self.candidate_diff_status != "non_convergence"
                or self.candidate_non_convergence_reason != "unchanged_diff"
                or self.current_diff_sha256 != self.previous_diff_sha256
            ):
                raise ValueError("unchanged-diff escalation facts are invalid")
        elif self.decision_reason == "repeated_review_semantic_fingerprint":
            if (
                self.candidate_diff_status != "generated"
                or self.current_review_semantic_fingerprint
                != self.previous_review_semantic_fingerprint
            ):
                raise ValueError("repeated-semantic escalation facts are invalid")
        elif self.decision_reason == "repeated_canonical_blocking_findings":
            if (
                self.candidate_diff_status != "generated"
                or self.current_review_semantic_fingerprint
                == self.previous_review_semantic_fingerprint
                or self.current_blocking_findings_fingerprint
                != self.previous_blocking_findings_fingerprint
            ):
                raise ValueError("repeated-finding escalation facts are invalid")
        elif (
            self.candidate_diff_status != "generated"
            or self.current_review_semantic_fingerprint
            == self.previous_review_semantic_fingerprint
            or self.current_blocking_findings_fingerprint
            == self.previous_blocking_findings_fingerprint
            or self.current_rework_attempt_index != 2
            or self.current_rework_attempt_index + 1 < self.rework_attempt_limit
        ):
            raise ValueError("attempt-exhaustion escalation facts are invalid")
        return self

    @staticmethod
    def compute_replay_key(
        *,
        source_convergence_decision_replay_key: str,
        decision_reason: BoundedReworkTerminalEscalationReason,
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "schema_version": (
                    P25_BOUNDED_REWORK_TERMINAL_ESCALATION_REPLAY_SCHEMA_VERSION
                ),
                "source_convergence_decision_replay_key": (
                    source_convergence_decision_replay_key
                ),
                "decision_reason": decision_reason,
            }
        )

    @staticmethod
    def build_risk_summary(
        *,
        reason: BoundedReworkTerminalEscalationReason,
        attempt_index: int,
        attempt_limit: int,
    ) -> str:
        return (
            f"P25 automatic bounded rework terminated because {reason}. "
            f"Attempt {attempt_index} of {attempt_limit} cannot continue "
            "automatically. Human review is required before any further "
            "execution or delivery action."
        )

    def compute_fingerprint(self) -> str:
        return compute_p25_contract_sha256(
            self.model_dump(
                mode="python",
                exclude={
                    "terminal_escalation_package_id",
                    "created_at",
                    "package_fingerprint",
                },
            )
        )


__all__ = (
    "BoundedReworkTerminalEscalationReason",
    "P25_BOUNDED_REWORK_TERMINAL_ESCALATION_NAMESPACE",
    "P25_BOUNDED_REWORK_TERMINAL_ESCALATION_REPLAY_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_TERMINAL_ESCALATION_SCHEMA_VERSION",
    "ProjectDirectorBoundedReworkTerminalEscalationFinding",
    "ProjectDirectorBoundedReworkTerminalEscalationPackage",
    "TerminalEscalationFindingSource",
)
