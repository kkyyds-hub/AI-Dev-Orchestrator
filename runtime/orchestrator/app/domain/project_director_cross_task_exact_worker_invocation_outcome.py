"""Immutable P24-E4A exact Worker invocation outcome contracts."""

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
from app.domain.project_role import ProjectRoleCode


CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION = (
    "p24-e-exact-worker-invocation-outcome.v1"
)
CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_REPLAY_SCHEMA_VERSION = (
    "p24-exact-worker-invocation-outcome-replay.v1"
)
CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION = (
    "record_exact_worker_invocation_outcome"
)
CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_INTENT = (
    "cross_task_exact_worker_invocation_outcome"
)
CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL = (
    "p24_cross_task_exact_worker_invocation_outcome_recorded"
)
CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION_TYPE = (
    "p24_cross_task_exact_worker_invocation_outcome_record"
)

CrossTaskExactWorkerInvocationOutcomeStatus = Literal[
    "not_invoked",
    "returned",
    "raised",
]
CrossTaskExactWorkerInvocationOutcomeResultStatus = Literal[
    "outcome_recorded",
    "outcome_replayed",
    "recovery_required",
    "blocked",
]
CrossTaskExactWorkerInvocationOutcomeBlockedReason = Literal[
    "exact_worker_invocation_outcome_history_invalid",
    "exact_worker_invocation_outcome_history_conflict",
    "exact_worker_invocation_outcome_replay_conflict",
    "exact_worker_invocation_outcome_package_invalid",
    "exact_worker_invocation_outcome_exact_run_reservation_invalid",
    "exact_worker_invocation_outcome_worker_start_reservation_invalid",
    "exact_worker_invocation_outcome_claim_invalid",
    "exact_worker_invocation_outcome_task_identity_conflict",
    "exact_worker_invocation_outcome_run_identity_conflict",
    "exact_worker_invocation_outcome_worker_authority_conflict",
    "exact_worker_invocation_outcome_pre_call_revalidation_failed",
    "exact_worker_invocation_outcome_worker_result_invalid",
    "exact_worker_invocation_outcome_worker_result_binding_conflict",
    "exact_worker_invocation_outcome_worker_raised",
    "exact_worker_invocation_outcome_claim_without_outcome_recovery_required",
    "exact_worker_invocation_outcome_git_boundary_violation",
    "exact_worker_invocation_outcome_persistence_failed",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(?:api[ _-]?key|authorization|password|secret|token|prompt|"
    r"environment(?:[ _-]?variable)?|env|provider[ _-]?credential)"
    r"\s*[:=]"
)
_BEARER_VALUE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{8,}")

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
    "duplicate_worker_invocation_outcome",
    "worker_invocation_without_reservation",
    "worker_invocation_without_claim",
    "worker_reinvocation",
    "agent_session_creation_without_claim",
    "worker_outcome_without_claim",
    "worker_outcome_overwrite",
    "verification_command_execution",
    "uncontrolled_workspace_write",
)
_COMPLETED_ACTIONS = (
    "task_claim",
    "run_creation",
    "worker_start_reservation",
    "worker_invocation_claim",
    "worker_outcome_recording",
)


