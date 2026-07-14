"""Immutable P25-B bounded rework invocation Outcome contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_bounded_rework_contract import (
    P25_BOUNDED_REWORK_ATTEMPT_LIMIT,
    ProjectDirectorBoundedReworkAuthorityEnvelope,
    compute_p25_contract_sha256,
    normalize_utc_datetime,
    require_optional_sha256,
    require_optional_trimmed_text,
    require_sha256,
    require_trimmed_text,
    validate_unique_paths,
)


BOUNDED_REWORK_INVOCATION_OUTCOME_SCHEMA_VERSION = "p25-b-invocation-outcome.v1"
BOUNDED_REWORK_INVOCATION_OUTCOME_REPLAY_SCHEMA_VERSION = (
    "p25-b-invocation-outcome-replay.v1"
)

BoundedReworkInvocationOutcomeStatus: TypeAlias = Literal[
    "returned",
    "raised",
    "invalid_result",
    "recovery_required",
    "human_escalation_required",
]
BoundedReworkScopeValidationStatus: TypeAlias = Literal[
    "valid",
    "invalid",
    "indeterminate",
]
BoundedReworkSideEffectState: TypeAlias = Literal[
    "none",
    "observed",
    "indeterminate",
]
BoundedReworkGitActivityKind: TypeAlias = Literal[
    "git_add",
    "git_commit",
    "git_push",
    "branch_create",
    "branch_delete",
    "checkout",
    "switch",
    "reset",
    "stash",
    "rebase",
    "tag",
    "pull_request",
    "merge",
    "ci_trigger",
    "repository_head_changed",
    "repository_status_changed",
    "git_control_metadata_changed",
]

_SENSITIVE_ERROR_MARKERS = (
    "authorization:",
    "api_key=",
    "apikey=",
    "token=",
    "secret=",
    "stdout:",
    "stderr:",
    "prompt:",
)


class ProjectDirectorBoundedReworkInvocationOutcome(DomainModel):
    """Durable result facts for one exact Claim; never execution authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-b-invocation-outcome.v1"] = (
        BOUNDED_REWORK_INVOCATION_OUTCOME_SCHEMA_VERSION
    )
    outcome_id: UUID
    outcome_fingerprint: str = Field(min_length=64, max_length=64)
    outcome_replay_key: str = Field(min_length=64, max_length=64)
    created_at: datetime
    outcome_status: BoundedReworkInvocationOutcomeStatus

    claim_id: UUID
    claim_fingerprint: str = Field(min_length=64, max_length=64)
    claim_token: str = Field(min_length=64, max_length=64)
    reservation_id: UUID
    reservation_fingerprint: str = Field(min_length=64, max_length=64)
    package_id: UUID
    package_fingerprint: str = Field(min_length=64, max_length=64)
    authority: ProjectDirectorBoundedReworkAuthorityEnvelope

    exact_task_id: UUID
    exact_run_id: UUID
    rework_attempt_index: int = Field(ge=0, lt=3)
    rework_attempt_limit: int
    invocation_ordinal: Literal[0] = 0

    executor_attempted: bool
    executor_started: bool
    executor_returned: bool
    executor_raised: bool
    executor_result_valid: bool
    safe_error_code: str | None = Field(default=None, max_length=120)
    redacted_error_summary: str | None = Field(default=None, max_length=1_000)

    workspace_before_manifest_fingerprint: str = Field(min_length=64, max_length=64)
    workspace_before_content_fingerprint: str = Field(min_length=64, max_length=64)
    workspace_after_manifest_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    workspace_after_content_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    declared_changed_paths: tuple[str, ...] = ()
    observed_changed_paths: tuple[str, ...] = ()
    scope_validation_status: BoundedReworkScopeValidationStatus
    git_activity_detected: bool
    git_activity_kinds: tuple[BoundedReworkGitActivityKind, ...] = ()
    side_effect_state: BoundedReworkSideEffectState

    candidate_manifest_id: UUID | None = None
    candidate_manifest_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    candidate_files_changed: bool
    recovery_required: bool
    human_escalation_required: bool

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
        return normalize_utc_datetime(value, label="bounded rework Outcome created_at")

    @field_validator(
        "outcome_fingerprint",
        "outcome_replay_key",
        "claim_fingerprint",
        "claim_token",
        "reservation_fingerprint",
        "package_fingerprint",
        "workspace_before_manifest_fingerprint",
        "workspace_before_content_fingerprint",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return require_sha256(value, label="bounded rework Outcome hash")

    @field_validator(
        "workspace_after_manifest_fingerprint",
        "workspace_after_content_fingerprint",
        "candidate_manifest_fingerprint",
    )
    @classmethod
    def validate_optional_hashes(cls, value: str | None) -> str | None:
        return require_optional_sha256(value, label="bounded rework Outcome hash")

    @field_validator("safe_error_code", "redacted_error_summary")
    @classmethod
    def validate_optional_error_text(cls, value: str | None) -> str | None:
        return require_optional_trimmed_text(value, label="bounded rework safe error")

    @field_validator("redacted_error_summary")
    @classmethod
    def reject_sensitive_error_text(cls, value: str | None) -> str | None:
        if value is not None and any(
            marker in value.lower() for marker in _SENSITIVE_ERROR_MARKERS
        ):
            raise ValueError("bounded rework error summary must be redacted")
        return value

    @field_validator("declared_changed_paths", "observed_changed_paths")
    @classmethod
    def validate_changed_paths(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return validate_unique_paths(values, allow_empty=True)

    @field_validator("git_activity_kinds")
    @classmethod
    def validate_git_activity_kinds(
        cls,
        values: tuple[BoundedReworkGitActivityKind, ...],
    ) -> tuple[BoundedReworkGitActivityKind, ...]:
        if len(values) != len(set(values)):
            raise ValueError("Git activity kinds must be unique")
        return values

    @model_validator(mode="after")
    def validate_outcome(self) -> "ProjectDirectorBoundedReworkInvocationOutcome":
        self._validate_identity_and_call_facts()
        self._validate_workspace_and_git_facts()
        self._validate_status()
        if self.outcome_replay_key != self.compute_outcome_replay_key(
            claim_id=self.claim_id,
            claim_token=self.claim_token,
            reservation_id=self.reservation_id,
            package_id=self.package_id,
            exact_task_id=self.exact_task_id,
            exact_run_id=self.exact_run_id,
        ):
            raise ValueError("bounded rework Outcome replay key does not match")
        if self.outcome_fingerprint != self.compute_fingerprint():
            raise ValueError("bounded rework Outcome fingerprint does not match")
        return self

    def _validate_identity_and_call_facts(self) -> None:
        if (
            self.exact_task_id != self.authority.source_task_id
            or self.exact_task_id != self.authority.target_task_id
            or self.exact_run_id != self.authority.source_run_id
        ):
            raise ValueError("Outcome must bind the authority's exact Task and Run")
        if self.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT:
            raise ValueError("bounded rework attempt limit must equal three")
        identities = {
            self.outcome_id,
            self.claim_id,
            self.reservation_id,
            self.package_id,
            self.authority.source_p23_dispatch_consumption_id,
            self.exact_task_id,
            self.exact_run_id,
        }
        if len(identities) != 7:
            raise ValueError("bounded rework Outcome identities must be distinct")
        if self.executor_returned and self.executor_raised:
            raise ValueError("executor returned and raised states are mutually exclusive")
        if self.executor_started and not self.executor_attempted:
            raise ValueError("executor start requires an attempted invocation")
        if (self.executor_returned or self.executor_raised) and not (
            self.executor_attempted and self.executor_started
        ):
            raise ValueError("executor terminal facts require attempted and started")
        if self.human_escalation_required and not self.recovery_required:
            raise ValueError("human escalation requires recovery state")

    def _validate_workspace_and_git_facts(self) -> None:
        after_pair = (
            self.workspace_after_manifest_fingerprint,
            self.workspace_after_content_fingerprint,
        )
        if (after_pair[0] is None) != (after_pair[1] is None):
            raise ValueError("workspace after fingerprints must appear together")
        terminal_execution_status = self.outcome_status in {
            "returned",
            "raised",
            "invalid_result",
        }
        if terminal_execution_status and any(value is None for value in after_pair):
            raise ValueError(
                "terminal executor Outcomes require complete workspace after state"
            )
        if (
            self.outcome_status
            in {"recovery_required", "human_escalation_required"}
            and self.executor_started
            and all(value is None for value in after_pair)
            and (
                self.side_effect_state != "indeterminate"
                or not self.recovery_required
                or self.executor_result_valid
            )
        ):
            raise ValueError(
                "started recovery without after state must remain indeterminate"
            )
        if self.git_activity_detected != bool(self.git_activity_kinds):
            raise ValueError("Git activity detection requires exact activity kinds")
        if self.git_activity_detected and (
            self.outcome_status != "human_escalation_required"
            or self.executor_result_valid
            or not self.recovery_required
            or not self.human_escalation_required
        ):
            raise ValueError("Git activity must block success and force escalation")
        if self.side_effect_state == "indeterminate" and (
            not self.recovery_required
            or self.executor_result_valid
            or self.outcome_status == "returned"
        ):
            raise ValueError(
                "indeterminate side effects require a non-success recovery state"
            )
        if self.candidate_files_changed:
            if (
                self.side_effect_state != "observed"
                or not self.declared_changed_paths
                or not self.observed_changed_paths
                or self.candidate_manifest_id is None
                or self.candidate_manifest_fingerprint is None
            ):
                raise ValueError("changed candidate files require manifest-bound paths")
        elif (
            self.declared_changed_paths
            or self.observed_changed_paths
            or self.candidate_manifest_id is not None
            or self.candidate_manifest_fingerprint is not None
        ):
            raise ValueError("unchanged candidate state cannot carry changed-file facts")
        if self.side_effect_state == "none" and (
            self.candidate_files_changed
            or self.declared_changed_paths
            or self.observed_changed_paths
            or self.candidate_manifest_id is not None
            or self.candidate_manifest_fingerprint is not None
        ):
            raise ValueError("no side effects cannot carry candidate change facts")

    def _validate_status(self) -> None:
        if self.outcome_status == "returned":
            if (
                not self.executor_attempted
                or not self.executor_started
                or not self.executor_returned
                or self.executor_raised
                or not self.executor_result_valid
                or self.safe_error_code is not None
                or self.redacted_error_summary is not None
                or self.scope_validation_status != "valid"
                or self.declared_changed_paths != self.observed_changed_paths
                or self.git_activity_detected
                or self.side_effect_state == "indeterminate"
                or self.recovery_required
                or self.human_escalation_required
            ):
                raise ValueError("successful returned Outcome has contradictory facts")
            return

        if self.executor_result_valid:
            raise ValueError("non-success Outcome cannot claim a valid executor result")
        if self.safe_error_code is None or self.redacted_error_summary is None:
            raise ValueError("non-success Outcome requires safe redacted error evidence")
        require_trimmed_text(self.safe_error_code, label="bounded rework error code")
        if self.outcome_status == "raised":
            if (
                not self.executor_attempted
                or not self.executor_started
                or self.executor_returned
                or not self.executor_raised
                or not self.recovery_required
            ):
                raise ValueError("raised Outcome has contradictory executor facts")
        elif self.outcome_status == "invalid_result":
            if (
                not self.executor_attempted
                or not self.executor_started
                or not self.executor_returned
                or self.executor_raised
                or not self.recovery_required
            ):
                raise ValueError("invalid result Outcome requires recovery")
        elif self.outcome_status == "recovery_required":
            if not self.recovery_required or self.human_escalation_required:
                raise ValueError("recovery Outcome must remain recovery-only")
        elif not self.human_escalation_required:
            raise ValueError("human escalation Outcome must require escalation")

    @staticmethod
    def compute_outcome_replay_key(
        *,
        claim_id: UUID,
        claim_token: str,
        reservation_id: UUID,
        package_id: UUID,
        exact_task_id: UUID,
        exact_run_id: UUID,
    ) -> str:
        return compute_p25_contract_sha256(
            {
                "schema_version": BOUNDED_REWORK_INVOCATION_OUTCOME_REPLAY_SCHEMA_VERSION,
                "claim_id": claim_id,
                "claim_token": claim_token,
                "reservation_id": reservation_id,
                "package_id": package_id,
                "exact_task_id": exact_task_id,
                "exact_run_id": exact_run_id,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p25_contract_sha256(
            self.model_dump(mode="python", exclude={"outcome_fingerprint"})
        )


__all__ = (
    "BOUNDED_REWORK_INVOCATION_OUTCOME_REPLAY_SCHEMA_VERSION",
    "BOUNDED_REWORK_INVOCATION_OUTCOME_SCHEMA_VERSION",
    "BoundedReworkGitActivityKind",
    "BoundedReworkInvocationOutcomeStatus",
    "BoundedReworkScopeValidationStatus",
    "BoundedReworkSideEffectState",
    "ProjectDirectorBoundedReworkInvocationOutcome",
)
