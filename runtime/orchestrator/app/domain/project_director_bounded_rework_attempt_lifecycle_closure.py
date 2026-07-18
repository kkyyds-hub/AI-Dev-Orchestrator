"""Durable terminal state for one P25 attempt's exact P23 Task/Run pair."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid5

from pydantic import ConfigDict, Field, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_bounded_rework_contract import compute_p25_contract_sha256
from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import TaskHumanStatus, TaskStatus


P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_SCHEMA_VERSION = "p25-i-d.v1"
P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_NAMESPACE = UUID(
    "56dcf682-5a5a-4d0c-92f4-19138e621297"
)


class ProjectDirectorBoundedReworkAttemptLifecycleClosure(DomainModel):
    """One replay-safe lifecycle closeout for the attempt named by P25-I."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["p25-i-d.v1"] = (
        P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_SCHEMA_VERSION
    )
    closure_id: UUID
    closure_fingerprint: str = Field(min_length=64, max_length=64)
    closure_replay_key: str = Field(min_length=64, max_length=64)
    created_at: datetime

    source_convergence_decision_message_id: UUID
    source_convergence_decision_id: UUID
    source_convergence_decision_fingerprint: str = Field(min_length=64, max_length=64)
    source_convergence_decision_replay_key: str = Field(min_length=64, max_length=64)
    source_p23_dispatch_consumption_message_id: UUID
    source_p23_dispatch_consumption_id: UUID
    source_p23_dispatch_consumption_fingerprint: str = Field(min_length=64, max_length=64)
    source_package_id: UUID
    source_attempt_id: UUID
    source_executor_outcome_id: UUID
    source_candidate_diff_message_id: UUID
    source_review_outcome_message_id: UUID | None = None
    source_p22_summary_message_id: UUID | None = None
    source_task_id: UUID
    source_run_id: UUID
    current_rework_attempt_index: int = Field(ge=0, lt=3)
    next_rework_attempt_index: int | None = Field(default=None, ge=1, lt=3)
    decision_type: Literal["CONVERGED", "NEXT_ATTEMPT_ELIGIBLE", "ESCALATE_TO_HUMAN"]
    decision_reason: str = Field(min_length=1, max_length=100)
    closure_kind: Literal[
        "converged_success", "retryable_verification_failure", "terminal_human_escalation"
    ]
    task_status_before: TaskStatus
    task_status_after: TaskStatus
    task_human_status_before: TaskHumanStatus
    task_human_status_after: TaskHumanStatus
    run_status_before: RunStatus
    run_status_after: RunStatus
    run_failure_category: RunFailureCategory | None = None
    quality_gate_passed: bool
    product_runtime_git_write_allowed: Literal[False] = False
    worker_started: Literal[False] = False
    task_created: Literal[False] = False
    run_created: Literal[False] = False

    @model_validator(mode="after")
    def validate_identity_and_state(self):
        if self.closure_id != uuid5(
            P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_NAMESPACE,
            self.closure_replay_key,
        ):
            raise ValueError("P25-I-D closure identity is not deterministic")
        if self.closure_fingerprint != self.compute_fingerprint():
            raise ValueError("P25-I-D closure fingerprint does not match")
        if self.task_status_before != TaskStatus.RUNNING or self.run_status_before != RunStatus.RUNNING:
            raise ValueError("P25-I-D only closes a running Task and Run")
        if self.closure_kind == "converged_success":
            expected = ("CONVERGED", TaskStatus.COMPLETED, RunStatus.SUCCEEDED, None, True)
        elif self.closure_kind == "retryable_verification_failure":
            expected = (
                "NEXT_ATTEMPT_ELIGIBLE", TaskStatus.FAILED, RunStatus.FAILED,
                RunFailureCategory.VERIFICATION_FAILED, False,
            )
        else:
            expected = (
                "ESCALATE_TO_HUMAN", TaskStatus.WAITING_HUMAN, RunStatus.FAILED,
                RunFailureCategory.VERIFICATION_FAILED, False,
            )
        if (
            self.decision_type,
            self.task_status_after,
            self.run_status_after,
            self.run_failure_category,
            self.quality_gate_passed,
        ) != expected:
            raise ValueError("P25-I-D closure state mapping is invalid")
        return self

    def compute_fingerprint(self) -> str:
        return compute_p25_contract_sha256(
            self.model_dump(mode="json", exclude={"closure_fingerprint", "created_at"})
        )

    @staticmethod
    def compute_replay_key(*, decision_replay_key: str, source_run_id: UUID) -> str:
        return compute_p25_contract_sha256(
            {"schema_version": P25_BOUNDED_REWORK_ATTEMPT_LIFECYCLE_CLOSURE_SCHEMA_VERSION,
             "decision_replay_key": decision_replay_key, "source_run_id": str(source_run_id)}
        )