class ProjectDirectorCrossTaskExactWorkerInvocationOutcome(DomainModel):
    """One durable result for one consumed exact invocation claim."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["p24-e-exact-worker-invocation-outcome.v1"] = (
        CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION
    )

    exact_worker_invocation_outcome_id: UUID
    worker_invocation_outcome_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    worker_invocation_outcome_replay_key: str = Field(
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

    exact_worker_invocation_claim_id: UUID
    exact_worker_invocation_claim_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )
    exact_worker_invocation_claim_replay_key: str = Field(
        min_length=64,
        max_length=64,
    )
    exact_worker_invocation_claim_token: str = Field(
        min_length=64,
        max_length=64,
    )

    continuation_sequence_no: Literal[5] = 5
    previous_record_id: UUID
    replay_of_record_id: None = None

    action: Literal["record_exact_worker_invocation_outcome"] = (
        CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION
    )
    status: CrossTaskExactWorkerInvocationOutcomeStatus

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
    exact_run_id: UUID

    worker_invocation_claimed: Literal[True] = True
    single_use_worker_call_authorized: Literal[True] = True
    claim_created_for_this_call: Literal[True] = True
    claim_replayed_for_this_call: Literal[False] = False

    worker_called: bool
    worker_call_attempted: bool
    worker_returned: bool
    worker_raised: bool
    worker_started: bool

    worker_result_contract_valid: bool
    worker_result_claimed: bool | None = None
    worker_result_message: str | None = Field(default=None, max_length=2_000)
    worker_execution_mode: str | None = Field(default=None, max_length=200)
    worker_failure_category: str | None = Field(default=None, max_length=200)
    worker_quality_gate_passed: bool | None = None
    worker_result_summary: str | None = Field(default=None, max_length=2_000)

    claim_worker_model_name: str
    claim_worker_model_tier: str
    claim_worker_selected_skill_codes: tuple[str, ...]
    claim_worker_selected_skill_names: tuple[str, ...]
    claim_worker_owner_role_code: ProjectRoleCode
    claim_worker_upstream_role_code: ProjectRoleCode | None
    claim_worker_downstream_role_code: ProjectRoleCode | None

    worker_result_model_name: str | None = None
    worker_result_model_tier: str | None = None
    worker_result_selected_skill_codes: tuple[str, ...] = ()
    worker_result_selected_skill_names: tuple[str, ...] = ()
    worker_result_owner_role_code: ProjectRoleCode | None = None
    worker_result_upstream_role_code: ProjectRoleCode | None = None
    worker_result_downstream_role_code: ProjectRoleCode | None = None
    worker_result_route_reason: str | None = None
    worker_result_strategy_code: str | None = None
    worker_result_dispatch_status: str | None = None
    worker_authority_result_validated: bool

    reserved_snapshot_present: bool
    reserved_snapshot_source: str | None = None
    reserved_snapshot_exact_task_id: UUID | None = None
    reserved_snapshot_exact_run_id: UUID | None = None
    reserved_snapshot_exact_binding_validated: bool = False
    reserved_snapshot_task_routed: bool = False
    reserved_snapshot_task_claimed_in_this_cycle: bool = False
    reserved_snapshot_run_created_in_this_cycle: bool = False
    reserved_snapshot_budget_rechecked: bool = False
    reserved_snapshot_existing_run_reused: bool = False
    reserved_snapshot_shared_execution_seam_used: bool = False
    reserved_snapshot_blocked_reasons: tuple[str, ...] = ()

    task_status_after: str | None = None
    task_human_status_after: str | None = None
    task_paused_reason_after: str | None = None

    run_status_after: str | None = None
    run_finished_at_after: datetime | None = None
    run_failure_category_after: str | None = None
    run_quality_gate_passed_after: bool | None = None

    agent_session_id: UUID | None = None
    agent_session_status: str | None = None
    agent_session_phase: str | None = None

    runtime_handle_id: str | None = Field(default=None, max_length=2_000)
    native_process_started: bool

    exception_type: str | None = Field(default=None, max_length=200)
    exception_summary: str | None = Field(default=None, max_length=2_000)

    human_recovery_required: bool
    worker_call_state_indeterminate: Literal[False] = False
    blocked_reasons: tuple[
        CrossTaskExactWorkerInvocationOutcomeBlockedReason,
        ...,
    ] = ()

    worker_reported_git_write_activity: bool
    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: tuple[str, ...] = _REQUIRED_FORBIDDEN_ACTIONS

    @field_validator("created_at", "run_finished_at_after", mode="after")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        normalized = ensure_utc_datetime(value)
        if normalized is None or normalized.tzinfo is None:
            raise ValueError(
                "exact Worker invocation outcome timestamps must be UTC-aware"
            )
        return normalized

    @field_validator(
        "worker_invocation_outcome_fingerprint",
        "worker_invocation_outcome_replay_key",
        "continuation_root_fingerprint",
        "continuation_idempotency_key",
        "instruction_package_fingerprint",
        "instruction_candidate_fingerprint",
        "exact_run_reservation_fingerprint",
        "exact_run_reservation_replay_key",
        "exact_worker_start_reservation_fingerprint",
        "exact_worker_start_reservation_replay_key",
        "exact_worker_invocation_claim_fingerprint",
        "exact_worker_invocation_claim_replay_key",
        "exact_worker_invocation_claim_token",
        "source_completion_evidence_fingerprint",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError(
                "exact Worker invocation outcome hashes must be lowercase SHA-256"
            )
        return value

    @field_validator(
        "worker_result_message",
        "worker_result_summary",
        "exception_type",
        "exception_summary",
        "runtime_handle_id",
    )
    @classmethod
    def reject_sensitive_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip() or value != value.strip():
            raise ValueError("exact Worker invocation outcome text must be trimmed")
        if _SENSITIVE_ASSIGNMENT.search(value) or _BEARER_VALUE.search(value):
            raise ValueError(
                "exact Worker invocation outcome text contains sensitive material"
            )
        return value

    @field_validator(
        "worker_execution_mode",
        "worker_failure_category",
        "claim_worker_model_name",
        "claim_worker_model_tier",
        "worker_result_model_name",
        "worker_result_model_tier",
        "worker_result_route_reason",
        "worker_result_strategy_code",
        "worker_result_dispatch_status",
        "reserved_snapshot_source",
        "task_status_after",
        "task_human_status_after",
        "task_paused_reason_after",
        "run_status_after",
        "run_failure_category_after",
        "agent_session_status",
        "agent_session_phase",
        "exception_type",
    )
    @classmethod
    def require_trimmed_optional_text(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("exact Worker invocation outcome strings must be trimmed")
        return value

    @model_validator(mode="after")
    def validate_outcome(
        self,
    ) -> "ProjectDirectorCrossTaskExactWorkerInvocationOutcome":
        self._validate_identity_and_lineage()
        self._validate_claim_authority()
        self._validate_result_authority_shape()
        self._validate_reserved_snapshot_shape()
        self._validate_after_state()
        self._validate_forbidden_actions()
        self._validate_branch()
        self._validate_replay_and_fingerprint()
        return self

    def _validate_identity_and_lineage(self) -> None:
        lineage_ids = {
            self.continuation_id,
            self.continuation_root_record_id,
            self.instruction_package_id,
            self.exact_run_reservation_id,
            self.exact_worker_start_reservation_id,
            self.exact_worker_invocation_claim_id,
            self.exact_worker_invocation_outcome_id,
            self.task_creation_record_id,
            self.source_completion_evidence_id,
        }
        if len(lineage_ids) != 9:
            raise ValueError(
                "exact Worker invocation outcome lineage IDs must be distinct"
            )
        if self.exact_run_id in lineage_ids:
            raise ValueError("exact Run identity must differ from lineage records")
        if self.previous_record_id != self.exact_worker_invocation_claim_id:
            raise ValueError("exact Worker invocation outcome must follow its E3 claim")
        if self.source_task_id == self.next_task_id:
            raise ValueError("next Task must differ from the source Task")
        if self.source_run_id == self.exact_run_id:
            raise ValueError("exact Run must differ from the source Run")
        if self.next_task_index >= self.task_count:
            raise ValueError("exact Worker invocation outcome Task index is invalid")

    def _validate_claim_authority(self) -> None:
        if (
            not self.claim_worker_model_name.strip()
            or not self.claim_worker_model_tier.strip()
            or not self.claim_worker_selected_skill_codes
            or len(self.claim_worker_selected_skill_codes)
            != len(self.claim_worker_selected_skill_names)
            or len(self.claim_worker_selected_skill_codes)
            != len(set(self.claim_worker_selected_skill_codes))
            or len(self.claim_worker_selected_skill_names)
            != len(set(self.claim_worker_selected_skill_names))
            or any(
                not item.strip() or item != item.strip()
                for item in (
                    self.claim_worker_selected_skill_codes
                    + self.claim_worker_selected_skill_names
                )
            )
        ):
            raise ValueError("exact Worker invocation claim authority is incomplete")

    def _validate_result_authority_shape(self) -> None:
        result_strings = (
            self.worker_result_selected_skill_codes
            + self.worker_result_selected_skill_names
        )
        if any(not item.strip() or item != item.strip() for item in result_strings):
            raise ValueError("Worker result Skill authority must be trimmed")
        if (
            self.worker_authority_result_validated
            and not self._authority_matches_claim()
        ):
            raise ValueError("validated Worker authority must match the E3 claim")

    def _authority_matches_claim(self) -> bool:
        return (
            self.worker_result_model_name == self.claim_worker_model_name
            and self.worker_result_model_tier == self.claim_worker_model_tier
            and self.worker_result_selected_skill_codes
            == self.claim_worker_selected_skill_codes
            and self.worker_result_selected_skill_names
            == self.claim_worker_selected_skill_names
            and len(self.worker_result_selected_skill_codes)
            == len(self.worker_result_selected_skill_names)
            and len(self.worker_result_selected_skill_codes)
            == len(set(self.worker_result_selected_skill_codes))
            and len(self.worker_result_selected_skill_names)
            == len(set(self.worker_result_selected_skill_names))
            and self.worker_result_owner_role_code
            == self.claim_worker_owner_role_code
            and self.worker_result_upstream_role_code
            == self.claim_worker_upstream_role_code
            and self.worker_result_downstream_role_code
            == self.claim_worker_downstream_role_code
        )

    def _validate_reserved_snapshot_shape(self) -> None:
        if self.reserved_snapshot_present:
            if (
                self.reserved_snapshot_source is None
                or self.reserved_snapshot_exact_task_id is None
                or self.reserved_snapshot_exact_run_id is None
            ):
                raise ValueError("present reserved snapshot requires exact identities")
        elif (
            self.reserved_snapshot_source is not None
            or self.reserved_snapshot_exact_task_id is not None
            or self.reserved_snapshot_exact_run_id is not None
            or self.reserved_snapshot_exact_binding_validated
            or self.reserved_snapshot_task_routed
            or self.reserved_snapshot_task_claimed_in_this_cycle
            or self.reserved_snapshot_run_created_in_this_cycle
            or self.reserved_snapshot_budget_rechecked
            or self.reserved_snapshot_existing_run_reused
            or self.reserved_snapshot_shared_execution_seam_used
            or self.reserved_snapshot_blocked_reasons
        ):
            raise ValueError("absent reserved snapshot cannot carry snapshot facts")
        if (
            len(self.reserved_snapshot_blocked_reasons)
            != len(set(self.reserved_snapshot_blocked_reasons))
            or any(
                not reason.strip() or reason != reason.strip()
                for reason in self.reserved_snapshot_blocked_reasons
            )
        ):
            raise ValueError("reserved snapshot blocked reasons are invalid")

    def _validate_after_state(self) -> None:
        if (self.agent_session_id is None) != (self.agent_session_status is None):
            raise ValueError("AgentSession identity and status must appear together")
        if self.agent_session_id is None and self.agent_session_phase is not None:
            raise ValueError("AgentSession phase requires an AgentSession identity")

    def _validate_forbidden_actions(self) -> None:
        if (
            self.forbidden_actions != _REQUIRED_FORBIDDEN_ACTIONS
            or len(self.forbidden_actions) != len(set(self.forbidden_actions))
            or any(
                not action.strip() or action != action.strip()
                for action in self.forbidden_actions
            )
            or any(
                action in self.forbidden_actions
                for action in _COMPLETED_ACTIONS
            )
            or "worker_invocation" in self.forbidden_actions
            or len(self.blocked_reasons) != len(set(self.blocked_reasons))
        ):
            raise ValueError("exact Worker invocation outcome actions are invalid")

    def _validate_branch(self) -> None:
        if (
            self.worker_called != self.worker_call_attempted
            or self.worker_started != self.worker_call_attempted
        ):
            raise ValueError("Worker call attempt facts are inconsistent")
        if self.worker_reported_git_write_activity and (
            self.worker_result_contract_valid
            or not self.human_recovery_required
            or "exact_worker_invocation_outcome_git_boundary_violation"
            not in self.blocked_reasons
        ):
            raise ValueError("reported Git activity must force recovery")

        if self.status == "not_invoked":
            self._validate_not_invoked()
        elif self.status == "returned":
            self._validate_returned()
        else:
            self._validate_raised()

    def _validate_not_invoked(self) -> None:
        if (
            self.worker_call_attempted
            or self.worker_returned
            or self.worker_raised
            or self.worker_result_contract_valid
            or self.worker_result_claimed is not None
            or self.worker_authority_result_validated
            or self.reserved_snapshot_present
            or self.exception_type is not None
            or self.exception_summary is not None
            or self.native_process_started
            or self.worker_reported_git_write_activity
            or not self.human_recovery_required
            or not self.blocked_reasons
            or "exact_worker_invocation_outcome_pre_call_revalidation_failed"
            not in self.blocked_reasons
            or self._has_worker_result_payload()
        ):
            raise ValueError("not_invoked outcome has contradictory Worker evidence")

    def _validate_returned(self) -> None:
        if (
            not self.worker_call_attempted
            or not self.worker_returned
            or self.worker_raised
            or self.exception_type is not None
            or self.exception_summary is not None
        ):
            raise ValueError("returned outcome has contradictory call evidence")

        if self.worker_result_contract_valid:
            if (
                self.worker_result_claimed is not True
                or not self.worker_authority_result_validated
                or not self._authority_matches_claim()
                or not self.worker_result_message
                or not self.reserved_snapshot_present
                or self.reserved_snapshot_exact_task_id != self.next_task_id
                or self.reserved_snapshot_exact_run_id != self.exact_run_id
                or not self.reserved_snapshot_exact_binding_validated
                or self.reserved_snapshot_task_routed
                or self.reserved_snapshot_task_claimed_in_this_cycle
                or self.reserved_snapshot_run_created_in_this_cycle
                or not self.reserved_snapshot_existing_run_reused
                or not self.reserved_snapshot_shared_execution_seam_used
                or self.reserved_snapshot_blocked_reasons
                or self.human_recovery_required
                or self.blocked_reasons
                or self.worker_reported_git_write_activity
            ):
                raise ValueError(
                    "valid returned outcome requires exact Worker evidence"
                )
        elif not self.human_recovery_required or not self.blocked_reasons:
            raise ValueError("invalid returned outcome must require recovery")

    def _validate_raised(self) -> None:
        if (
            not self.worker_call_attempted
            or self.worker_returned
            or not self.worker_raised
            or self.worker_result_contract_valid
            or self.worker_result_claimed is not None
            or self.worker_authority_result_validated
            or self.reserved_snapshot_present
            or not self.exception_type
            or not self.exception_summary
            or not self.human_recovery_required
            or not self.blocked_reasons
            or "exact_worker_invocation_outcome_worker_raised"
            not in self.blocked_reasons
            or self._has_worker_result_payload()
        ):
            raise ValueError("raised outcome requires safe exception evidence")

    def _has_worker_result_payload(self) -> bool:
        return any(
            value is not None
            for value in (
                self.worker_result_message,
                self.worker_execution_mode,
                self.worker_failure_category,
                self.worker_quality_gate_passed,
                self.worker_result_summary,
                self.worker_result_model_name,
                self.worker_result_model_tier,
                self.worker_result_owner_role_code,
                self.worker_result_upstream_role_code,
                self.worker_result_downstream_role_code,
                self.worker_result_route_reason,
                self.worker_result_strategy_code,
                self.worker_result_dispatch_status,
            )
        ) or bool(
            self.worker_result_selected_skill_codes
            or self.worker_result_selected_skill_names
        )

    def _validate_replay_and_fingerprint(self) -> None:
        if (
            self.worker_invocation_outcome_replay_key
            != self.compute_worker_invocation_outcome_replay_key(
                continuation_id=self.continuation_id,
                exact_worker_invocation_claim_id=(
                    self.exact_worker_invocation_claim_id
                ),
                exact_worker_invocation_claim_token=(
                    self.exact_worker_invocation_claim_token
                ),
                exact_worker_start_reservation_id=(
                    self.exact_worker_start_reservation_id
                ),
                next_task_id=self.next_task_id,
                exact_run_id=self.exact_run_id,
            )
        ):
            raise ValueError(
                "exact Worker invocation outcome replay key does not match"
            )
        if self.worker_invocation_outcome_fingerprint != self.compute_fingerprint():
            raise ValueError(
                "exact Worker invocation outcome fingerprint does not match"
            )

    @staticmethod
    def compute_worker_invocation_outcome_replay_key(
        *,
        continuation_id: UUID,
        exact_worker_invocation_claim_id: UUID,
        exact_worker_invocation_claim_token: str,
        exact_worker_start_reservation_id: UUID,
        next_task_id: UUID,
        exact_run_id: UUID,
    ) -> str:
        return compute_p24_contract_sha256(
            {
                "schema_version": (
                    CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_REPLAY_SCHEMA_VERSION
                ),
                "action": CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION,
                "continuation_id": continuation_id,
                "exact_worker_invocation_claim_id": (
                    exact_worker_invocation_claim_id
                ),
                "exact_worker_invocation_claim_token": (
                    exact_worker_invocation_claim_token
                ),
                "exact_worker_start_reservation_id": (
                    exact_worker_start_reservation_id
                ),
                "next_task_id": next_task_id,
                "exact_run_id": exact_run_id,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p24_contract_sha256(
            self.model_dump(
                mode="python",
                exclude={"worker_invocation_outcome_fingerprint"},
            )
        )


class ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult(DomainModel):
    """Strict result for the future atomic invocation outcome service."""

    model_config = ConfigDict(frozen=True)

    status: CrossTaskExactWorkerInvocationOutcomeResultStatus
    exact_worker_invocation_claim_id: UUID | None = None
    outcome: ProjectDirectorCrossTaskExactWorkerInvocationOutcome | None = None
    blocked_reasons: tuple[
        CrossTaskExactWorkerInvocationOutcomeBlockedReason,
        ...,
    ] = ()

    outcome_recorded: bool = False
    outcome_replayed: bool = False
    resumed_from_existing_outcome: bool = False
    recovery_required: bool = False

    automatic_worker_call_allowed: Literal[False] = False
    worker_call_attempted: bool | None = False
    worker_call_state_indeterminate: bool = False
    product_runtime_git_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> "ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult":
        if (
            len(self.blocked_reasons) != len(set(self.blocked_reasons))
            or (self.outcome is not None and (
                self.exact_worker_invocation_claim_id
                != self.outcome.exact_worker_invocation_claim_id
            ))
        ):
            raise ValueError(
                "exact Worker invocation outcome result identity is invalid"
            )

        if self.status == "outcome_recorded":
            valid = (
                self.exact_worker_invocation_claim_id is not None
                and self.outcome is not None
                and not self.blocked_reasons
                and self.outcome_recorded
                and not self.outcome_replayed
                and not self.resumed_from_existing_outcome
                and self.recovery_required
                == self.outcome.human_recovery_required
                and self.worker_call_attempted
                == self.outcome.worker_call_attempted
                and not self.worker_call_state_indeterminate
            )
        elif self.status == "outcome_replayed":
            valid = (
                self.exact_worker_invocation_claim_id is not None
                and self.outcome is not None
                and not self.blocked_reasons
                and not self.outcome_recorded
                and self.outcome_replayed
                and self.resumed_from_existing_outcome
                and self.recovery_required
                == self.outcome.human_recovery_required
                and self.worker_call_attempted
                == self.outcome.worker_call_attempted
                and not self.worker_call_state_indeterminate
            )
        elif self.status == "recovery_required":
            valid = (
                self.exact_worker_invocation_claim_id is not None
                and self.outcome is None
                and bool(self.blocked_reasons)
                and not self.outcome_recorded
                and not self.outcome_replayed
                and not self.resumed_from_existing_outcome
                and self.recovery_required
                and self.worker_call_attempted is None
                and self.worker_call_state_indeterminate
                and (
                    "exact_worker_invocation_outcome_"
                    "claim_without_outcome_recovery_required"
                    in self.blocked_reasons
                )
            )
        else:
            valid = (
                self.outcome is None
                and bool(self.blocked_reasons)
                and not self.outcome_recorded
                and not self.outcome_replayed
                and not self.resumed_from_existing_outcome
                and not self.recovery_required
                and self.worker_call_attempted is False
                and not self.worker_call_state_indeterminate
            )

        if not valid:
            raise ValueError("exact Worker invocation outcome result is inconsistent")
        return self


__all__ = (
    "CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION",
    "CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_ACTION_TYPE",
    "CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_INTENT",
    "CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_REPLAY_SCHEMA_VERSION",
    "CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SCHEMA_VERSION",
    "CROSS_TASK_EXACT_WORKER_INVOCATION_OUTCOME_SOURCE_DETAIL",
    "CrossTaskExactWorkerInvocationOutcomeBlockedReason",
    "CrossTaskExactWorkerInvocationOutcomeResultStatus",
    "CrossTaskExactWorkerInvocationOutcomeStatus",
    "ProjectDirectorCrossTaskExactWorkerInvocationOutcome",
    "ProjectDirectorCrossTaskExactWorkerInvocationOutcomeResult",
)
