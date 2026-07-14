"""Immutable P25-B exact bounded rework attempt reservation contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_bounded_rework_contract import (
    P25_BOUNDED_REWORK_ATTEMPT_LIMIT,
    ProjectDirectorBoundedReworkAuthorityEnvelope,
    compute_p25_contract_sha256,
    normalize_utc_datetime,
    require_git_commit,
    require_sha256,
)


BOUNDED_REWORK_ATTEMPT_RESERVATION_SCHEMA_VERSION = (
    "p25-b-attempt-reservation.v1"
)
BOUNDED_REWORK_ATTEMPT_RESERVATION_REPLAY_SCHEMA_VERSION = (
    "p25-b-attempt-reservation-replay.v1"
)


class ProjectDirectorBoundedReworkAttemptReservation(DomainModel):
    """Pure exact-attempt reservation evidence; it performs no side effect."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-b-attempt-reservation.v1"] = (
        BOUNDED_REWORK_ATTEMPT_RESERVATION_SCHEMA_VERSION
    )
    reservation_id: UUID
    reservation_fingerprint: str = Field(min_length=64, max_length=64)
    reservation_replay_key: str = Field(min_length=64, max_length=64)
    reservation_token: str = Field(min_length=64, max_length=64)
    created_at: datetime
    reservation_status: Literal["reserved"] = "reserved"
    replay_state: Literal["new", "replayed"] = "new"

    package_id: UUID
    package_fingerprint: str = Field(min_length=64, max_length=64)
    package_replay_key: str = Field(min_length=64, max_length=64)
    authority: ProjectDirectorBoundedReworkAuthorityEnvelope

    exact_task_id: UUID
    exact_run_id: UUID
    rework_attempt_index: int = Field(ge=0, lt=3)
    rework_attempt_limit: int
    workspace_binding_fingerprint: str = Field(min_length=64, max_length=64)
    base_commit_sha: str = Field(min_length=40, max_length=40)
    source_candidate_diff_sha256: str = Field(min_length=64, max_length=64)

    external_call_performed: Literal[False] = False
    sandbox_file_written: Literal[False] = False
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
        return normalize_utc_datetime(value, label="bounded rework reservation created_at")

    @field_validator(
        "reservation_fingerprint",
        "reservation_replay_key",
        "reservation_token",
        "package_fingerprint",
        "package_replay_key",
        "workspace_binding_fingerprint",
        "source_candidate_diff_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return require_sha256(value, label="bounded rework reservation hash")

    @field_validator("base_commit_sha")
    @classmethod
    def validate_base_commit(cls, value: str) -> str:
        return require_git_commit(value, label="bounded rework reservation base commit")

    @model_validator(mode="after")
    def validate_reservation(
        self,
    ) -> "ProjectDirectorBoundedReworkAttemptReservation":
        if (
            self.exact_task_id != self.authority.source_task_id
            or self.exact_task_id != self.authority.target_task_id
            or self.exact_run_id != self.authority.source_run_id
        ):
            raise ValueError("reservation must bind the authority's exact Task and Run")
        if self.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT:
            raise ValueError("bounded rework attempt limit must equal three")
        identities = {
            self.reservation_id,
            self.package_id,
            self.authority.source_p23_dispatch_consumption_id,
            self.exact_task_id,
            self.exact_run_id,
        }
        if len(identities) != 5:
            raise ValueError("bounded rework reservation identities must be distinct")
        if self.reservation_replay_key != self.compute_reservation_replay_key(
            package_id=self.package_id,
            package_fingerprint=self.package_fingerprint,
            authority=self.authority,
            exact_task_id=self.exact_task_id,
            exact_run_id=self.exact_run_id,
            rework_attempt_index=self.rework_attempt_index,
        ):
            raise ValueError("bounded rework reservation replay key does not match")
        if self.reservation_fingerprint != self.compute_fingerprint():
            raise ValueError("bounded rework reservation fingerprint does not match")
        return self

    @staticmethod
    def compute_reservation_replay_key(
        *,
        package_id: UUID,
        package_fingerprint: str,
        authority: ProjectDirectorBoundedReworkAuthorityEnvelope,
        exact_task_id: UUID,
        exact_run_id: UUID,
        rework_attempt_index: int,
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "schema_version": (
                    BOUNDED_REWORK_ATTEMPT_RESERVATION_REPLAY_SCHEMA_VERSION
                ),
                "package_id": package_id,
                "package_fingerprint": package_fingerprint,
                "source_p23_dispatch_consumption_id": (
                    authority.source_p23_dispatch_consumption_id
                ),
                "source_p23_dispatch_consumption_fingerprint": (
                    authority.source_p23_dispatch_consumption_fingerprint
                ),
                "exact_task_id": exact_task_id,
                "exact_run_id": exact_run_id,
                "rework_attempt_index": rework_attempt_index,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p25_contract_sha256(
            self.model_dump(mode="python", exclude={"reservation_fingerprint"})
        )


__all__ = (
    "BOUNDED_REWORK_ATTEMPT_RESERVATION_REPLAY_SCHEMA_VERSION",
    "BOUNDED_REWORK_ATTEMPT_RESERVATION_SCHEMA_VERSION",
    "ProjectDirectorBoundedReworkAttemptReservation",
)
