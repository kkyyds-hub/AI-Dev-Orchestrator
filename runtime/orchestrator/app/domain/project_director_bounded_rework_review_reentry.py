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
    require_sha256,
    validate_absolute_posix_path,
    validate_unique_paths,
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

P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION = "p21-c-h-review-output.v1"
BoundedReworkReviewerExecutor = Literal["codex", "claude-code"]


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


__all__ = (
    "BoundedReworkReviewerExecutor",
    "P25_BOUNDED_REWORK_REVIEW_CLAIM_NAMESPACE",
    "P25_BOUNDED_REWORK_REVIEW_CLAIM_REPLAY_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_REVIEW_CLAIM_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_NAMESPACE",
    "P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_REPLAY_SCHEMA_VERSION",
    "P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SCHEMA_VERSION",
    "ProjectDirectorBoundedReworkReviewInvocationClaim",
    "ProjectDirectorBoundedReworkReviewReentryPreflight",
)
