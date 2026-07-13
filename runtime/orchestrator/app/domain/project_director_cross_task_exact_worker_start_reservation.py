"""Immutable P24-E2A exact Worker-start reservation contracts."""

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


CROSS_TASK_EXACT_WORKER_START_RESERVATION_SCHEMA_VERSION = (
    "p24-e-exact-worker-start-reservation.v1"
)
CROSS_TASK_EXACT_WORKER_START_RESERVATION_REPLAY_SCHEMA_VERSION = (
    "p24-exact-worker-start-reservation-replay.v1"
)
CROSS_TASK_EXACT_WORKER_START_RESERVATION_ACTION = (
    "reserve_exact_worker_start"
)
CROSS_TASK_EXACT_WORKER_START_RESERVATION_INTENT = (
    "cross_task_exact_worker_start_reservation"
)
CROSS_TASK_EXACT_WORKER_START_RESERVATION_SOURCE_DETAIL = (
    "p24_cross_task_exact_worker_start_reserved"
)
CROSS_TASK_EXACT_WORKER_START_RESERVATION_ACTION_TYPE = (
    "p24_cross_task_exact_worker_start_reservation_record"
)

CrossTaskExactWorkerStartReservationStatus = Literal[
    "worker_start_reserved",
]
CrossTaskExactWorkerStartReservationResultStatus = Literal[
    "worker_start_reserved",
    "worker_start_replayed",
    "blocked",
]
CrossTaskExactWorkerStartReservationBlockedReason = Literal[
    "exact_worker_start_reservation_history_invalid",
    "exact_worker_start_reservation_history_conflict",
    "exact_worker_start_reservation_replay_conflict",
    "exact_worker_start_reservation_exact_run_reservation_invalid",
    "exact_worker_start_reservation_instruction_package_invalid",
    "exact_worker_start_reservation_task_missing",
    "exact_worker_start_reservation_task_identity_conflict",
    "exact_worker_start_reservation_task_state_conflict",
    "exact_worker_start_reservation_run_missing",
    "exact_worker_start_reservation_run_identity_conflict",
    "exact_worker_start_reservation_run_state_conflict",
    "exact_worker_start_reservation_run_routing_conflict",
    "exact_worker_start_reservation_agent_session_conflict",
    "exact_worker_start_reservation_worker_authority_conflict",
    "exact_worker_start_reservation_git_boundary_violation",
    "exact_worker_start_reservation_persistence_failed",
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
    "worker_invocation",
    "worker_invocation_without_reservation",
    "worker_invocation_without_claim",
    "agent_session_creation",
    "verification_command_execution",
    "uncontrolled_workspace_write",
)
_COMPLETED_ACTIONS = {
    "task_claim",
    "run_creation",
    "worker_start_reservation",
}


