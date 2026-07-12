"""Project Director P23-D2-B1 Worker start reservation contract."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


ProtectedTransitionWorkerStartReservationStatus = Literal[
    "reserved",
    "blocked",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorProtectedTransitionWorkerStartReservationResult(DomainModel):
    """Unique eligibility reservation for a future exact Worker invocation."""

    reservation_status: ProtectedTransitionWorkerStartReservationStatus
    reservation_id: UUID | None = None
    reservation_fingerprint: str = Field(default="", max_length=64)
    reservation_token: str | None = Field(default=None, max_length=200)

    session_id: UUID
    project_id: UUID | None = None
    source_task_id: UUID
    target_task_id: UUID | None = None
    run_id: UUID | None = None

    source_consumption_message_id: UUID
    source_consumption_id: UUID | None = None
    source_consumption_fingerprint: str = Field(default="", max_length=64)

    source_preflight_message_id: UUID | None = None
    source_intent_message_id: UUID | None = None
    source_p22_summary_message_id: UUID | None = None
    source_review_message_id: UUID | None = None
    source_freshness_message_id: UUID | None = None

    disposition_type: Literal["AUTO_CONTINUE", "AUTO_REWORK"] | None = None
    dispatch_kind: Literal["auto_continue", "auto_rework"] | None = None
    target_task_strategy: Literal[
        "source_task_continue",
        "source_task_rework",
    ] | None = None

    review_result_fingerprint: str = Field(default="", max_length=64)
    review_semantic_fingerprint: str = Field(default="", max_length=64)

    d1_current_freshness_fingerprint: str = Field(default="", max_length=64)
    reservation_current_freshness_fingerprint: str = Field(
        default="",
        max_length=64,
    )
    source_diff_sha256: str = Field(default="", max_length=64)
    current_diff_sha256: str = Field(default="", max_length=64)
    review_scope_paths: list[str] = Field(default_factory=list)
    current_scope_paths: list[str] = Field(default_factory=list)
    workspace_path: str = Field(default="", max_length=2_000)
    workspace_path_within_root: bool = False

    task_status: str | None = None
    task_human_status: str | None = None
    run_status: str | None = None
    run_started_at: datetime | None = None
    run_routing_metadata_valid: bool = False

    agent_session_absent: bool = False

    budget_guard_allowed: bool = False
    budget_pressure_level: str | None = None
    budget_strategy_action: str | None = None
    budget_strategy_code: str | None = None
    budget_policy_source: str | None = None
    retry_limit_reached: bool = False

    rework_attempt_index: int = Field(default=0, ge=0)
    rework_attempt_limit: int = Field(default=3, ge=1)

    replay_check_completed: bool = False
    resumed_from_existing_reservation: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    blocked_reasons: list[str] = Field(default_factory=list)

    worker_start_reserved: bool = False
    worker_started: bool = False
    agent_session_created: bool = False
    runtime_started: bool = False
    continuation_started: bool = False
    rework_started: bool = False

    task_created: bool = False
    run_created: bool = False
    task_status_mutated: bool = False
    run_status_mutated: bool = False

    git_write_performed: bool = False
    gate_allows_write: bool = False
    product_runtime_git_write_allowed: bool = False
    ai_project_director_total_loop: Literal["Partial"] = "Partial"

    @field_validator("created_at", "run_started_at", mode="after")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        """Normalize persisted timestamps to aware UTC values."""

        return ensure_utc_datetime(value)

    @field_validator(
        "worker_started",
        "agent_session_created",
        "runtime_started",
        "continuation_started",
        "rework_started",
        "task_created",
        "run_created",
        "task_status_mutated",
        "run_status_mutated",
        "git_write_performed",
        "gate_allows_write",
        "product_runtime_git_write_allowed",
        mode="after",
    )
    @classmethod
    def reject_forbidden_side_effect_flags(cls, value: bool) -> bool:
        """B1 cannot report execution, persistence mutation, or Git authority."""

        if value:
            raise ValueError("Worker start reservation cannot report side effects")
        return value

    @model_validator(mode="after")
    def validate_reservation_state(
        self,
    ) -> "ProjectDirectorProtectedTransitionWorkerStartReservationResult":
        """Enforce strict reserved and blocked terminal combinations."""

        if self.reservation_status == "blocked":
            if self.reservation_id is not None or self.worker_start_reserved:
                raise ValueError("blocked reservation cannot create a reservation record")
            if not self.blocked_reasons:
                raise ValueError("blocked reservation must include reasons")
            return self

        required_values = (
            self.reservation_id,
            self.reservation_token,
            self.project_id,
            self.target_task_id,
            self.run_id,
            self.source_consumption_id,
            self.source_preflight_message_id,
            self.source_intent_message_id,
            self.source_p22_summary_message_id,
            self.source_review_message_id,
            self.source_freshness_message_id,
            self.disposition_type,
            self.dispatch_kind,
            self.target_task_strategy,
            self.task_status,
            self.task_human_status,
            self.run_status,
            self.run_started_at,
            self.budget_pressure_level,
            self.budget_strategy_action,
            self.budget_strategy_code,
            self.budget_policy_source,
        )
        if any(value is None for value in required_values):
            raise ValueError("reserved state requires complete evidence and runtime identity")
        fingerprints = (
            self.reservation_fingerprint,
            self.source_consumption_fingerprint,
            self.review_result_fingerprint,
            self.review_semantic_fingerprint,
            self.d1_current_freshness_fingerprint,
            self.reservation_current_freshness_fingerprint,
            self.source_diff_sha256,
            self.current_diff_sha256,
        )
        if not all(_LOWER_HEX_SHA256.match(value) for value in fingerprints):
            raise ValueError("reserved state requires valid SHA-256 fingerprints")
        if self.target_task_id != self.source_task_id:
            raise ValueError("reservation must target the exact source Task")
        if self.source_consumption_id != self.source_consumption_message_id:
            raise ValueError("reservation must bind the exact D1 consumption")
        expected_dispatch = {
            "AUTO_CONTINUE": ("auto_continue", "source_task_continue"),
            "AUTO_REWORK": ("auto_rework", "source_task_rework"),
        }[self.disposition_type]
        if (self.dispatch_kind, self.target_task_strategy) != expected_dispatch:
            raise ValueError("disposition and dispatch mapping do not match")
        if (
            self.task_status != "running"
            or self.task_human_status in ("requested", "in_progress")
            or self.run_status != "running"
            or not self.run_routing_metadata_valid
        ):
            raise ValueError("reservation requires an eligible running Task and Run")
        if (
            self.d1_current_freshness_fingerprint
            != self.reservation_current_freshness_fingerprint
            or self.source_diff_sha256 != self.current_diff_sha256
            or not self.review_scope_paths
            or self.review_scope_paths != self.current_scope_paths
            or not self.workspace_path
            or not self.workspace_path_within_root
        ):
            raise ValueError("reservation requires unchanged current evidence")
        if (
            self.rework_attempt_limit != 3
            or self.rework_attempt_index >= self.rework_attempt_limit
            or self.dispatch_kind == "auto_continue"
            and self.rework_attempt_index != 0
        ):
            raise ValueError("reservation violates the bounded rework contract")
        if (
            not self.agent_session_absent
            or not self.budget_guard_allowed
            or self.retry_limit_reached
            or not self.replay_check_completed
            or not self.worker_start_reserved
            or self.blocked_reasons
        ):
            raise ValueError("reserved state requires all eligibility checks to pass")
        return self


__all__ = (
    "ProjectDirectorProtectedTransitionWorkerStartReservationResult",
    "ProtectedTransitionWorkerStartReservationStatus",
)
