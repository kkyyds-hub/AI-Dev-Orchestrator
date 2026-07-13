"""Immutable P24-E3A exact Worker invocation claim contracts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime
from app.domain.project_director_next_task_instruction_package import (
    compute_p24_contract_sha256,
)
from app.domain.project_director_next_task_instruction_package_candidate import (
    ProjectDirectorCandidateRepositoryBindingSnapshot,
    ProjectDirectorCandidateSelectedSkill,
    ProjectDirectorCandidateWorkspaceBindingSnapshot,
)
from app.domain.project_role import ProjectRoleCode


CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SCHEMA_VERSION = (
    "p24-e-exact-worker-invocation-claim.v1"
)
CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_REPLAY_SCHEMA_VERSION = (
    "p24-exact-worker-invocation-claim-replay.v1"
)
CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_TOKEN_SCHEMA_VERSION = (
    "p24-exact-worker-invocation-claim-token.v1"
)
CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_ACTION = (
    "claim_exact_worker_invocation"
)
CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_INTENT = (
    "cross_task_exact_worker_invocation_claim"
)
CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL = (
    "p24_cross_task_exact_worker_invocation_claimed"
)
CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_ACTION_TYPE = (
    "p24_cross_task_exact_worker_invocation_claim_record"
)

CrossTaskExactWorkerInvocationClaimStatus = Literal[
    "worker_invocation_claimed",
]
CrossTaskExactWorkerInvocationClaimResultStatus = Literal[
    "invocation_claim_created",
    "invocation_claim_replayed",
    "blocked",
]
CrossTaskExactWorkerInvocationClaimBlockedReason = Literal[
    "exact_worker_invocation_claim_history_invalid",
    "exact_worker_invocation_claim_history_conflict",
    "exact_worker_invocation_claim_replay_conflict",
    "exact_worker_invocation_claim_package_invalid",
    "exact_worker_invocation_claim_exact_run_reservation_invalid",
    "exact_worker_invocation_claim_worker_start_reservation_invalid",
    "exact_worker_invocation_claim_task_missing",
    "exact_worker_invocation_claim_task_identity_conflict",
    "exact_worker_invocation_claim_task_state_conflict",
    "exact_worker_invocation_claim_run_missing",
    "exact_worker_invocation_claim_run_identity_conflict",
    "exact_worker_invocation_claim_run_state_conflict",
    "exact_worker_invocation_claim_run_routing_conflict",
    "exact_worker_invocation_claim_agent_session_conflict",
    "exact_worker_invocation_claim_worker_authority_conflict",
    "exact_worker_invocation_claim_git_boundary_violation",
    "exact_worker_invocation_claim_persistence_failed",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_FORBIDDEN_ACTIONS = (
    "product_runtime_git_write",
    "git_add",
    "git_commit",
    "git_push",
    "pull_request_creation",
    "merge",
    "branch_destruction",
    "global_pending_task_scan",
    "next_task_skip",
    "plan_mutation",
    "duplicate_task_creation",
    "duplicate_task_claim",
    "duplicate_run_creation",
    "duplicate_worker_start_reservation",
    "duplicate_worker_invocation_claim",
    "worker_invocation_without_reservation",
    "worker_invocation_without_claim",
    "worker_reinvocation",
    "agent_session_creation_without_claim",
    "worker_outcome_without_claim",
    "verification_command_execution",
    "uncontrolled_workspace_write",
)
_COMPLETED_ACTIONS = {
    "task_claim",
    "run_creation",
    "worker_start_reservation",
    "worker_invocation_claim",
}


class ProjectDirectorCrossTaskExactWorkerInvocationClaim(DomainModel):
    """Single-use authority committed before one future exact Worker call."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["p24-e-exact-worker-invocation-claim.v1"] = (
        CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SCHEMA_VERSION
    )

    exact_worker_invocation_claim_id: UUID
    worker_invocation_claim_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    worker_invocation_claim_replay_key: str = Field(
        min_length=64,
        max_length=64,
    )
    worker_invocation_claim_token: str = Field(
        min_length=64,
        max_length=64,
    )
    created_at: datetime

    continuation_id: UUID
    continuation_root_record_id: UUID
    continuation_root_fingerprint: str = Field(min_length=64, max_length=64)
    continuation_idempotency_key: str = Field(min_length=64, max_length=64)

    instruction_package_id: UUID
    instruction_package_fingerprint: str = Field(min_length=64, max_length=64)
    instruction_candidate_fingerprint: str = Field(min_length=64, max_length=64)

    exact_run_reservation_id: UUID
    exact_run_reservation_fingerprint: str = Field(min_length=64, max_length=64)
    exact_run_reservation_replay_key: str = Field(min_length=64, max_length=64)

    exact_worker_start_reservation_id: UUID
    exact_worker_start_reservation_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    exact_worker_start_reservation_replay_key: str = Field(
        min_length=64,
        max_length=64,
    )

    continuation_sequence_no: Literal[4] = 4
    previous_record_id: UUID
    replay_of_record_id: None = None

    action: Literal["claim_exact_worker_invocation"] = (
        CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_ACTION
    )
    status: CrossTaskExactWorkerInvocationClaimStatus = (
        "worker_invocation_claimed"
    )

    session_id: UUID
    project_id: UUID
    plan_version_id: UUID
    task_creation_record_id: UUID

    source_task_id: UUID
    source_run_id: UUID
    source_completion_evidence_id: UUID
    source_completion_evidence_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )

    next_task_id: UUID
    next_task_index: int = Field(ge=0)
    task_count: int = Field(ge=1)

    task_status_before: Literal["running"] = "running"
    task_human_status_before: Literal["none", "resolved"]
    task_paused_reason_absent: Literal[True] = True

    exact_run_id: UUID
    run_status_before: Literal["running"] = "running"
    exact_run_started_at: datetime
    exact_run_created_at: datetime
    exact_run_finished_at_before: None = None
    exact_run_failure_category_before: None = None
    exact_run_quality_gate_passed_before: None = None

    active_run_ids_before: tuple[UUID, ...]
    active_agent_session_ids_before: tuple[UUID, ...]

    worker_model_name: str
    worker_model_tier: str
    worker_owner_role_code: ProjectRoleCode
    worker_upstream_role_code: ProjectRoleCode | None
    worker_downstream_role_code: ProjectRoleCode | None

    worker_selected_skills: tuple[ProjectDirectorCandidateSelectedSkill, ...]
    worker_repository_binding: ProjectDirectorCandidateRepositoryBindingSnapshot
    worker_workspace_binding: ProjectDirectorCandidateWorkspaceBindingSnapshot
    worker_allowed_paths: tuple[str, ...]
    worker_forbidden_paths: tuple[str, ...]

    task_claimed: Literal[True] = True
    run_created: Literal[True] = True
    worker_start_reserved: Literal[True] = True
    worker_invocation_claimed: Literal[True] = True

    single_use_worker_call_authorized: Literal[True] = True
    worker_called: Literal[False] = False
    worker_call_attempted: Literal[False] = False

    agent_session_created: Literal[False] = False
    runtime_started: Literal[False] = False
    worker_outcome_recorded: Literal[False] = False

    task_status_mutated_by_claim: Literal[False] = False
    run_status_mutated_by_claim: Literal[False] = False
    product_runtime_git_write_allowed: Literal[False] = False

    forbidden_actions: tuple[str, ...] = _REQUIRED_FORBIDDEN_ACTIONS

    @field_validator(
        "created_at",
        "exact_run_started_at",
        "exact_run_created_at",
        mode="after",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None or normalized.tzinfo is None:
            raise ValueError(
                "exact Worker invocation claim timestamps must be UTC-aware"
            )
        return normalized

    @field_validator(
        "worker_invocation_claim_fingerprint",
        "worker_invocation_claim_replay_key",
        "worker_invocation_claim_token",
        "continuation_root_fingerprint",
        "continuation_idempotency_key",
        "instruction_package_fingerprint",
        "instruction_candidate_fingerprint",
        "exact_run_reservation_fingerprint",
        "exact_run_reservation_replay_key",
        "exact_worker_start_reservation_fingerprint",
        "exact_worker_start_reservation_replay_key",
        "source_completion_evidence_fingerprint",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError(
                "exact Worker invocation claim hashes must be lowercase SHA-256"
            )
        return value

    @model_validator(mode="after")
    def validate_claim(
        self,
    ) -> "ProjectDirectorCrossTaskExactWorkerInvocationClaim":
        lineage_ids = {
            self.continuation_id,
            self.continuation_root_record_id,
            self.instruction_package_id,
            self.exact_run_reservation_id,
            self.exact_worker_start_reservation_id,
            self.exact_worker_invocation_claim_id,
            self.task_creation_record_id,
            self.source_completion_evidence_id,
        }
        if len(lineage_ids) != 8:
            raise ValueError(
                "exact Worker invocation claim lineage IDs must be distinct"
            )
        if self.exact_run_id in lineage_ids:
            raise ValueError("exact Run identity must differ from lineage records")
        if self.previous_record_id != self.exact_worker_start_reservation_id:
            raise ValueError(
                "exact Worker invocation claim must follow the E2A reservation"
            )

        if self.source_task_id == self.next_task_id:
            raise ValueError("next Task must differ from the source Task")
        if self.source_run_id == self.exact_run_id:
            raise ValueError("exact Run must differ from the source Run")
        if self.next_task_index >= self.task_count:
            raise ValueError(
                "exact Worker invocation claim next Task index is outside the queue"
            )
        if self.active_run_ids_before != (self.exact_run_id,):
            raise ValueError(
                "exact Worker invocation claim requires only the exact active Run"
            )
        if self.active_agent_session_ids_before:
            raise ValueError(
                "exact Worker invocation claim requires no active AgentSession"
            )

        if not self.worker_model_name.strip() or not self.worker_model_tier.strip():
            raise ValueError("exact Worker invocation authority is incomplete")

        skill_codes = tuple(
            item.skill_code for item in self.worker_selected_skills
        )
        skill_names = tuple(
            item.skill_name for item in self.worker_selected_skills
        )
        if (
            not skill_codes
            or len(skill_codes) != len(set(skill_codes))
            or len(skill_names) != len(set(skill_names))
        ):
            raise ValueError("exact Worker selected Skills must be non-empty and unique")

        if (
            not self.worker_allowed_paths
            or len(self.worker_allowed_paths) != len(set(self.worker_allowed_paths))
            or len(self.worker_forbidden_paths)
            != len(set(self.worker_forbidden_paths))
            or any(
                not path.strip() or path != path.strip()
                for path in self.worker_allowed_paths + self.worker_forbidden_paths
            )
            or self.worker_repository_binding.focus_paths
            != self.worker_allowed_paths
        ):
            raise ValueError("exact Worker path authority is inconsistent")
        if self.worker_workspace_binding.project_id != self.project_id:
            raise ValueError("exact Worker workspace project identity conflicts")

        if (
            self.forbidden_actions != _REQUIRED_FORBIDDEN_ACTIONS
            or not _COMPLETED_ACTIONS.isdisjoint(self.forbidden_actions)
            or "worker_invocation" in self.forbidden_actions
        ):
            raise ValueError(
                "exact Worker invocation claim forbidden actions are inconsistent"
            )

        if (
            self.worker_invocation_claim_replay_key
            != self.compute_worker_invocation_claim_replay_key(
                continuation_id=self.continuation_id,
                exact_worker_start_reservation_id=(
                    self.exact_worker_start_reservation_id
                ),
                exact_run_reservation_id=self.exact_run_reservation_id,
                instruction_package_id=self.instruction_package_id,
                next_task_id=self.next_task_id,
                exact_run_id=self.exact_run_id,
            )
        ):
            raise ValueError(
                "exact Worker invocation claim replay key does not match"
            )
        if (
            self.worker_invocation_claim_token
            != self.compute_worker_invocation_claim_token(
                exact_worker_invocation_claim_id=(
                    self.exact_worker_invocation_claim_id
                ),
                worker_invocation_claim_replay_key=(
                    self.worker_invocation_claim_replay_key
                ),
                exact_worker_start_reservation_id=(
                    self.exact_worker_start_reservation_id
                ),
                exact_worker_start_reservation_fingerprint=(
                    self.exact_worker_start_reservation_fingerprint
                ),
                exact_run_id=self.exact_run_id,
            )
        ):
            raise ValueError(
                "exact Worker invocation claim token does not match"
            )
        if (
            self.worker_invocation_claim_fingerprint
            != self.compute_fingerprint()
        ):
            raise ValueError(
                "exact Worker invocation claim fingerprint does not match"
            )
        return self

    @staticmethod
    def compute_worker_invocation_claim_replay_key(
        *,
        continuation_id: UUID,
        exact_worker_start_reservation_id: UUID,
        exact_run_reservation_id: UUID,
        instruction_package_id: UUID,
        next_task_id: UUID,
        exact_run_id: UUID,
    ) -> str:
        return compute_p24_contract_sha256(
            {
                "schema_version": (
                    CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_REPLAY_SCHEMA_VERSION
                ),
                "action": CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_ACTION,
                "continuation_id": continuation_id,
                "exact_worker_start_reservation_id": (
                    exact_worker_start_reservation_id
                ),
                "exact_run_reservation_id": exact_run_reservation_id,
                "instruction_package_id": instruction_package_id,
                "next_task_id": next_task_id,
                "exact_run_id": exact_run_id,
            }
        )

    @staticmethod
    def compute_worker_invocation_claim_token(
        *,
        exact_worker_invocation_claim_id: UUID,
        worker_invocation_claim_replay_key: str,
        exact_worker_start_reservation_id: UUID,
        exact_worker_start_reservation_fingerprint: str,
        exact_run_id: UUID,
    ) -> str:
        return compute_p24_contract_sha256(
            {
                "schema_version": (
                    CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_TOKEN_SCHEMA_VERSION
                ),
                "action": CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_ACTION,
                "exact_worker_invocation_claim_id": (
                    exact_worker_invocation_claim_id
                ),
                "worker_invocation_claim_replay_key": (
                    worker_invocation_claim_replay_key
                ),
                "exact_worker_start_reservation_id": (
                    exact_worker_start_reservation_id
                ),
                "exact_worker_start_reservation_fingerprint": (
                    exact_worker_start_reservation_fingerprint
                ),
                "exact_run_id": exact_run_id,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p24_contract_sha256(
            self.model_dump(
                mode="python",
                exclude={"worker_invocation_claim_fingerprint"},
            )
        )


class ProjectDirectorCrossTaskExactWorkerInvocationClaimResult(DomainModel):
    """Strict result for the future atomic invocation-claim service."""

    model_config = ConfigDict(frozen=True)

    status: CrossTaskExactWorkerInvocationClaimResultStatus
    claim: ProjectDirectorCrossTaskExactWorkerInvocationClaim | None = None
    blocked_reasons: tuple[
        CrossTaskExactWorkerInvocationClaimBlockedReason,
        ...,
    ] = ()

    invocation_claim_created: bool = False
    invocation_claim_replayed: bool = False
    automatic_worker_call_allowed: bool = False
    worker_called: Literal[False] = False
    product_runtime_git_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> "ProjectDirectorCrossTaskExactWorkerInvocationClaimResult":
        if self.status == "invocation_claim_created":
            if (
                self.claim is None
                or self.blocked_reasons
                or not self.invocation_claim_created
                or self.invocation_claim_replayed
                or not self.automatic_worker_call_allowed
                or self.claim.status != "worker_invocation_claimed"
                or not self.claim.worker_invocation_claimed
                or not self.claim.single_use_worker_call_authorized
                or self.claim.worker_called
                or self.claim.worker_call_attempted
            ):
                raise ValueError(
                    "created exact Worker invocation claim result is inconsistent"
                )
        elif self.status == "invocation_claim_replayed":
            if (
                self.claim is None
                or self.blocked_reasons
                or self.invocation_claim_created
                or not self.invocation_claim_replayed
                or self.automatic_worker_call_allowed
                or self.claim.status != "worker_invocation_claimed"
                or not self.claim.worker_invocation_claimed
                or not self.claim.single_use_worker_call_authorized
                or self.claim.worker_called
                or self.claim.worker_call_attempted
            ):
                raise ValueError(
                    "replayed exact Worker invocation claim result is inconsistent"
                )
        elif (
            self.claim is not None
            or not self.blocked_reasons
            or len(self.blocked_reasons) != len(set(self.blocked_reasons))
            or self.invocation_claim_created
            or self.invocation_claim_replayed
            or self.automatic_worker_call_allowed
        ):
            raise ValueError(
                "blocked exact Worker invocation claim result is inconsistent"
            )
        return self


__all__ = (
    "CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_ACTION",
    "CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_ACTION_TYPE",
    "CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_INTENT",
    "CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_REPLAY_SCHEMA_VERSION",
    "CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SCHEMA_VERSION",
    "CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_SOURCE_DETAIL",
    "CROSS_TASK_EXACT_WORKER_INVOCATION_CLAIM_TOKEN_SCHEMA_VERSION",
    "CrossTaskExactWorkerInvocationClaimBlockedReason",
    "CrossTaskExactWorkerInvocationClaimResultStatus",
    "CrossTaskExactWorkerInvocationClaimStatus",
    "ProjectDirectorCrossTaskExactWorkerInvocationClaim",
    "ProjectDirectorCrossTaskExactWorkerInvocationClaimResult",
)
