"""Immutable P24 Task completion-policy contracts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime


TASK_COMPLETION_POLICY_PROPOSAL_SCHEMA_VERSION = (
    "p24-b-completion-policy-proposal.v1"
)
TASK_COMPLETION_POLICY_DECISION_SCHEMA_VERSION = (
    "p24-b-completion-policy-decision.v1"
)
TASK_COMPLETION_POLICY_SNAPSHOT_SCHEMA_VERSION = (
    "p24-b-completion-policy-snapshot.v1"
)

TaskCompletionRequirement = Literal[
    "required",
    "not_required",
    "unresolved",
]
ConfirmedTaskCompletionRequirement = Literal["required", "not_required"]
TaskCompletionPolicyStatus = Literal[
    "proposed",
    "confirmed",
    "superseded",
    "blocked",
]
TaskCompletionPolicyResultStatus = Literal[
    "proposal_prepared",
    "proposal_replayed",
    "decision_confirmed",
    "decision_replayed",
    "policy_revalidated",
    "blocked",
]
TaskCompletionPolicyBlockedReason = Literal[
    "completion_policy_plan_missing",
    "completion_policy_plan_not_confirmed",
    "completion_policy_task_creation_record_missing",
    "completion_policy_task_not_in_plan",
    "completion_policy_task_lineage_invalid",
    "completion_policy_proposal_missing",
    "completion_policy_proposal_schema_mismatch",
    "completion_policy_proposal_fingerprint_mismatch",
    "completion_policy_proposal_replay_conflict",
    "completion_policy_decision_invalid",
    "completion_policy_decision_actor_invalid",
    "completion_policy_decision_reason_missing",
    "completion_policy_decision_evidence_kind_missing",
    "completion_policy_decision_conflict",
    "completion_policy_snapshot_missing",
    "completion_policy_snapshot_schema_mismatch",
    "completion_policy_snapshot_fingerprint_mismatch",
    "completion_policy_snapshot_lineage_invalid",
    "completion_policy_version_conflict",
    "completion_policy_unresolved",
    "completion_policy_git_boundary_violation",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class _ImmutablePolicyModel(DomainModel):
    model_config = ConfigDict(frozen=True)

    @field_validator("created_at", mode="after", check_fields=False)
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)  # type: ignore[return-value]

    @field_validator(
        "proposal_fingerprint",
        "proposal_replay_key",
        "policy_source_bundle_fingerprint",
        "source_plan_fingerprint",
        "source_task_fingerprint",
        "decision_fingerprint",
        "completion_policy_fingerprint",
        "source_proposal_fingerprint",
        "source_decision_fingerprint",
        mode="after",
        check_fields=False,
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("completion policy fingerprints must be lowercase SHA-256")
        return value

    @field_validator("forbidden_actions", mode="after", check_fields=False)
    @classmethod
    def require_git_boundary(cls, value: list[str]) -> list[str]:
        if "no_product_runtime_git_write" not in value:
            raise ValueError("completion policy must preserve the runtime Git boundary")
        if len(value) != len(set(value)):
            raise ValueError("completion policy forbidden actions must be unique")
        return value


class ProjectDirectorTaskCompletionPolicyProposal(_ImmutablePolicyModel):
    """Append-only, non-authoritative policy recommendation for one Task."""

    schema_version: Literal["p24-b-completion-policy-proposal.v1"] = (
        TASK_COMPLETION_POLICY_PROPOSAL_SCHEMA_VERSION
    )
    proposal_id: UUID
    proposal_fingerprint: str = Field(min_length=64, max_length=64)
    proposal_replay_key: str = Field(min_length=64, max_length=64)
    proposal_status: Literal["proposed"] = "proposed"
    created_at: datetime

    session_id: UUID
    project_id: UUID
    plan_version_id: UUID
    plan_version_no: int = Field(ge=1)
    task_creation_record_id: UUID
    task_id: UUID

    policy_source_bundle_fingerprint: str = Field(min_length=64, max_length=64)
    source_plan_fingerprint: str = Field(min_length=64, max_length=64)
    source_task_fingerprint: str = Field(min_length=64, max_length=64)
    source_config_fingerprints: dict[str, str] = Field(default_factory=dict)

    review_requirement_proposal: TaskCompletionRequirement
    verification_requirement_proposal: TaskCompletionRequirement
    delivery_requirement_proposal: TaskCompletionRequirement
    approval_requirement_proposal: TaskCompletionRequirement

    review_proposal_sources: list[str] = Field(default_factory=list)
    verification_proposal_sources: list[str] = Field(default_factory=list)
    delivery_proposal_sources: list[str] = Field(default_factory=list)
    approval_proposal_sources: list[str] = Field(default_factory=list)

    review_reason_codes: list[str] = Field(default_factory=list)
    verification_reason_codes: list[str] = Field(default_factory=list)
    delivery_reason_codes: list[str] = Field(default_factory=list)
    approval_reason_codes: list[str] = Field(default_factory=list)

    supersedes_proposal_id: UUID | None = None
    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: list[str]

    @field_validator("source_config_fingerprints")
    @classmethod
    def validate_config_fingerprints(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not key.strip() or not _SHA256.fullmatch(item) for key, item in value.items()):
            raise ValueError("config fingerprint entries must be named SHA-256 values")
        return dict(sorted(value.items()))

    @model_validator(mode="after")
    def prohibit_automatic_not_required(self) -> "ProjectDirectorTaskCompletionPolicyProposal":
        requirements = (
            self.review_requirement_proposal,
            self.verification_requirement_proposal,
            self.delivery_requirement_proposal,
            self.approval_requirement_proposal,
        )
        if "not_required" in requirements:
            raise ValueError("a policy proposal cannot infer not_required")
        if self.product_runtime_git_write_allowed:
            raise ValueError("product runtime Git writes are forbidden")
        return self


class ProjectDirectorTaskCompletionPolicyDecision(_ImmutablePolicyModel):
    """Explicit human-owner decision that consumes one exact proposal."""

    schema_version: Literal["p24-b-completion-policy-decision.v1"] = (
        TASK_COMPLETION_POLICY_DECISION_SCHEMA_VERSION
    )
    decision_id: UUID
    decision_fingerprint: str = Field(min_length=64, max_length=64)
    created_at: datetime

    proposal_id: UUID
    proposal_fingerprint: str = Field(min_length=64, max_length=64)
    session_id: UUID
    project_id: UUID
    plan_version_id: UUID
    task_creation_record_id: UUID
    task_id: UUID

    review_requirement: ConfirmedTaskCompletionRequirement
    verification_requirement: ConfirmedTaskCompletionRequirement
    delivery_requirement: ConfirmedTaskCompletionRequirement
    approval_requirement: ConfirmedTaskCompletionRequirement

    review_reason_codes: list[str] = Field(default_factory=list)
    verification_reason_codes: list[str] = Field(default_factory=list)
    delivery_reason_codes: list[str] = Field(default_factory=list)
    approval_reason_codes: list[str] = Field(default_factory=list)

    review_acceptable_evidence_kinds: list[str] = Field(default_factory=list)
    verification_acceptable_evidence_kinds: list[str] = Field(default_factory=list)
    delivery_acceptable_evidence_kinds: list[str] = Field(default_factory=list)
    approval_acceptable_terminal_results: list[str] = Field(default_factory=list)

    confirmed_source_evidence_ids: list[UUID] = Field(default_factory=list)
    decision_actor_type: Literal["human_owner"] = "human_owner"
    decided_by: str = Field(min_length=1, max_length=200)
    client_request_id: str = Field(min_length=1, max_length=200)
    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: list[str]

    @field_validator(
        "review_reason_codes",
        "verification_reason_codes",
        "delivery_reason_codes",
        "approval_reason_codes",
        "review_acceptable_evidence_kinds",
        "verification_acceptable_evidence_kinds",
        "delivery_acceptable_evidence_kinds",
        "approval_acceptable_terminal_results",
    )
    @classmethod
    def normalize_string_sets(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("completion policy decision lists must be unique")
        return normalized

    @field_validator("confirmed_source_evidence_ids")
    @classmethod
    def require_unique_evidence_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("confirmed source evidence IDs must be unique")
        return value

    @field_validator("decided_by", "client_request_id")
    @classmethod
    def normalize_owner_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("owner identity and client request ID must be non-empty")
        return normalized

    @field_validator("decided_by")
    @classmethod
    def prohibit_non_human_owner_identity(cls, value: str) -> str:
        if value.casefold() in {"system", "assistant", "ai_project_director"}:
            raise ValueError("decision owner must identify an explicit human owner")
        return value

    @model_validator(mode="after")
    def validate_explicit_axis_decisions(self) -> "ProjectDirectorTaskCompletionPolicyDecision":
        axes = (
            (
                self.review_requirement,
                self.review_reason_codes,
                self.review_acceptable_evidence_kinds,
            ),
            (
                self.verification_requirement,
                self.verification_reason_codes,
                self.verification_acceptable_evidence_kinds,
            ),
            (
                self.delivery_requirement,
                self.delivery_reason_codes,
                self.delivery_acceptable_evidence_kinds,
            ),
            (
                self.approval_requirement,
                self.approval_reason_codes,
                self.approval_acceptable_terminal_results,
            ),
        )
        for requirement, reasons, acceptable_results in axes:
            if requirement == "not_required" and not reasons:
                raise ValueError("not_required requires a reason code")
            if requirement == "required" and not acceptable_results:
                raise ValueError("required requires acceptable evidence or result kinds")
        if self.product_runtime_git_write_allowed:
            raise ValueError("product runtime Git writes are forbidden")
        return self


class ProjectDirectorTaskCompletionPolicySnapshot(_ImmutablePolicyModel):
    """Immutable confirmed completion-policy authority for one exact Task."""

    schema_version: Literal["p24-b-completion-policy-snapshot.v1"] = (
        TASK_COMPLETION_POLICY_SNAPSHOT_SCHEMA_VERSION
    )
    completion_policy_id: UUID
    completion_policy_version: int = Field(ge=1)
    completion_policy_fingerprint: str = Field(min_length=64, max_length=64)
    completion_policy_status: Literal["confirmed"] = "confirmed"
    created_at: datetime

    session_id: UUID
    project_id: UUID
    plan_version_id: UUID
    plan_version_no: int = Field(ge=1)
    task_creation_record_id: UUID
    task_id: UUID

    source_proposal_id: UUID
    source_proposal_fingerprint: str = Field(min_length=64, max_length=64)
    source_decision_id: UUID
    source_decision_fingerprint: str = Field(min_length=64, max_length=64)
    supersedes_completion_policy_id: UUID | None = None

    review_requirement: ConfirmedTaskCompletionRequirement
    verification_requirement: ConfirmedTaskCompletionRequirement
    delivery_requirement: ConfirmedTaskCompletionRequirement
    approval_requirement: ConfirmedTaskCompletionRequirement

    review_policy_source: str = Field(min_length=1, max_length=100)
    verification_policy_source: str = Field(min_length=1, max_length=100)
    delivery_policy_source: str = Field(min_length=1, max_length=100)
    approval_policy_source: str = Field(min_length=1, max_length=100)

    review_policy_evidence_ids: list[UUID]
    verification_policy_evidence_ids: list[UUID]
    delivery_policy_evidence_ids: list[UUID]
    approval_policy_evidence_ids: list[UUID]

    required_terminal_task_status: Literal["completed"] = "completed"
    required_terminal_run_status: Literal["succeeded"] = "succeeded"
    required_quality_gate_result: Literal[True] = True

    required_review_terminal_results: list[str] = Field(default_factory=list)
    required_verification_evidence_kinds: list[str] = Field(default_factory=list)
    required_delivery_evidence_kinds: list[str] = Field(default_factory=list)
    required_approval_terminal_results: list[str] = Field(default_factory=list)

    human_confirmation_required: Literal[True] = True
    human_confirmation_evidence_id: UUID
    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: list[str]

    @model_validator(mode="after")
    def validate_confirmed_snapshot(self) -> "ProjectDirectorTaskCompletionPolicySnapshot":
        evidence_groups = (
            self.review_policy_evidence_ids,
            self.verification_policy_evidence_ids,
            self.delivery_policy_evidence_ids,
            self.approval_policy_evidence_ids,
        )
        if any(not values or len(values) != len(set(values)) for values in evidence_groups):
            raise ValueError("confirmed policy axes require unique decision evidence")
        if self.human_confirmation_evidence_id != self.source_decision_id:
            raise ValueError("human confirmation evidence must be the source decision")
        required_axes = (
            (self.review_requirement, self.required_review_terminal_results),
            (self.verification_requirement, self.required_verification_evidence_kinds),
            (self.delivery_requirement, self.required_delivery_evidence_kinds),
            (self.approval_requirement, self.required_approval_terminal_results),
        )
        for requirement, acceptable_results in required_axes:
            if requirement == "required" and not acceptable_results:
                raise ValueError("required snapshot axes need acceptable terminal evidence")
        if self.product_runtime_git_write_allowed:
            raise ValueError("product runtime Git writes are forbidden")
        return self


class ProjectDirectorTaskCompletionPolicyResult(DomainModel):
    """Fail-closed result shared by proposal, decision, and revalidation entries."""

    model_config = ConfigDict(frozen=True)

    status: TaskCompletionPolicyResultStatus
    proposal: ProjectDirectorTaskCompletionPolicyProposal | None = None
    decision: ProjectDirectorTaskCompletionPolicyDecision | None = None
    snapshot: ProjectDirectorTaskCompletionPolicySnapshot | None = None
    blocked_reasons: list[TaskCompletionPolicyBlockedReason] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result_shape(self) -> "ProjectDirectorTaskCompletionPolicyResult":
        if self.status == "blocked":
            if not self.blocked_reasons or any(
                value is not None for value in (self.proposal, self.decision, self.snapshot)
            ):
                raise ValueError("blocked result requires only stable blocked reasons")
        elif self.blocked_reasons:
            raise ValueError("successful policy result cannot contain blocked reasons")
        elif self.status.startswith("proposal_") and self.proposal is None:
            raise ValueError("proposal result requires a proposal")
        elif self.status.startswith("decision_") and (
            self.proposal is None or self.decision is None or self.snapshot is None
        ):
            raise ValueError("decision result requires proposal, decision, and snapshot")
        elif self.status == "policy_revalidated" and (
            self.proposal is None or self.decision is None or self.snapshot is None
        ):
            raise ValueError("revalidation result requires the complete policy lineage")
        return self

    @classmethod
    def blocked(
        cls,
        *reasons: TaskCompletionPolicyBlockedReason,
    ) -> "ProjectDirectorTaskCompletionPolicyResult":
        return cls(status="blocked", blocked_reasons=list(dict.fromkeys(reasons)))


__all__ = (
    "ConfirmedTaskCompletionRequirement",
    "ProjectDirectorTaskCompletionPolicyDecision",
    "ProjectDirectorTaskCompletionPolicyProposal",
    "ProjectDirectorTaskCompletionPolicyResult",
    "ProjectDirectorTaskCompletionPolicySnapshot",
    "TASK_COMPLETION_POLICY_DECISION_SCHEMA_VERSION",
    "TASK_COMPLETION_POLICY_PROPOSAL_SCHEMA_VERSION",
    "TASK_COMPLETION_POLICY_SNAPSHOT_SCHEMA_VERSION",
    "TaskCompletionPolicyBlockedReason",
    "TaskCompletionPolicyResultStatus",
    "TaskCompletionPolicyStatus",
    "TaskCompletionRequirement",
)
