"""Pure domain contracts for Project Director semantic turn interpretation.

These contracts are side-effect free. They do not persist messages, discussion
events, or workspaces; create plans, tasks, or runs; start workers or executors;
or mutate repositories.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_conversation_intelligence import (
    DirectorResponseSource,
    TurnInterpretation,
)


class ConversationRiskSignalType(StrEnum):
    """Side-effect language categories detected before semantic interpretation."""

    TASK_CREATION = "task_creation"
    WORKER_START = "worker_start"
    EXECUTOR_START = "executor_start"
    PLAN_MODIFICATION = "plan_modification"
    PLAN_APPLICATION = "plan_application"
    TASK_DELETION = "task_deletion"
    ACCEPTANCE_CRITERIA_CHANGE = "acceptance_criteria_change"
    GIT_WRITE = "git_write"
    DEPLOYMENT = "deployment"
    PUBLISH = "publish"
    DESTRUCTIVE_DATABASE_CHANGE = "destructive_database_change"


def _contains_sensitive_provider_marker(value: str) -> bool:
    normalized = value.lower()
    return any(
        marker in normalized
        for marker in ("api_key", "api key", "authorization", "bearer ", "sk-")
    )


class ConversationRiskSignal(DomainModel):
    """One deterministic match for possible side-effect language."""

    signal_type: ConversationRiskSignalType
    matched_phrase: str = Field(min_length=1)
    start_index: int = Field(ge=0)
    end_index: int = Field(ge=1)

    @field_validator("matched_phrase", mode="before")
    @classmethod
    def normalize_matched_phrase(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("matched_phrase must be a string.")
        normalized = value.strip()
        if not normalized:
            raise ValueError("matched_phrase cannot be empty.")
        return normalized

    @model_validator(mode="after")
    def validate_span(self) -> "ConversationRiskSignal":
        if self.end_index <= self.start_index:
            raise ValueError("end_index must be greater than start_index.")
        return self


class ConversationRiskScan(DomainModel):
    """Stable, non-sensitive summary of deterministic side-effect signals."""

    signals: list[ConversationRiskSignal] = Field(default_factory=list)
    has_side_effect_signal: bool
    reason_summary: str = Field(min_length=1)

    @field_validator("reason_summary", mode="before")
    @classmethod
    def normalize_reason_summary(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("reason_summary must be a string.")
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason_summary cannot be empty.")
        return normalized

    @model_validator(mode="after")
    def normalize_signal_order_and_validate(self) -> "ConversationRiskScan":
        unique_keys = {
            (signal.signal_type, signal.start_index, signal.end_index)
            for signal in self.signals
        }
        if len(unique_keys) != len(self.signals):
            raise ValueError("Risk signals cannot repeat a type and span.")
        ordered_signals = sorted(
            self.signals,
            key=lambda signal: (
                signal.start_index,
                signal.end_index,
                signal.signal_type.value,
            ),
        )
        object.__setattr__(self, "signals", ordered_signals)
        if self.has_side_effect_signal != bool(self.signals):
            raise ValueError("has_side_effect_signal must match signals.")
        return self


class TurnInterpretationOutcome(DomainModel):
    """One non-persistent semantic interpretation and its governance overlay."""

    interpretation: TurnInterpretation
    risk_scan: ConversationRiskScan
    source: DirectorResponseSource
    source_detail: str = Field(min_length=1)
    receipt_id: str | None = None
    provider_attempted: bool
    fallback_reason: str | None = None
    risk_semantic_conflict: bool = False

    @field_validator("source_detail", "fallback_reason", mode="before")
    @classmethod
    def normalize_non_sensitive_detail(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Outcome detail fields must be strings.")
        normalized = value.strip()
        if not normalized:
            return None
        if _contains_sensitive_provider_marker(normalized):
            raise ValueError("Outcome detail fields cannot contain provider secrets.")
        return normalized

    @model_validator(mode="after")
    def validate_provider_or_fallback_source(self) -> "TurnInterpretationOutcome":
        if self.source not in {
            DirectorResponseSource.PROVIDER,
            DirectorResponseSource.RULE_FALLBACK,
        }:
            raise ValueError("Only provider or rule_fallback sources are allowed.")
        if self.source == DirectorResponseSource.PROVIDER:
            if not self.provider_attempted:
                raise ValueError("Provider outcomes require provider_attempted=True.")
            if self.fallback_reason is not None:
                raise ValueError("Provider outcomes cannot have fallback_reason.")
        else:
            if self.receipt_id is not None:
                raise ValueError("Rule fallback outcomes cannot have receipt_id.")
            if not self.fallback_reason:
                raise ValueError("Rule fallback outcomes require fallback_reason.")
        return self
