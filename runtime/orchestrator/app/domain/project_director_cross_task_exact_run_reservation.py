"""Immutable P24-E1A exact next-Task Run reservation contracts."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime
from app.domain.project_director_exact_next_task_routing_snapshot import (
    ProjectDirectorRoutingScoreItemSnapshot,
    ProjectDirectorStrategyDecisionSnapshot,
)
from app.domain.project_director_next_task_instruction_package import (
    compute_p24_contract_sha256,
)
from app.domain.project_role import ProjectRoleCode
from app.domain.task import TaskPriority, TaskRiskLevel


CROSS_TASK_EXACT_RUN_RESERVATION_SCHEMA_VERSION = (
    "p24-e-exact-run-reservation.v1"
)
CROSS_TASK_EXACT_RUN_RESERVATION_REPLAY_SCHEMA_VERSION = (
    "p24-exact-run-reservation-replay.v1"
)
CROSS_TASK_EXACT_RUN_RESERVATION_ACTION = "reserve_exact_next_task_run"

CROSS_TASK_EXACT_RUN_RESERVATION_INTENT = (
    "cross_task_exact_run_reservation"
)
CROSS_TASK_EXACT_RUN_RESERVATION_SOURCE_DETAIL = (
    "p24_cross_task_exact_run_reserved"
)
CROSS_TASK_EXACT_RUN_RESERVATION_ACTION_TYPE = (
    "p24_cross_task_exact_run_reservation_record"
)

CrossTaskExactRunReservationStatus = Literal["next_task_run_created"]
CrossTaskExactRunReservationResultStatus = Literal[
    "run_reserved",
    "run_replayed",
    "blocked",
]
CrossTaskExactRunReservationBlockedReason = Literal[
    "exact_run_reservation_history_invalid",
    "exact_run_reservation_history_conflict",
    "exact_run_reservation_replay_conflict",
    "exact_run_reservation_root_invalid",
    "exact_run_reservation_package_invalid",
    "exact_run_reservation_candidate_invalid",
    "exact_run_reservation_task_missing",
    "exact_run_reservation_task_identity_conflict",
    "exact_run_reservation_task_state_conflict",
    "exact_run_reservation_dependency_blocked",
    "exact_run_reservation_active_run_conflict",
    "exact_run_reservation_active_agent_session_conflict",
    "exact_run_reservation_routing_conflict",
    "exact_run_reservation_budget_blocked",
    "exact_run_reservation_human_confirmation_required",
    "exact_run_reservation_task_claim_conflict",
    "exact_run_reservation_run_creation_failed",
    "exact_run_reservation_git_boundary_violation",
    "exact_run_reservation_persistence_failed",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_FORBIDDEN_ACTIONS = {
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
    "worker_invocation",
    "worker_invocation_without_reservation",
    "verification_command_execution",
    "uncontrolled_workspace_write",
}
_COMPLETED_ACTIONS = {
    "task_claim",
    "run_creation",
}


class ProjectDirectorCrossTaskExactRunReservation(DomainModel):
    """Task-claim plus Run-creation fact, not a Worker-start reservation."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["p24-e-exact-run-reservation.v1"] = (
        CROSS_TASK_EXACT_RUN_RESERVATION_SCHEMA_VERSION
    )

    exact_run_reservation_id: UUID
    reservation_fingerprint: str = Field(min_length=64, max_length=64)
    reservation_replay_key: str = Field(min_length=64, max_length=64)
    created_at: datetime

    continuation_id: UUID
    continuation_root_record_id: UUID
    continuation_root_fingerprint: str = Field(min_length=64, max_length=64)
    continuation_idempotency_key: str = Field(min_length=64, max_length=64)

    instruction_package_id: UUID
    instruction_package_fingerprint: str = Field(min_length=64, max_length=64)
    instruction_candidate_fingerprint: str = Field(min_length=64, max_length=64)

    continuation_sequence_no: Literal[2] = 2
    previous_record_id: UUID
    replay_of_record_id: None = None

    action: Literal["reserve_exact_next_task_run"] = (
        CROSS_TASK_EXACT_RUN_RESERVATION_ACTION
    )
    status: CrossTaskExactRunReservationStatus = "next_task_run_created"

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
    task_title: str
    task_input_summary: str
    owner_role_code: ProjectRoleCode
    priority: TaskPriority
    risk_level: TaskRiskLevel
    depends_on_task_ids: tuple[UUID, ...]

    task_status_before: Literal["pending"] = "pending"
    task_status_after: Literal["running"] = "running"
    task_human_status: Literal["none", "resolved"]
    task_paused_reason_absent: Literal[True] = True

    new_task_created: Literal[False] = False
    task_claimed: Literal[True] = True
    run_created: Literal[True] = True
    worker_called: Literal[False] = False

    active_run_ids_before: tuple[UUID, ...]
    active_agent_session_ids_before: tuple[UUID, ...]

    exact_run_id: UUID
    exact_run_status: Literal["running"] = "running"
    exact_run_started_at: datetime
    exact_run_created_at: datetime
    exact_run_finished_at: None = None
    exact_run_failure_category: None = None
    exact_run_quality_gate_passed: None = None

    run_model_name: str
    run_route_reason: str
    run_routing_score: float
    run_routing_score_breakdown: tuple[
        ProjectDirectorRoutingScoreItemSnapshot,
        ...,
    ]
    run_strategy_decision: ProjectDirectorStrategyDecisionSnapshot

    run_owner_role_code: ProjectRoleCode
    run_upstream_role_code: ProjectRoleCode | None
    run_downstream_role_code: ProjectRoleCode | None
    run_handoff_reason: str
    run_dispatch_status: str

    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: tuple[str, ...]

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
            raise ValueError("exact Run reservation timestamps must be UTC-aware")
        return normalized

    @field_validator(
        "reservation_fingerprint",
        "reservation_replay_key",
        "continuation_root_fingerprint",
        "continuation_idempotency_key",
        "instruction_package_fingerprint",
        "instruction_candidate_fingerprint",
        "source_completion_evidence_fingerprint",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("exact Run reservation hashes must be lowercase SHA-256")
        return value

    @field_validator("run_routing_score")
    @classmethod
    def require_finite_routing_score(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("exact Run routing score must be finite")
        return value

    @model_validator(mode="after")
    def validate_reservation(
        self,
    ) -> "ProjectDirectorCrossTaskExactRunReservation":
        lineage_ids = {
            self.continuation_id,
            self.continuation_root_record_id,
            self.instruction_package_id,
        }
        if len(lineage_ids) != 3:
            raise ValueError("exact Run reservation lineage IDs must be distinct")
        if self.exact_run_reservation_id in lineage_ids:
            raise ValueError("exact Run reservation identity must be distinct")
        if self.exact_run_id in lineage_ids | {self.exact_run_reservation_id}:
            raise ValueError("exact Run identity must be distinct")
        if self.previous_record_id != self.continuation_root_record_id:
            raise ValueError("exact Run reservation must follow its continuation root")

        if self.source_task_id == self.next_task_id:
            raise ValueError("next Task must differ from the source Task")
        if self.next_task_index >= self.task_count:
            raise ValueError("exact Run reservation next Task index is outside the queue")
        if not self.task_title.strip() or not self.task_input_summary.strip():
            raise ValueError("exact Run reservation next Task identity is incomplete")

        if self.active_run_ids_before or self.active_agent_session_ids_before:
            raise ValueError("exact Run reservation requires empty concurrency snapshots")

        if (
            not self.run_model_name.strip()
            or not self.run_route_reason.strip()
            or not self.run_handoff_reason.strip()
            or not self.run_dispatch_status.strip()
        ):
            raise ValueError("exact Run routing identity is incomplete")

        decision = self.run_strategy_decision
        if (
            decision.model_name != self.run_model_name
            or decision.owner_role_code != self.run_owner_role_code
            or self.run_owner_role_code != self.owner_role_code
            or not decision.model_tier
            or not decision.model_tier.strip()
            or not decision.selected_skill_codes
            or len(decision.selected_skill_codes)
            != len(decision.selected_skill_names)
            or not decision.strategy_code.strip()
        ):
            raise ValueError("exact Run routing facts conflict with strategy decision")

        if (
            not self.forbidden_actions
            or len(self.forbidden_actions) != len(set(self.forbidden_actions))
            or any(
                not action.strip() or action != action.strip()
                for action in self.forbidden_actions
            )
            or not _REQUIRED_FORBIDDEN_ACTIONS.issubset(self.forbidden_actions)
            or not _COMPLETED_ACTIONS.isdisjoint(self.forbidden_actions)
        ):
            raise ValueError("exact Run reservation forbidden actions are incomplete")

        if self.reservation_replay_key != self.compute_reservation_replay_key(
            continuation_id=self.continuation_id,
            continuation_root_record_id=self.continuation_root_record_id,
            instruction_package_id=self.instruction_package_id,
            next_task_id=self.next_task_id,
        ):
            raise ValueError("exact Run reservation replay key does not match")
        if self.reservation_fingerprint != self.compute_fingerprint():
            raise ValueError("exact Run reservation fingerprint does not match")
        return self

    @staticmethod
    def compute_reservation_replay_key(
        *,
        continuation_id: UUID,
        continuation_root_record_id: UUID,
        instruction_package_id: UUID,
        next_task_id: UUID,
    ) -> str:
        return compute_p24_contract_sha256(
            {
                "schema_version": (
                    CROSS_TASK_EXACT_RUN_RESERVATION_REPLAY_SCHEMA_VERSION
                ),
                "action": CROSS_TASK_EXACT_RUN_RESERVATION_ACTION,
                "continuation_id": continuation_id,
                "continuation_root_record_id": continuation_root_record_id,
                "instruction_package_id": instruction_package_id,
                "next_task_id": next_task_id,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p24_contract_sha256(
            self.model_dump(mode="python", exclude={"reservation_fingerprint"})
        )


class ProjectDirectorCrossTaskExactRunReservationResult(DomainModel):
    """Strict result for the future atomic exact-Run reservation service."""

    model_config = ConfigDict(frozen=True)

    status: CrossTaskExactRunReservationResultStatus
    reservation: ProjectDirectorCrossTaskExactRunReservation | None = None
    blocked_reasons: tuple[CrossTaskExactRunReservationBlockedReason, ...] = ()
    product_runtime_git_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> "ProjectDirectorCrossTaskExactRunReservationResult":
        if self.status in {"run_reserved", "run_replayed"}:
            if (
                self.reservation is None
                or self.blocked_reasons
                or self.reservation.status != "next_task_run_created"
                or self.reservation.task_status_after != "running"
                or self.reservation.exact_run_status != "running"
            ):
                raise ValueError("successful exact Run reservation result is inconsistent")
        elif (
            self.reservation is not None
            or not self.blocked_reasons
            or len(self.blocked_reasons) != len(set(self.blocked_reasons))
        ):
            raise ValueError("blocked exact Run reservation result is inconsistent")
        return self


__all__ = (
    "CROSS_TASK_EXACT_RUN_RESERVATION_ACTION",
    "CROSS_TASK_EXACT_RUN_RESERVATION_ACTION_TYPE",
    "CROSS_TASK_EXACT_RUN_RESERVATION_INTENT",
    "CROSS_TASK_EXACT_RUN_RESERVATION_REPLAY_SCHEMA_VERSION",
    "CROSS_TASK_EXACT_RUN_RESERVATION_SCHEMA_VERSION",
    "CROSS_TASK_EXACT_RUN_RESERVATION_SOURCE_DETAIL",
    "CrossTaskExactRunReservationBlockedReason",
    "CrossTaskExactRunReservationResultStatus",
    "CrossTaskExactRunReservationStatus",
    "ProjectDirectorCrossTaskExactRunReservation",
    "ProjectDirectorCrossTaskExactRunReservationResult",
)
