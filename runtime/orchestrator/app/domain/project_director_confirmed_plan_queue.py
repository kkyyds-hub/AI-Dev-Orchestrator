"""Immutable P24-C confirmed-plan queue resolution contracts."""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel


CONFIRMED_PLAN_QUEUE_SCHEMA_VERSION = "p24-c-confirmed-plan-queue.v1"

ConfirmedPlanQueueResolutionStatus = Literal[
    "next_task_resolved",
    "plan_queue_exhausted",
    "blocked",
]
ConfirmedPlanQueueBlockedReason = Literal[
    "source_completion_evidence_missing",
    "source_completion_evidence_invalid",
    "source_completion_evidence_scope_mismatch",
    "plan_creation_record_missing",
    "plan_creation_record_conflict",
    "plan_lineage_invalid",
    "source_task_not_in_plan_queue",
    "next_task_missing",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorConfirmedPlanQueueSnapshot(DomainModel):
    """One strictly validated authoritative queue and its immediate successor."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["p24-c-confirmed-plan-queue.v1"] = (
        CONFIRMED_PLAN_QUEUE_SCHEMA_VERSION
    )

    source_completion_evidence_id: UUID
    source_completion_evidence_fingerprint: str = Field(min_length=64, max_length=64)

    session_id: UUID
    project_id: UUID
    plan_version_id: UUID
    plan_version_no: int = Field(ge=1)
    task_creation_record_id: UUID

    queue_task_ids: list[UUID]
    task_count: int = Field(ge=1)
    queue_fingerprint: str = Field(min_length=64, max_length=64)

    source_task_id: UUID
    source_task_index: int = Field(ge=0)
    next_task_id: UUID | None
    next_task_index: int | None = Field(ge=0)
    queue_exhausted: bool

    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: list[str]

    @field_validator(
        "source_completion_evidence_fingerprint",
        "queue_fingerprint",
        mode="after",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("confirmed plan queue hashes must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_queue(self) -> "ProjectDirectorConfirmedPlanQueueSnapshot":
        if (
            not self.queue_task_ids
            or len(self.queue_task_ids) != len(set(self.queue_task_ids))
            or self.task_count != len(self.queue_task_ids)
            or self.source_task_index >= self.task_count
            or self.queue_task_ids[self.source_task_index] != self.source_task_id
        ):
            raise ValueError("confirmed plan queue identity is invalid")
        if self.queue_exhausted:
            if (
                self.next_task_id is not None
                or self.next_task_index is not None
                or self.source_task_index != self.task_count - 1
            ):
                raise ValueError("exhausted plan queue has an invalid successor")
        elif (
            self.next_task_id is None
            or self.next_task_index is None
            or self.next_task_index != self.source_task_index + 1
            or self.next_task_index >= self.task_count
            or self.queue_task_ids[self.next_task_index] != self.next_task_id
        ):
            raise ValueError("resolved plan queue has an invalid successor")
        if (
            not self.forbidden_actions
            or len(self.forbidden_actions) != len(set(self.forbidden_actions))
        ):
            raise ValueError("confirmed plan queue forbidden actions must be unique")
        return self


class ProjectDirectorConfirmedPlanQueueResolution(DomainModel):
    """Fail-closed result for exact next-Task resolution."""

    model_config = ConfigDict(frozen=True)

    status: ConfirmedPlanQueueResolutionStatus
    snapshot: ProjectDirectorConfirmedPlanQueueSnapshot | None = None
    blocked_reasons: list[ConfirmedPlanQueueBlockedReason] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_resolution(self) -> "ProjectDirectorConfirmedPlanQueueResolution":
        if self.status == "blocked":
            if self.snapshot is not None or not self.blocked_reasons:
                raise ValueError("blocked queue resolution requires stable reasons only")
        else:
            if self.snapshot is None or self.blocked_reasons:
                raise ValueError("successful queue resolution requires a snapshot only")
            expected_status = (
                "plan_queue_exhausted"
                if self.snapshot.queue_exhausted
                else "next_task_resolved"
            )
            if self.status != expected_status:
                raise ValueError("queue resolution status does not match its snapshot")
        if len(self.blocked_reasons) != len(set(self.blocked_reasons)):
            raise ValueError("queue resolution blocked reasons must be unique")
        return self

    @classmethod
    def blocked(
        cls,
        *reasons: ConfirmedPlanQueueBlockedReason,
    ) -> "ProjectDirectorConfirmedPlanQueueResolution":
        return cls(
            status="blocked",
            snapshot=None,
            blocked_reasons=list(dict.fromkeys(reasons)),
        )


__all__ = (
    "CONFIRMED_PLAN_QUEUE_SCHEMA_VERSION",
    "ConfirmedPlanQueueBlockedReason",
    "ConfirmedPlanQueueResolutionStatus",
    "ProjectDirectorConfirmedPlanQueueResolution",
    "ProjectDirectorConfirmedPlanQueueSnapshot",
)
