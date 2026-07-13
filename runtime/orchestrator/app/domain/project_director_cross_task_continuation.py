"""Immutable P24-D2B1 cross-Task continuation root contracts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime
from app.domain.project_director_next_task_instruction_package import (
    ProjectDirectorNextTaskInstructionPackage,
    compute_p24_contract_sha256,
)


CROSS_TASK_CONTINUATION_SCHEMA_VERSION = "p24-d-continuation.v1"
CROSS_TASK_CONTINUATION_REPLAY_SCHEMA_VERSION = (
    "p24-continuation-replay.v1"
)
CROSS_TASK_CONTINUATION_ACTION = "cross_task_auto_continue"

CrossTaskContinuationRootStatus = Literal[
    "prepared",
    "plan_queue_exhausted",
]
CrossTaskContinuationPreparationStatus = Literal[
    "package_prepared",
    "package_replayed",
    "plan_queue_exhausted_recorded",
    "plan_queue_exhausted_replayed",
    "blocked",
]
CrossTaskContinuationBlockedReason = Literal[
    "continuation_candidate_invalid",
    "continuation_history_invalid",
    "continuation_history_conflict",
    "continuation_replay_conflict",
    "continuation_package_invalid",
    "continuation_root_invalid",
    "continuation_git_boundary_violation",
    "continuation_persistence_failed",
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
    "uncontrolled_workspace_write",
    "task_claim",
    "run_creation",
    "worker_invocation",
    "verification_command_execution",
}


class ProjectDirectorCrossTaskContinuationRoot(DomainModel):
    """First immutable record for one exact source completion identity."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["p24-d-continuation.v1"] = (
        CROSS_TASK_CONTINUATION_SCHEMA_VERSION
    )

    record_id: UUID
    continuation_id: UUID
    continuation_fingerprint: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=64, max_length=64)
    created_at: datetime

    sequence_no: Literal[1] = 1
    previous_record_id: None = None
    replay_of_record_id: None = None

    action: Literal["cross_task_auto_continue"] = CROSS_TASK_CONTINUATION_ACTION
    status: CrossTaskContinuationRootStatus

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

    next_task_id: UUID | None = None
    instruction_package_id: UUID | None = None
    instruction_package_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    instruction_candidate_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )

    exact_run_id: None = None
    worker_reservation_id: None = None
    worker_invocation_claim_id: None = None
    worker_outcome_id: None = None

    new_task_created: Literal[False] = False
    run_created: Literal[False] = False
    worker_called: Literal[False] = False

    blocked_reasons: tuple[CrossTaskContinuationBlockedReason, ...] = ()
    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: tuple[str, ...]

    @field_validator("created_at", mode="after")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None or normalized.tzinfo is None:
            raise ValueError("continuation root created_at must be UTC-aware")
        return normalized

    @field_validator(
        "continuation_fingerprint",
        "idempotency_key",
        "source_completion_evidence_fingerprint",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("continuation root hashes must be lowercase SHA-256")
        return value

    @field_validator(
        "instruction_package_fingerprint",
        "instruction_candidate_fingerprint",
    )
    @classmethod
    def require_optional_sha256(cls, value: str | None) -> str | None:
        if value is not None and not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("continuation package hashes must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_root(self) -> "ProjectDirectorCrossTaskContinuationRoot":
        if self.record_id == self.continuation_id:
            raise ValueError("continuation record and logical IDs must differ")
        if self.blocked_reasons:
            raise ValueError("continuation root branches cannot contain blocked reasons")

        package_fields = (
            self.instruction_package_id,
            self.instruction_package_fingerprint,
            self.instruction_candidate_fingerprint,
        )
        if self.status == "prepared":
            if self.next_task_id is None or any(item is None for item in package_fields):
                raise ValueError("prepared continuation root requires its exact package")
            if self.next_task_id == self.source_task_id:
                raise ValueError("next Task must differ from the source Task")
            if self.instruction_package_id in {
                self.record_id,
                self.continuation_id,
            }:
                raise ValueError("continuation and package identities must be distinct")
        elif self.next_task_id is not None or any(
            item is not None for item in package_fields
        ):
            raise ValueError("exhausted continuation root cannot contain next-Task facts")

        if (
            not self.forbidden_actions
            or len(self.forbidden_actions) != len(set(self.forbidden_actions))
            or any(
                not action.strip() or action != action.strip()
                for action in self.forbidden_actions
            )
            or not _REQUIRED_FORBIDDEN_ACTIONS.issubset(self.forbidden_actions)
        ):
            raise ValueError("continuation root forbidden actions are incomplete")
        if self.idempotency_key != self.compute_idempotency_key(
            session_id=self.session_id,
            project_id=self.project_id,
            plan_version_id=self.plan_version_id,
            task_creation_record_id=self.task_creation_record_id,
            source_task_id=self.source_task_id,
            source_run_id=self.source_run_id,
            source_completion_evidence_id=self.source_completion_evidence_id,
        ):
            raise ValueError("continuation idempotency key does not match")
        if self.continuation_fingerprint != self.compute_fingerprint():
            raise ValueError("continuation fingerprint does not match")
        return self

    @staticmethod
    def compute_idempotency_key(
        *,
        session_id: UUID,
        project_id: UUID,
        plan_version_id: UUID,
        task_creation_record_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
        source_completion_evidence_id: UUID,
    ) -> str:
        return compute_p24_contract_sha256(
            {
                "schema_version": CROSS_TASK_CONTINUATION_REPLAY_SCHEMA_VERSION,
                "action": CROSS_TASK_CONTINUATION_ACTION,
                "session_id": session_id,
                "project_id": project_id,
                "plan_version_id": plan_version_id,
                "task_creation_record_id": task_creation_record_id,
                "source_task_id": source_task_id,
                "source_run_id": source_run_id,
                "source_completion_evidence_id": source_completion_evidence_id,
            }
        )

    def compute_fingerprint(self) -> str:
        return compute_p24_contract_sha256(
            self.model_dump(mode="python", exclude={"continuation_fingerprint"})
        )


class ProjectDirectorCrossTaskContinuationPreparationResult(DomainModel):
    """Strict outcome of the future atomic continuation preparation service."""

    model_config = ConfigDict(frozen=True)

    status: CrossTaskContinuationPreparationStatus
    continuation_root: ProjectDirectorCrossTaskContinuationRoot | None = None
    instruction_package: ProjectDirectorNextTaskInstructionPackage | None = None
    blocked_reasons: tuple[CrossTaskContinuationBlockedReason, ...] = ()
    product_runtime_git_write_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> "ProjectDirectorCrossTaskContinuationPreparationResult":
        if self.status in {"package_prepared", "package_replayed"}:
            if (
                self.continuation_root is None
                or self.continuation_root.status != "prepared"
                or self.instruction_package is None
                or self.blocked_reasons
            ):
                raise ValueError("prepared continuation result is inconsistent")
            root = self.continuation_root
            package = self.instruction_package
            if (
                root.instruction_package_id != package.package_id
                or root.instruction_package_fingerprint
                != package.package_fingerprint
                or root.instruction_candidate_fingerprint
                != package.instruction_candidate_fingerprint
                or root.continuation_id != package.continuation_id
                or root.next_task_id != package.next_task_id
                or root.session_id != package.session_id
                or root.project_id != package.project_id
                or root.plan_version_id != package.plan_version_id
                or root.task_creation_record_id != package.task_creation_record_id
                or root.source_task_id != package.source_task_id
                or root.source_run_id != package.source_run_id
                or root.source_completion_evidence_id
                != package.source_completion_evidence_id
                or root.source_completion_evidence_fingerprint
                != package.source_completion_evidence_fingerprint
            ):
                raise ValueError("continuation root does not bind the exact package")
        elif self.status in {
            "plan_queue_exhausted_recorded",
            "plan_queue_exhausted_replayed",
        }:
            if (
                self.continuation_root is None
                or self.continuation_root.status != "plan_queue_exhausted"
                or self.instruction_package is not None
                or self.blocked_reasons
            ):
                raise ValueError("exhausted continuation result is inconsistent")
        elif (
            self.continuation_root is not None
            or self.instruction_package is not None
            or not self.blocked_reasons
            or len(self.blocked_reasons) != len(set(self.blocked_reasons))
        ):
            raise ValueError("blocked continuation result is inconsistent")
        return self


__all__ = (
    "CROSS_TASK_CONTINUATION_ACTION",
    "CROSS_TASK_CONTINUATION_REPLAY_SCHEMA_VERSION",
    "CROSS_TASK_CONTINUATION_SCHEMA_VERSION",
    "CrossTaskContinuationBlockedReason",
    "CrossTaskContinuationPreparationStatus",
    "CrossTaskContinuationRootStatus",
    "ProjectDirectorCrossTaskContinuationPreparationResult",
    "ProjectDirectorCrossTaskContinuationRoot",
)
