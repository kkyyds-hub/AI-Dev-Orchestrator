"""Immutable P25-H bounded rework review re-entry contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid5

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_bounded_rework_contract import (
    P25_BOUNDED_REWORK_ATTEMPT_LIMIT,
    ProjectDirectorBoundedReworkAuthorityEnvelope,
    compute_p25_contract_sha256,
    normalize_utc_datetime,
    require_git_commit,
    require_optional_trimmed_text,
    require_sha256,
    require_trimmed_text,
    validate_absolute_posix_path,
    validate_unique_paths,
)
from app.domain.project_director_sandbox_candidate_diff_readonly_reviewer_adapter import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult,
)


P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SCHEMA_VERSION = (
    "p25-h-review-preflight.v1"
)
P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_REPLAY_SCHEMA_VERSION = (
    "p25-h-review-preflight-replay.v1"
)
P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_NAMESPACE = UUID(
    "b401caa2-22f2-4099-a5b5-e559e7a6e8fe"
)

P25_BOUNDED_REWORK_REVIEW_CLAIM_SCHEMA_VERSION = (
    "p25-h-review-invocation-claim.v1"
)
P25_BOUNDED_REWORK_REVIEW_CLAIM_REPLAY_SCHEMA_VERSION = (
    "p25-h-review-invocation-claim-replay.v1"
)
P25_BOUNDED_REWORK_REVIEW_CLAIM_NAMESPACE = UUID(
    "9b1d8568-e9d9-4214-993b-140f1ff6e906"
)
P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SCHEMA_VERSION = (
    "p25-h-review-invocation-attempt.v1"
)
P25_BOUNDED_REWORK_REVIEW_ATTEMPT_REPLAY_SCHEMA_VERSION = (
    "p25-h-review-invocation-attempt-replay.v1"
)
P25_BOUNDED_REWORK_REVIEW_ATTEMPT_NAMESPACE = UUID(
    "b5509ac8-d885-4de8-a27f-d678a7541e73"
)
P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION = (
    "p25-h-review-invocation-outcome.v1"
)
P25_BOUNDED_REWORK_REVIEW_OUTCOME_REPLAY_SCHEMA_VERSION = (
    "p25-h-review-invocation-outcome-replay.v1"
)
P25_BOUNDED_REWORK_REVIEW_OUTCOME_NAMESPACE = UUID(
    "a6efe61f-d3b9-4485-a8e2-6d5dca84c4b0"
)

P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION = "p21-c-h-review-output.v1"
BoundedReworkReviewerExecutor = Literal["codex", "claude-code"]
BoundedReworkReviewInvocationOutcomeStatus = Literal[
    "validated_output",
    "blocked",
    "raised",
]


class ProjectDirectorBoundedReworkReviewReentryPreflight(DomainModel):
    """Frozen P25-H review re-entry preflight with no reviewer side effects."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-h-review-preflight.v1"] = (
        P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SCHEMA_VERSION
    )
    preflight_id: UUID
    preflight_fingerprint: str = Field(min_length=64, max_length=64)
    preflight_replay_key: str = Field(min_length=64, max_length=64)
    created_at: datetime
    preflight_status: Literal["ready"] = "ready"

    source_candidate_diff_message_id: UUID
    source_candidate_diff_id: UUID
    source_candidate_diff_fingerprint: str = Field(min_length=64, max_length=64)
    source_candidate_diff_replay_key: str = Field(min_length=64, max_length=64)
    source_candidate_diff_sha256: str = Field(min_length=64, max_length=64)

    source_candidate_manifest_id: UUID
    source_candidate_manifest_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )

    source_outcome_id: UUID
    source_outcome_fingerprint: str = Field(min_length=64, max_length=64)
    source_claim_id: UUID
    source_reservation_id: UUID
    source_package_id: UUID

    source_attempt_id: UUID
    rework_attempt_index: int = Field(ge=0, lt=3)
    rework_attempt_limit: int

    old_review_message_id: UUID
    old_review_fingerprint: str = Field(min_length=64, max_length=64)
    old_review_semantic_fingerprint: str = Field(min_length=64, max_length=64)
    old_review_prompt_sha256: str = Field(min_length=64, max_length=64)
    old_review_source_diff_message_id: UUID
    old_review_source_diff_sha256: str = Field(min_length=64, max_length=64)

    authority: ProjectDirectorBoundedReworkAuthorityEnvelope
    exact_task_id: UUID
    exact_run_id: UUID

    base_commit_sha: str = Field(min_length=40, max_length=40)
    base_snapshot_fingerprint: str = Field(min_length=64, max_length=64)

    workspace_binding_id: UUID
    workspace_binding_fingerprint: str = Field(min_length=64, max_length=64)
    workspace_path: str = Field(min_length=1, max_length=2_000)
    workspace_business_manifest_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    workspace_business_content_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )

    requested_reviewer_executor: BoundedReworkReviewerExecutor
    review_input_schema_version: Literal["p25-h-review-preflight.v1"] = (
        P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SCHEMA_VERSION
    )
    review_output_schema_version: Literal["p21-c-h-review-output.v1"] = (
        P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION
    )
    review_scope_paths: tuple[str, ...]
    review_prompt_sha256: str = Field(min_length=64, max_length=64)
    review_prompt_bytes: int = Field(ge=1)

    reviewer_attempted: Literal[False] = False
    reviewer_started: Literal[False] = False
    reviewer_returned: Literal[False] = False
    reviewer_raised: Literal[False] = False
    review_output_persisted: Literal[False] = False

    provider_called: Literal[False] = False
    main_project_write_allowed: Literal[False] = False
    product_runtime_git_write_allowed: Literal[False] = False
    patch_apply_allowed: Literal[False] = False
    git_write_allowed: Literal[False] = False
    task_created: Literal[False] = False
    run_created: Literal[False] = False

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value, label="P25-H preflight created_at")

    @field_validator(
        "preflight_fingerprint",
        "preflight_replay_key",
        "source_candidate_diff_fingerprint",
        "source_candidate_diff_replay_key",
        "source_candidate_diff_sha256",
        "source_candidate_manifest_fingerprint",
        "source_outcome_fingerprint",
        "old_review_fingerprint",
        "old_review_semantic_fingerprint",
        "old_review_prompt_sha256",
        "old_review_source_diff_sha256",
        "base_snapshot_fingerprint",
        "workspace_binding_fingerprint",
        "workspace_business_manifest_fingerprint",
        "workspace_business_content_fingerprint",
        "review_prompt_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return require_sha256(value, label="P25-H review preflight hash")

    @field_validator("base_commit_sha")
    @classmethod
    def validate_base_commit(cls, value: str) -> str:
        return require_git_commit(value, label="P25-H review preflight base commit")

    @field_validator("workspace_path")
    @classmethod
    def validate_workspace_path(cls, value: str) -> str:
        return validate_absolute_posix_path(value)

    @field_validator("review_scope_paths")
    @classmethod
    def validate_scope_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        values = validate_unique_paths(values, allow_empty=False)
        if values != tuple(sorted(values)):
            raise ValueError("P25-H review scope paths must be sorted")
        return values

    @model_validator(mode="after")
    def validate_preflight(self) -> "ProjectDirectorBoundedReworkReviewReentryPreflight":
        if (
            self.exact_task_id != self.authority.source_task_id
            or self.exact_task_id != self.authority.target_task_id
            or self.exact_run_id != self.authority.source_run_id
        ):
            raise ValueError("P25-H preflight must bind the authority's exact Task and Run")
        if self.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT:
            raise ValueError("P25-H preflight attempt limit must equal three")
        if self.source_attempt_id != self.source_reservation_id:
            raise ValueError("P25-H source attempt must alias the reservation identity")
        if self.review_prompt_sha256 == self.old_review_prompt_sha256:
            raise ValueError("P25-H review prompt must be fresh")
        if (
            self.source_candidate_diff_message_id == self.old_review_source_diff_message_id
            or self.source_candidate_diff_sha256 == self.old_review_source_diff_sha256
        ):
            raise ValueError("P25-H source diff must be fresh")
        if self.preflight_replay_key != self.compute_preflight_replay_key(
            source_candidate_diff_replay_key=self.source_candidate_diff_replay_key
        ):
            raise ValueError("P25-H preflight replay key does not match")
        if self.preflight_id != uuid5(
            P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_NAMESPACE,
            self.source_candidate_diff_replay_key,
        ):
            raise ValueError("P25-H preflight identity is not deterministic")
        if self.preflight_fingerprint != self.compute_fingerprint():
            raise ValueError("P25-H preflight fingerprint does not match")
        return self

    @staticmethod
    def compute_preflight_replay_key(
        *,
        source_candidate_diff_replay_key: str,
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "schema_version": (
                    P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_REPLAY_SCHEMA_VERSION
                ),
                "source_candidate_diff_replay_key": source_candidate_diff_replay_key,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p25_contract_sha256(
            self.model_dump(mode="python", exclude={"preflight_fingerprint"})
        )


class ProjectDirectorBoundedReworkReviewInvocationClaim(DomainModel):
    """Single-use P25-H reviewer invocation Claim with no reviewer execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-h-review-invocation-claim.v1"] = (
        P25_BOUNDED_REWORK_REVIEW_CLAIM_SCHEMA_VERSION
    )
    review_claim_id: UUID
    review_claim_fingerprint: str = Field(min_length=64, max_length=64)
    review_claim_replay_key: str = Field(min_length=64, max_length=64)
    review_claim_token: str = Field(min_length=64, max_length=64)
    created_at: datetime
    claim_status: Literal["claimed"] = "claimed"

    preflight_id: UUID
    preflight_fingerprint: str = Field(min_length=64, max_length=64)
    preflight_replay_key: str = Field(min_length=64, max_length=64)

    source_candidate_diff_message_id: UUID
    source_candidate_diff_sha256: str = Field(min_length=64, max_length=64)
    source_outcome_id: UUID
    source_attempt_id: UUID
    source_package_id: UUID

    authority: ProjectDirectorBoundedReworkAuthorityEnvelope
    exact_task_id: UUID
    exact_run_id: UUID
    rework_attempt_index: int = Field(ge=0, lt=3)
    rework_attempt_limit: int

    requested_reviewer_executor: BoundedReworkReviewerExecutor
    review_prompt_sha256: str = Field(min_length=64, max_length=64)
    review_prompt_bytes: int = Field(ge=1)
    review_output_schema_version: Literal["p21-c-h-review-output.v1"] = (
        P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION
    )

    invocation_ordinal: Literal[0] = 0

    reviewer_call_attempted: Literal[False] = False
    reviewer_started: Literal[False] = False
    reviewer_returned: Literal[False] = False
    reviewer_raised: Literal[False] = False
    review_success_evidence_present: Literal[False] = False

    provider_called_by_claim: Literal[False] = False
    product_runtime_git_write_allowed: Literal[False] = False
    main_project_write_allowed: Literal[False] = False
    patch_apply_allowed: Literal[False] = False
    git_write_allowed: Literal[False] = False
    task_created: Literal[False] = False
    run_created: Literal[False] = False

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value, label="P25-H review Claim created_at")

    @field_validator(
        "review_claim_fingerprint",
        "review_claim_replay_key",
        "review_claim_token",
        "preflight_fingerprint",
        "preflight_replay_key",
        "source_candidate_diff_sha256",
        "review_prompt_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return require_sha256(value, label="P25-H review Claim hash")

    @model_validator(mode="after")
    def validate_claim(self) -> "ProjectDirectorBoundedReworkReviewInvocationClaim":
        if (
            self.exact_task_id != self.authority.source_task_id
            or self.exact_task_id != self.authority.target_task_id
            or self.exact_run_id != self.authority.source_run_id
        ):
            raise ValueError("P25-H review Claim must bind the authority's exact Task and Run")
        if self.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT:
            raise ValueError("P25-H review Claim attempt limit must equal three")
        if self.review_claim_replay_key != self.compute_claim_replay_key(
            preflight_replay_key=self.preflight_replay_key,
            invocation_ordinal=self.invocation_ordinal,
        ):
            raise ValueError("P25-H review Claim replay key does not match")
        if self.review_claim_id != uuid5(
            P25_BOUNDED_REWORK_REVIEW_CLAIM_NAMESPACE,
            self.preflight_replay_key,
        ):
            raise ValueError("P25-H review Claim identity is not deterministic")
        if self.review_claim_fingerprint != self.compute_fingerprint():
            raise ValueError("P25-H review Claim fingerprint does not match")
        return self

    @staticmethod
    def compute_claim_replay_key(
        *,
        preflight_replay_key: str,
        invocation_ordinal: int,
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "schema_version": P25_BOUNDED_REWORK_REVIEW_CLAIM_REPLAY_SCHEMA_VERSION,
                "preflight_replay_key": preflight_replay_key,
                "invocation_ordinal": invocation_ordinal,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p25_contract_sha256(
            self.model_dump(mode="python", exclude={"review_claim_fingerprint"})
        )


class ProjectDirectorBoundedReworkReviewInvocationAttempt(DomainModel):
    """Durable call reservation that preserves P25-H reviewer call-once semantics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-h-review-invocation-attempt.v1"] = (
        P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SCHEMA_VERSION
    )
    review_attempt_id: UUID
    review_attempt_fingerprint: str = Field(min_length=64, max_length=64)
    review_attempt_replay_key: str = Field(min_length=64, max_length=64)
    created_at: datetime
    attempt_status: Literal["call_reserved"] = "call_reserved"

    review_claim_id: UUID
    review_claim_fingerprint: str = Field(min_length=64, max_length=64)
    review_claim_replay_key: str = Field(min_length=64, max_length=64)
    review_claim_token_fingerprint: str = Field(min_length=64, max_length=64)

    preflight_id: UUID
    preflight_fingerprint: str = Field(min_length=64, max_length=64)

    source_candidate_diff_message_id: UUID
    source_candidate_diff_id: UUID
    source_candidate_diff_fingerprint: str = Field(min_length=64, max_length=64)
    source_candidate_diff_sha256: str = Field(min_length=64, max_length=64)

    source_outcome_id: UUID
    source_attempt_id: UUID
    source_package_id: UUID

    authority: ProjectDirectorBoundedReworkAuthorityEnvelope
    exact_task_id: UUID
    exact_run_id: UUID
    rework_attempt_index: int = Field(ge=0, lt=3)
    rework_attempt_limit: int

    requested_reviewer_executor: BoundedReworkReviewerExecutor
    review_prompt_sha256: str = Field(min_length=64, max_length=64)
    review_prompt_bytes: int = Field(ge=1)
    review_output_schema_version: Literal["p21-c-h-review-output.v1"] = (
        P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION
    )
    invocation_ordinal: Literal[0] = 0

    reviewer_call_reserved: Literal[True] = True
    reviewer_call_attempted: Literal[False] = False
    reviewer_started: Literal[False] = False
    reviewer_returned: Literal[False] = False
    reviewer_raised: Literal[False] = False
    review_output_persisted: Literal[False] = False

    provider_called: Literal[False] = False
    main_project_write_allowed: Literal[False] = False
    product_runtime_git_write_allowed: Literal[False] = False
    patch_apply_allowed: Literal[False] = False
    git_write_allowed: Literal[False] = False
    task_created: Literal[False] = False
    run_created: Literal[False] = False

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value, label="P25-H review attempt created_at")

    @field_validator(
        "review_attempt_fingerprint",
        "review_attempt_replay_key",
        "review_claim_fingerprint",
        "review_claim_replay_key",
        "review_claim_token_fingerprint",
        "preflight_fingerprint",
        "source_candidate_diff_fingerprint",
        "source_candidate_diff_sha256",
        "review_prompt_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return require_sha256(value, label="P25-H review attempt hash")

    @model_validator(mode="after")
    def validate_attempt(self) -> "ProjectDirectorBoundedReworkReviewInvocationAttempt":
        if (
            self.exact_task_id != self.authority.source_task_id
            or self.exact_task_id != self.authority.target_task_id
            or self.exact_run_id != self.authority.source_run_id
        ):
            raise ValueError("P25-H review attempt must bind the authority's exact Task and Run")
        if self.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT:
            raise ValueError("P25-H review attempt limit must equal three")
        if self.source_candidate_diff_message_id != self.source_candidate_diff_id:
            raise ValueError("P25-H review attempt must bind one exact candidate diff message")
        if self.review_attempt_replay_key != self.compute_attempt_replay_key(
            review_claim_replay_key=self.review_claim_replay_key,
            invocation_ordinal=self.invocation_ordinal,
        ):
            raise ValueError("P25-H review attempt replay key does not match")
        if self.review_attempt_id != uuid5(
            P25_BOUNDED_REWORK_REVIEW_ATTEMPT_NAMESPACE,
            self.review_attempt_replay_key,
        ):
            raise ValueError("P25-H review attempt identity is not deterministic")
        if self.review_attempt_fingerprint != self.compute_fingerprint():
            raise ValueError("P25-H review attempt fingerprint does not match")
        return self

    @staticmethod
    def compute_attempt_replay_key(
        *,
        review_claim_replay_key: str,
        invocation_ordinal: int,
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "schema_version": (
                    P25_BOUNDED_REWORK_REVIEW_ATTEMPT_REPLAY_SCHEMA_VERSION
                ),
                "review_claim_replay_key": review_claim_replay_key,
                "invocation_ordinal": invocation_ordinal,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p25_contract_sha256(
            self.model_dump(mode="python", exclude={"review_attempt_fingerprint"})
        )


class ProjectDirectorBoundedReworkReviewInvocationOutcome(DomainModel):
    """Durable P25-H readonly review outcome recorded after one reserved call."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-h-review-invocation-outcome.v1"] = (
        P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION
    )
    review_outcome_id: UUID
    review_outcome_fingerprint: str = Field(min_length=64, max_length=64)
    review_outcome_replay_key: str = Field(min_length=64, max_length=64)
    created_at: datetime
    outcome_status: BoundedReworkReviewInvocationOutcomeStatus

    review_attempt_id: UUID
    review_attempt_fingerprint: str = Field(min_length=64, max_length=64)
    review_attempt_replay_key: str = Field(min_length=64, max_length=64)
    review_claim_id: UUID
    review_claim_fingerprint: str = Field(min_length=64, max_length=64)
    preflight_id: UUID
    preflight_fingerprint: str = Field(min_length=64, max_length=64)

    source_candidate_diff_message_id: UUID
    source_candidate_diff_id: UUID
    source_candidate_diff_fingerprint: str = Field(min_length=64, max_length=64)
    source_candidate_diff_sha256: str = Field(min_length=64, max_length=64)

    source_candidate_manifest_id: UUID
    source_candidate_manifest_fingerprint: str = Field(min_length=64, max_length=64)
    source_executor_outcome_id: UUID
    source_package_id: UUID
    source_attempt_id: UUID

    authority: ProjectDirectorBoundedReworkAuthorityEnvelope
    exact_task_id: UUID
    exact_run_id: UUID
    rework_attempt_index: int = Field(ge=0, lt=3)
    rework_attempt_limit: int

    requested_reviewer_executor: BoundedReworkReviewerExecutor
    review_prompt_sha256: str = Field(min_length=64, max_length=64)
    review_prompt_bytes: int = Field(ge=1)
    review_scope_paths: tuple[str, ...]
    review_output_schema_version: Literal["p21-c-h-review-output.v1"] = (
        P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION
    )
    invocation_ordinal: Literal[0] = 0

    adapter_result: (
        ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult | None
    ) = None
    review_result_fingerprint: str = Field(min_length=64, max_length=64)
    review_semantic_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )

    safe_error_code: str | None = Field(default=None, max_length=120)
    blocked_reasons: tuple[str, ...] = ()
    recovery_required: bool = False
    human_escalation_required: bool = False

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value, label="P25-H review outcome created_at")

    @field_validator(
        "review_outcome_fingerprint",
        "review_outcome_replay_key",
        "review_attempt_fingerprint",
        "review_attempt_replay_key",
        "review_claim_fingerprint",
        "preflight_fingerprint",
        "source_candidate_diff_fingerprint",
        "source_candidate_diff_sha256",
        "source_candidate_manifest_fingerprint",
        "review_prompt_sha256",
        "review_result_fingerprint",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return require_sha256(value, label="P25-H review outcome hash")

    @field_validator("review_semantic_fingerprint")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        if value is not None:
            return require_sha256(value, label="P25-H review outcome semantic hash")
        return value

    @field_validator("safe_error_code")
    @classmethod
    def validate_optional_error_code(cls, value: str | None) -> str | None:
        return require_optional_trimmed_text(value, label="P25-H review outcome error")

    @field_validator("blocked_reasons")
    @classmethod
    def validate_blocked_reasons(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(require_trimmed_text(value, label="P25-H blocked reason") for value in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError("P25-H blocked reasons must be unique")
        return normalized

    @field_validator("review_scope_paths")
    @classmethod
    def validate_scope_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        values = validate_unique_paths(values, allow_empty=False)
        if values != tuple(sorted(values)):
            raise ValueError("P25-H review outcome scope paths must be sorted")
        return values

    @model_validator(mode="after")
    def validate_outcome(self) -> "ProjectDirectorBoundedReworkReviewInvocationOutcome":
        if (
            self.exact_task_id != self.authority.source_task_id
            or self.exact_task_id != self.authority.target_task_id
            or self.exact_run_id != self.authority.source_run_id
        ):
            raise ValueError("P25-H review outcome must bind the authority's exact Task and Run")
        if self.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT:
            raise ValueError("P25-H review outcome attempt limit must equal three")
        if self.source_candidate_diff_message_id != self.source_candidate_diff_id:
            raise ValueError("P25-H review outcome must bind one exact candidate diff message")
        if self.human_escalation_required and not self.recovery_required:
            raise ValueError("P25-H review outcome escalation requires recovery")
        if self.review_outcome_replay_key != self.compute_outcome_replay_key(
            review_attempt_replay_key=self.review_attempt_replay_key,
            source_candidate_diff_sha256=self.source_candidate_diff_sha256,
            review_prompt_sha256=self.review_prompt_sha256,
            invocation_ordinal=self.invocation_ordinal,
        ):
            raise ValueError("P25-H review outcome replay key does not match")
        if self.review_outcome_id != uuid5(
            P25_BOUNDED_REWORK_REVIEW_OUTCOME_NAMESPACE,
            self.review_attempt_replay_key,
        ):
            raise ValueError("P25-H review outcome identity is not deterministic")
        self._validate_status_specific_rules()
        if self.review_outcome_fingerprint != self.compute_fingerprint():
            raise ValueError("P25-H review outcome fingerprint does not match")
        return self

    def _validate_status_specific_rules(self) -> None:
        if self.outcome_status == "validated_output":
            if (
                self.adapter_result is None
                or self.adapter_result.adapter_status != "validated_output"
                or not self.adapter_result.review_prompt_verified
                or self.adapter_result.review_prompt_sha256 != self.review_prompt_sha256
                or self.adapter_result.review_prompt_bytes != self.review_prompt_bytes
                or tuple(self.adapter_result.review_scope_paths) != self.review_scope_paths
                or self.adapter_result.review_output_schema_version
                != self.review_output_schema_version
                or not self.adapter_result.transport_invoked
                or self.adapter_result.transport_status != "completed"
                or self.adapter_result.output_validation_status != "validated"
                or not self.adapter_result.strict_json_valid
                or not self.adapter_result.schema_valid
                or not self.adapter_result.semantics_valid
                or not self.adapter_result.evidence_scope_valid
                or self.adapter_result.review_status != "reviewed"
                or self.adapter_result.verdict is None
                or self.adapter_result.risk_level is None
                or self.adapter_result.provider_called
                or (
                    self.adapter_result.codex_started
                    and self.adapter_result.claude_code_started
                )
            ):
                raise ValueError("P25-H validated outcome gate is not satisfied")
            if (
                self.safe_error_code is not None
                or self.blocked_reasons
                or self.recovery_required
                or self.human_escalation_required
                or self.review_semantic_fingerprint is None
            ):
                raise ValueError("P25-H validated outcome must be terminal and semantic")
        elif self.outcome_status == "blocked":
            if (
                self.adapter_result is None
                or self.adapter_result.adapter_status != "blocked"
                or self.safe_error_code is not None
                or not self.blocked_reasons
                or self.recovery_required
                or self.human_escalation_required
                or self.review_semantic_fingerprint is not None
            ):
                raise ValueError("P25-H blocked outcome must persist blocked adapter facts")
        else:
            if (
                self.adapter_result is not None
                or self.safe_error_code is None
                or self.blocked_reasons
                or self.recovery_required
                or self.human_escalation_required
                or self.review_semantic_fingerprint is not None
            ):
                raise ValueError("P25-H raised outcome must persist only safe raised facts")

    @staticmethod
    def compute_outcome_replay_key(
        *,
        review_attempt_replay_key: str,
        source_candidate_diff_sha256: str,
        review_prompt_sha256: str,
        invocation_ordinal: int,
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "schema_version": (
                    P25_BOUNDED_REWORK_REVIEW_OUTCOME_REPLAY_SCHEMA_VERSION
                ),
                "review_attempt_replay_key": review_attempt_replay_key,
                "source_candidate_diff_sha256": source_candidate_diff_sha256,
                "review_prompt_sha256": review_prompt_sha256,
                "invocation_ordinal": invocation_ordinal,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p25_contract_sha256(
            self.model_dump(mode="python", exclude={"review_outcome_fingerprint"})
        )


__all__ = (
    "BoundedReworkReviewerExecutor",
    "P25_BOUNDED_REWORK_REVIEW_CLAIM_NAMESPACE",
    "P25_BOUNDED_REWORK_REVIEW_CLAIM_REPLAY_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_REVIEW_CLAIM_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_REVIEW_ATTEMPT_NAMESPACE",
    "P25_BOUNDED_REWORK_REVIEW_ATTEMPT_REPLAY_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_REVIEW_ATTEMPT_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_REVIEW_OUTCOME_NAMESPACE",
    "P25_BOUNDED_REWORK_REVIEW_OUTCOME_REPLAY_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_REVIEW_OUTCOME_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_NAMESPACE",
    "P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_REPLAY_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SCHEMA_VERSION",
    "ProjectDirectorBoundedReworkReviewInvocationAttempt",
    "ProjectDirectorBoundedReworkReviewInvocationClaim",
    "ProjectDirectorBoundedReworkReviewInvocationOutcome",
    "ProjectDirectorBoundedReworkReviewReentryPreflight",
)
