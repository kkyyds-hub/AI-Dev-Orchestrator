"""Immutable P24 completion-review evidence reconstructed from P21-C/P21-D."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime


SOURCE_COMPLETION_REVIEW_EVIDENCE_SCHEMA_VERSION = (
    "p24-b-source-completion-review-evidence.v1"
)
SOURCE_COMPLETION_REVIEW_EVIDENCE_KIND = (
    "validated_candidate_diff_review_auto_continue"
)

SourceCompletionReviewBlockedReason = Literal[
    "source_completion_review_evidence_missing",
    "source_completion_review_evidence_id_invalid",
    "source_completion_review_evidence_conflict",
    "source_completion_review_message_invalid",
    "source_completion_review_fingerprint_mismatch",
    "source_completion_review_diff_invalid",
    "source_completion_review_terminal_result_unsupported",
    "source_completion_review_verdict_not_allowed",
    "source_completion_review_changes_required",
    "source_completion_review_disposition_missing",
    "source_completion_review_disposition_invalid",
    "source_completion_review_disposition_not_continue",
    "source_completion_review_disposition_fingerprint_mismatch",
    "source_completion_review_stale_for_run",
    "source_completion_review_timeline_invalid",
]

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectDirectorSourceCompletionReviewEvidence(DomainModel):
    """Exact persisted completion-review facts for one successful source Run."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[
        "p24-b-source-completion-review-evidence.v1"
    ] = SOURCE_COMPLETION_REVIEW_EVIDENCE_SCHEMA_VERSION
    review_evidence_kind: Literal[
        "validated_candidate_diff_review_auto_continue"
    ] = SOURCE_COMPLETION_REVIEW_EVIDENCE_KIND

    review_message_id: UUID
    review_result_fingerprint: str = Field(min_length=64, max_length=64)
    review_session_id: UUID
    review_project_id: UUID
    review_task_id: UUID

    source_preflight_message_id: UUID
    source_diff_message_id: UUID
    source_diff_sha256: str = Field(min_length=64, max_length=64)

    review_output_schema_version: str = Field(min_length=1, max_length=100)
    review_status: Literal["reviewed"] = "reviewed"
    review_verdict: Literal[
        "no_blocking_findings",
        "non_blocking_findings",
    ]
    review_risk_level: Literal["low", "medium", "high"]

    disposition_message_id: UUID
    disposition_id: UUID
    disposition_status: Literal["computed"] = "computed"
    disposition_type: Literal["AUTO_CONTINUE"] = "AUTO_CONTINUE"
    disposition_review_result_fingerprint: str = Field(
        min_length=64,
        max_length=64,
    )

    review_message_created_at: datetime
    source_diff_message_created_at: datetime
    disposition_message_created_at: datetime

    product_runtime_git_write_allowed: Literal[False] = False
    forbidden_actions: list[str]

    @field_validator(
        "review_result_fingerprint",
        "source_diff_sha256",
        "disposition_review_result_fingerprint",
        mode="after",
    )
    @classmethod
    def require_sha256(cls, value: str) -> str:
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError("completion review hashes must be lowercase SHA-256")
        return value

    @field_validator(
        "review_message_created_at",
        "source_diff_message_created_at",
        "disposition_message_created_at",
        mode="after",
    )
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("completion review datetime is required")
        return normalized

    @model_validator(mode="after")
    def validate_review_evidence(self) -> "ProjectDirectorSourceCompletionReviewEvidence":
        if (
            self.review_result_fingerprint
            != self.disposition_review_result_fingerprint
        ):
            raise ValueError("review and disposition fingerprints must match")
        if not self.forbidden_actions or len(self.forbidden_actions) != len(
            set(self.forbidden_actions)
        ):
            raise ValueError("completion review forbidden actions must be unique")
        if (
            self.review_message_created_at < self.source_diff_message_created_at
            or self.disposition_message_created_at < self.review_message_created_at
        ):
            raise ValueError("completion review timeline is invalid")
        return self


class SourceCompletionReviewEvidenceResolution(DomainModel):
    """Fail-closed result for exact declared completion-review evidence IDs."""

    model_config = ConfigDict(frozen=True)

    status: Literal["resolved", "blocked"]
    snapshot: ProjectDirectorSourceCompletionReviewEvidence | None = None
    blocked_reasons: list[SourceCompletionReviewBlockedReason] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_resolution(self) -> "SourceCompletionReviewEvidenceResolution":
        if self.status == "resolved":
            if self.snapshot is None or self.blocked_reasons:
                raise ValueError("resolved review evidence requires only a snapshot")
        elif self.snapshot is not None or not self.blocked_reasons:
            raise ValueError("blocked review evidence requires only stable reasons")
        if len(self.blocked_reasons) != len(set(self.blocked_reasons)):
            raise ValueError("completion review blocked reasons must be unique")
        return self

    @classmethod
    def blocked(
        cls,
        *reasons: SourceCompletionReviewBlockedReason,
    ) -> "SourceCompletionReviewEvidenceResolution":
        return cls(
            status="blocked",
            snapshot=None,
            blocked_reasons=list(dict.fromkeys(reasons)),
        )


__all__ = (
    "ProjectDirectorSourceCompletionReviewEvidence",
    "SOURCE_COMPLETION_REVIEW_EVIDENCE_KIND",
    "SOURCE_COMPLETION_REVIEW_EVIDENCE_SCHEMA_VERSION",
    "SourceCompletionReviewBlockedReason",
    "SourceCompletionReviewEvidenceResolution",
)
