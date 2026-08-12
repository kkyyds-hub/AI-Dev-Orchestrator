"""Pure domain contracts for the non-writing Director Shadow comparison seam.

This module is pure domain and side-effect free. It describes diagnostic
summaries for comparing the governed Legacy Director envelope with a
supervised Director Runtime outcome. The models intentionally cannot carry
raw response text, raw candidate payloads, envelopes, or any handle able to
write authoritative state: a shadow result is an observation only and never a
second admission path.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from app.domain._base import DomainModel


class ShadowComparisonError(ValueError):
    """Safe, fail-closed shadow comparison boundary failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ShadowComparisonDimensionStatus(StrEnum):
    """Bounded status recorded for one compared dimension."""

    MISMATCH = "mismatch"


class ShadowComparisonDifference(DomainModel):
    """One bounded per-dimension diagnostic summary.

    Summaries are enum-like bounded scalars only; raw payloads and full
    response text never appear here.
    """

    dimension: str = Field(min_length=1, max_length=64)
    status: ShadowComparisonDimensionStatus
    legacy_summary: str = Field(default="", max_length=256)
    runtime_summary: str = Field(default="", max_length=256)


class ShadowRuntimeFailureSummary(DomainModel):
    """Sanitized runtime failure facts without messages, stacks, or payloads."""

    attempt_state: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=128)
    stage: str = Field(min_length=1, max_length=64)
    retryable: bool


class LegacyShadowObservationMetadata(DomainModel):
    """Optional Legacy-side observation facts absent from the envelope.

    Every field is optional; an absent field makes the related dimension not
    comparable instead of forcing a mismatch, and supplying metadata must
    never require changing the Legacy serving chain.
    """

    duration_ms: float | None = Field(default=None, ge=0)
    usage_keys: tuple[str, ...] | None = None
    attempt_state: str | None = Field(default=None, min_length=1, max_length=64)
    discussion_observed_status: str | None = Field(
        default=None, min_length=1, max_length=64
    )
    discussion_suggested_next_status: str | None = Field(
        default=None, min_length=1, max_length=64
    )

    @field_validator("usage_keys")
    @classmethod
    def validate_usage_keys(
        cls, value: tuple[str, ...] | None
    ) -> tuple[str, ...] | None:
        if value is None:
            return value
        if len(value) > 32:
            raise ValueError("shadow_comparison_usage_keys_invalid")
        for key in value:
            if not isinstance(key, str) or not key.strip() or len(key) > 64:
                raise ValueError("shadow_comparison_usage_keys_invalid")
        return value


class DirectorShadowComparisonResult(DomainModel):
    """Diagnostic-only shadow comparison output.

    Invariants:
    - authoritative, write_allowed, and candidate_admitted are always False.
    - runtime_failed marks a supervised runtime failure; the Legacy chain is
      unaffected and remains the sole serving and authoritative path.
    - semantic_match only states that every comparable dimension matched. It
      does not mean the runtime output is correct, approved, or allowed to
      write.
    - The result carries bounded summaries only and can never transport raw
      response text, discussion delta candidates, or proposal payloads.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)

    request_id: str = Field(min_length=1, max_length=256)
    authoritative: Literal[False] = False
    write_allowed: Literal[False] = False
    candidate_admitted: Literal[False] = False
    runtime_failed: bool
    semantic_match: bool
    differences: tuple[ShadowComparisonDifference, ...] = Field(default_factory=tuple)
    compared_dimensions: tuple[str, ...] = Field(default_factory=tuple)
    unavailable_dimensions: tuple[str, ...] = Field(default_factory=tuple)
    runtime_failure_summary: ShadowRuntimeFailureSummary | None = None


__all__ = (
    "DirectorShadowComparisonResult",
    "LegacyShadowObservationMetadata",
    "ShadowComparisonDifference",
    "ShadowComparisonDimensionStatus",
    "ShadowComparisonError",
    "ShadowRuntimeFailureSummary",
)