class ProjectDirectorCrossTaskExactWorkerStartReservation(DomainModel):
    """Authority reserved for a future Worker call, before invocation."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["p24-e-exact-worker-start-reservation.v1"] = (
        CROSS_TASK_EXACT_WORKER_START_RESERVATION_SCHEMA_VERSION
    )

    exact_worker_start_reservation_id: UUID
    worker_start_reservation_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    worker_start_reservation_replay_key: str = Field(
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

    continuation_sequence_no: Literal[3] = 3
    previous_record_id: UUID
    replay_of_record_id: None = None

    action: Literal["reserve_exact_worker_start"] = (
        CROSS_TASK_EXACT_WORKER_START_RESERVATION_ACTION
    )
    status: CrossTaskExactWorkerStartReservationStatus = (
        "worker_start_reserved"
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

    task_status: Literal["running"] = "running"
    task_human_status: Literal["none", "resolved"]
    task_paused_reason_absent: Literal[True] = True

    exact_run_id: UUID
    exact_run_status: Literal["running"] = "running"
    exact_run_started_at: datetime
    exact_run_created_at: datetime
    exact_run_finished_at: None = None
    exact_run_failure_category: None = None
    exact_run_quality_gate_passed: None = None

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

    worker_called: Literal[False] = False
    agent_session_created: Literal[False] = False
    invocation_claim_created: Literal[False] = False
    worker_outcome_recorded: Literal[False] = False
    runtime_started: Literal[False] = False

    task_status_mutated_by_worker_start: Literal[False] = False
    run_status_mutated_by_worker_start: Literal[False] = False
    product_runtime_git_write_allowed: Literal[False] = False

    active_agent_session_ids_before: tuple[UUID, ...]
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
                "exact Worker-start reservation timestamps must be UTC-aware"
            )
        return normalized

    @field_validator(
        "worker_start_reservation_fingerprint",
        "worker_start_reservation_replay_key",
        "continuation_root_fingerprint",
        "continuation_idempotency_key",
        "instruction_package_fingerprint",
        "instruction_candidate_fingerprint",
        "exact_run_reservation_fingerprint",
        "exact_run_reservation_replay_key",
        "source_completion_evidence_fingerprint",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError(
                "exact Worker-start reservation hashes must be lowercase SHA-256"
            )
        return value

    @model_validator(mode="after")
    def validate_reservation(
        self,
    ) -> "ProjectDirectorCrossTaskExactWorkerStartReservation":
        lineage_ids = {
            self.continuation_id,
            self.continuation_root_record_id,
            self.instruction_package_id,
            self.exact_run_reservation_id,
            self.exact_worker_start_reservation_id,
            self.task_creation_record_id,
        }
        if len(lineage_ids) != 6:
            raise ValueError(
                "exact Worker-start reservation lineage IDs must be distinct"
            )
        if self.exact_run_id in lineage_ids:
            raise ValueError("exact Run identity must differ from lineage records")
        if self.previous_record_id != self.exact_run_reservation_id:
            raise ValueError(
                "exact Worker-start reservation must follow the E1B reservation"
            )

        if self.source_task_id == self.next_task_id:
            raise ValueError("next Task must differ from the source Task")
        if self.next_task_index >= self.task_count:
            raise ValueError(
                "exact Worker-start reservation next Task index is outside the queue"
            )
        if self.active_agent_session_ids_before:
            raise ValueError(
                "exact Worker-start reservation requires no AgentSession"
            )

        if not self.worker_model_name.strip() or not self.worker_model_tier.strip():
            raise ValueError("exact Worker instruction Model authority is incomplete")

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
        ):
            raise ValueError(
                "exact Worker-start reservation forbidden actions are incomplete"
            )

        if (
            self.worker_start_reservation_replay_key
            != self.compute_worker_start_reservation_replay_key(
                continuation_id=self.continuation_id,
                exact_run_reservation_id=self.exact_run_reservation_id,
                instruction_package_id=self.instruction_package_id,
                next_task_id=self.next_task_id,
                exact_run_id=self.exact_run_id,
            )
        ):
            raise ValueError(
                "exact Worker-start reservation replay key does not match"
            )
        if (
            self.worker_start_reservation_fingerprint
            != self.compute_fingerprint()
        ):
            raise ValueError(
                "exact Worker-start reservation fingerprint does not match"
            )
        return self

    @staticmethod
    def compute_worker_start_reservation_replay_key(
        *,
        continuation_id: UUID,
        exact_run_reservation_id: UUID,
        instruction_package_id: UUID,
        next_task_id: UUID,
        exact_run_id: UUID,
    ) -> str:
        return compute_p24_contract_sha256(
            {
                "schema_version": (
                    CROSS_TASK_EXACT_WORKER_START_RESERVATION_REPLAY_SCHEMA_VERSION
                ),
                "action": CROSS_TASK_EXACT_WORKER_START_RESERVATION_ACTION,
                "continuation_id": continuation_id,
                "exact_run_reservation_id": exact_run_reservation_id,
                "instruction_package_id": instruction_package_id,
                "next_task_id": next_task_id,
                "exact_run_id": exact_run_id,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p24_contract_sha256(
            self.model_dump(
                mode="python",
                exclude={"worker_start_reservation_fingerprint"},
            )
        )


class ProjectDirectorCrossTaskExactWorkerStartReservationResult(DomainModel):
    """Strict result for the future Worker-start reservation service."""

    model_config = ConfigDict(frozen=True)

    status: CrossTaskExactWorkerStartReservationResultStatus
    reservation: ProjectDirectorCrossTaskExactWorkerStartReservation | None = None
    blocked_reasons: tuple[
        CrossTaskExactWorkerStartReservationBlockedReason,
        ...,
    ] = ()
    worker_start_reserved: bool = False
    worker_called: Literal[False] = False
    product_runtime_git_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> "ProjectDirectorCrossTaskExactWorkerStartReservationResult":
        if self.status in {"worker_start_reserved", "worker_start_replayed"}:
            if (
                self.reservation is None
                or self.blocked_reasons
                or not self.worker_start_reserved
                or self.reservation.status != "worker_start_reserved"
                or not self.reservation.worker_start_reserved
                or self.reservation.worker_called
            ):
                raise ValueError(
                    "successful exact Worker-start reservation result is inconsistent"
                )
        elif (
            self.reservation is not None
            or not self.blocked_reasons
            or len(self.blocked_reasons) != len(set(self.blocked_reasons))
            or self.worker_start_reserved
        ):
            raise ValueError(
                "blocked exact Worker-start reservation result is inconsistent"
            )
        return self


__all__ = (
    "CROSS_TASK_EXACT_WORKER_START_RESERVATION_ACTION",
    "CROSS_TASK_EXACT_WORKER_START_RESERVATION_ACTION_TYPE",
    "CROSS_TASK_EXACT_WORKER_START_RESERVATION_INTENT",
    "CROSS_TASK_EXACT_WORKER_START_RESERVATION_REPLAY_SCHEMA_VERSION",
    "CROSS_TASK_EXACT_WORKER_START_RESERVATION_SCHEMA_VERSION",
    "CROSS_TASK_EXACT_WORKER_START_RESERVATION_SOURCE_DETAIL",
    "CrossTaskExactWorkerStartReservationBlockedReason",
    "CrossTaskExactWorkerStartReservationResultStatus",
    "CrossTaskExactWorkerStartReservationStatus",
    "ProjectDirectorCrossTaskExactWorkerStartReservation",
    "ProjectDirectorCrossTaskExactWorkerStartReservationResult",
)
