"""Immutable P24 completion-delivery evidence for one exact version."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime


SOURCE_COMPLETION_DELIVERY_EVIDENCE_SCHEMA_VERSION = (
    "p24-b-source-completion-delivery-evidence.v1"
)
SOURCE_COMPLETION_DELIVERY_EVIDENCE_KIND = "deliverable_version_persisted"

SourceCompletionDeliveryBlockedReason = Literal[
    "source_completion_delivery_evidence_missing",
    "source_completion_delivery_evidence_id_invalid",
    "source_completion_delivery_evidence_conflict",
    "source_completion_delivery_evidence_kind_unsupported",
    "source_completion_delivery_deliverable_missing",
    "source_completion_delivery_version_missing",
    "source_completion_delivery_version_mismatch",
    "source_completion_delivery_project_mismatch",
    "source_completion_delivery_task_run_mismatch",
    "source_completion_delivery_version_lineage_invalid",
    "source_completion_delivery_fingerprint_mismatch",
    "source_completion_delivery_content_hash_mismatch",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorSourceCompletionDeliveryEvidence(DomainModel):
    """Readonly snapshot reconstructed from an exact persisted version."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[
        "p24-b-source-completion-delivery-evidence.v1"
    ] = SOURCE_COMPLETION_DELIVERY_EVIDENCE_SCHEMA_VERSION
    delivery_evidence_kind: Literal["deliverable_version_persisted"] = (
        SOURCE_COMPLETION_DELIVERY_EVIDENCE_KIND
    )

    deliverable_id: UUID
    deliverable_version_id: UUID
    deliverable_version_fingerprint: str = Field(min_length=64, max_length=64)

    project_id: UUID
    source_task_id: UUID
    source_run_id: UUID

    deliverable_type: str = Field(min_length=1, max_length=100)
    deliverable_title: str = Field(min_length=1, max_length=200)
    deliverable_stage: str = Field(min_length=1, max_length=100)
    deliverable_created_by_role_code: str = Field(min_length=1, max_length=100)

    version_number: int = Field(ge=1)
    version_author_role_code: str = Field(min_length=1, max_length=100)
    version_summary: str = Field(min_length=1, max_length=1_000)
    version_content_sha256: str = Field(min_length=64, max_length=64)
    version_content_bytes: int = Field(ge=1)
    version_content_format: str = Field(min_length=1, max_length=100)
    version_created_at: datetime

    deliverable_current_version_number_at_validation: int = Field(ge=1)
    declared_delivery_evidence_ids: list[UUID]

    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: list[str]

    @field_validator(
        "deliverable_version_fingerprint",
        "version_content_sha256",
        mode="after",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("delivery evidence hashes must be lowercase SHA-256")
        return value

    @field_validator("version_created_at", mode="after")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("delivery evidence version timestamp is required")
        return normalized

    @model_validator(mode="after")
    def validate_delivery_evidence(
        self,
    ) -> "ProjectDirectorSourceCompletionDeliveryEvidence":
        if self.declared_delivery_evidence_ids != [
            self.deliverable_id,
            self.deliverable_version_id,
        ]:
            raise ValueError("delivery evidence IDs must preserve exact declared order")
        if self.deliverable_id == self.deliverable_version_id:
            raise ValueError("delivery evidence IDs must be distinct")
        if self.deliverable_current_version_number_at_validation < self.version_number:
            raise ValueError("delivery evidence version lineage is invalid")
        if (
            not self.forbidden_actions
            or len(self.forbidden_actions) != len(set(self.forbidden_actions))
        ):
            raise ValueError("delivery evidence forbidden actions must be unique")
        return self


class SourceCompletionDeliveryEvidenceResolution(DomainModel):
    """Fail-closed result for exact declared completion-delivery IDs."""

    model_config = ConfigDict(frozen=True)

    status: Literal["resolved", "blocked"]
    snapshot: ProjectDirectorSourceCompletionDeliveryEvidence | None = None
    blocked_reasons: list[SourceCompletionDeliveryBlockedReason] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_resolution(self) -> "SourceCompletionDeliveryEvidenceResolution":
        if self.status == "resolved":
            if self.snapshot is None or self.blocked_reasons:
                raise ValueError("resolved delivery evidence requires only a snapshot")
        elif self.snapshot is not None or not self.blocked_reasons:
            raise ValueError("blocked delivery evidence requires only stable reasons")
        if len(self.blocked_reasons) != len(set(self.blocked_reasons)):
            raise ValueError("completion delivery blocked reasons must be unique")
        return self

    @classmethod
    def blocked(
        cls,
        *reasons: SourceCompletionDeliveryBlockedReason,
    ) -> "SourceCompletionDeliveryEvidenceResolution":
        return cls(
            status="blocked",
            snapshot=None,
            blocked_reasons=list(dict.fromkeys(reasons)),
        )


__all__ = (
    "ProjectDirectorSourceCompletionDeliveryEvidence",
    "SOURCE_COMPLETION_DELIVERY_EVIDENCE_KIND",
    "SOURCE_COMPLETION_DELIVERY_EVIDENCE_SCHEMA_VERSION",
    "SourceCompletionDeliveryBlockedReason",
    "SourceCompletionDeliveryEvidenceResolution",
)
