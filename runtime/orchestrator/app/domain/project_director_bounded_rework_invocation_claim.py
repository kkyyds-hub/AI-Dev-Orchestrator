"""Immutable P25-B bounded rework external invocation Claim contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_bounded_rework_contract import (
    P25_BOUNDED_REWORK_ATTEMPT_LIMIT,
    ProjectDirectorBoundedReworkAuthorityEnvelope,
    ProjectDirectorBoundedReworkModelSelection,
    ProjectDirectorBoundedReworkRoleSelection,
    ProjectDirectorBoundedReworkSkillSelection,
    compute_p25_contract_sha256,
    normalize_utc_datetime,
    require_sha256,
    require_trimmed_text,
    validate_skill_selections,
)


BOUNDED_REWORK_INVOCATION_CLAIM_SCHEMA_VERSION = "p25-b-invocation-claim.v1"
BOUNDED_REWORK_INVOCATION_CLAIM_REPLAY_SCHEMA_VERSION = (
    "p25-b-invocation-claim-replay.v1"
)


class ProjectDirectorBoundedReworkInvocationClaim(DomainModel):
    """Single-use authority committed before one future executor call."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-b-invocation-claim.v1"] = (
        BOUNDED_REWORK_INVOCATION_CLAIM_SCHEMA_VERSION
    )
    claim_id: UUID
    claim_fingerprint: str = Field(min_length=64, max_length=64)
    claim_replay_key: str = Field(min_length=64, max_length=64)
    claim_token: str = Field(min_length=64, max_length=64)
    created_at: datetime
    claim_status: Literal["claimed"] = "claimed"

    reservation_id: UUID
    reservation_fingerprint: str = Field(min_length=64, max_length=64)
    reservation_token: str = Field(min_length=64, max_length=64)
    package_id: UUID
    package_fingerprint: str = Field(min_length=64, max_length=64)
    authority: ProjectDirectorBoundedReworkAuthorityEnvelope

    exact_task_id: UUID
    exact_run_id: UUID
    rework_attempt_index: int = Field(ge=0, lt=3)
    rework_attempt_limit: int

    executor_adapter_kind: str = Field(min_length=1, max_length=120)
    selected_model: ProjectDirectorBoundedReworkModelSelection
    selected_skills: tuple[ProjectDirectorBoundedReworkSkillSelection, ...]
    selected_role: ProjectDirectorBoundedReworkRoleSelection
    workspace_before_manifest_fingerprint: str = Field(min_length=64, max_length=64)
    workspace_before_content_fingerprint: str = Field(min_length=64, max_length=64)
    invocation_ordinal: Literal[0] = 0

    executor_call_attempted: Literal[False] = False
    executor_started: Literal[False] = False
    executor_returned: Literal[False] = False
    executor_raised: Literal[False] = False
    executor_success_evidence_present: Literal[False] = False
    sandbox_file_written_by_claim: Literal[False] = False
    product_runtime_git_write_allowed: Literal[False] = False
    main_project_write_allowed: Literal[False] = False
    git_add_allowed: Literal[False] = False
    git_commit_allowed: Literal[False] = False
    git_push_allowed: Literal[False] = False
    branch_operation_allowed: Literal[False] = False
    pull_request_allowed: Literal[False] = False
    merge_allowed: Literal[False] = False
    ci_trigger_allowed: Literal[False] = False

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value, label="bounded rework Claim created_at")

    @field_validator(
        "claim_fingerprint",
        "claim_replay_key",
        "claim_token",
        "reservation_fingerprint",
        "reservation_token",
        "package_fingerprint",
        "workspace_before_manifest_fingerprint",
        "workspace_before_content_fingerprint",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return require_sha256(value, label="bounded rework Claim hash")

    @field_validator("executor_adapter_kind")
    @classmethod
    def validate_adapter(cls, value: str) -> str:
        return require_trimmed_text(value, label="bounded rework executor adapter")

    @field_validator("selected_skills")
    @classmethod
    def validate_skills(
        cls,
        values: tuple[ProjectDirectorBoundedReworkSkillSelection, ...],
    ) -> tuple[ProjectDirectorBoundedReworkSkillSelection, ...]:
        return validate_skill_selections(values)

    @model_validator(mode="after")
    def validate_claim(self) -> "ProjectDirectorBoundedReworkInvocationClaim":
        if (
            self.exact_task_id != self.authority.source_task_id
            or self.exact_task_id != self.authority.target_task_id
            or self.exact_run_id != self.authority.source_run_id
        ):
            raise ValueError("Claim must bind the authority's exact Task and Run")
        if self.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT:
            raise ValueError("bounded rework attempt limit must equal three")
        identities = {
            self.claim_id,
            self.reservation_id,
            self.package_id,
            self.authority.source_p23_dispatch_consumption_id,
            self.exact_task_id,
            self.exact_run_id,
        }
        if len(identities) != 6:
            raise ValueError("bounded rework Claim identities must be distinct")
        if self.claim_replay_key != self.compute_claim_replay_key(
            reservation_id=self.reservation_id,
            reservation_token=self.reservation_token,
            package_id=self.package_id,
            exact_task_id=self.exact_task_id,
            exact_run_id=self.exact_run_id,
            invocation_ordinal=self.invocation_ordinal,
        ):
            raise ValueError("bounded rework Claim replay key does not match")
        if self.claim_fingerprint != self.compute_fingerprint():
            raise ValueError("bounded rework Claim fingerprint does not match")
        return self

    @staticmethod
    def compute_claim_replay_key(
        *,
        reservation_id: UUID,
        reservation_token: str,
        package_id: UUID,
        exact_task_id: UUID,
        exact_run_id: UUID,
        invocation_ordinal: int,
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "schema_version": BOUNDED_REWORK_INVOCATION_CLAIM_REPLAY_SCHEMA_VERSION,
                "reservation_id": reservation_id,
                "reservation_token": reservation_token,
                "package_id": package_id,
                "exact_task_id": exact_task_id,
                "exact_run_id": exact_run_id,
                "invocation_ordinal": invocation_ordinal,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p25_contract_sha256(
            self.model_dump(mode="python", exclude={"claim_fingerprint"})
        )


__all__ = (
    "BOUNDED_REWORK_INVOCATION_CLAIM_REPLAY_SCHEMA_VERSION",
    "BOUNDED_REWORK_INVOCATION_CLAIM_SCHEMA_VERSION",
    "ProjectDirectorBoundedReworkInvocationClaim",
)
