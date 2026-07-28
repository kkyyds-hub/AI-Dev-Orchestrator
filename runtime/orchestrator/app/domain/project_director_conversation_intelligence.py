"""Pure domain contracts for Project Director conversation intelligence.

This module is pure domain and side-effect free. It does not persist discussion
state, create plans/tasks/runs, start workers/executors, or mutate repositories.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel
from app.domain.project_director_discussion import DiscussionDelta


class ConversationMode(StrEnum):
    """Semantic mode used for context selection and governance only."""

    GENERAL_DISCUSSION = "general_discussion"
    SOLUTION_EXPLORATION = "solution_exploration"
    OPTION_COMPARISON = "option_comparison"
    CLARIFICATION = "clarification"
    CHALLENGE = "challenge"
    CONSTRAINT_UPDATE = "constraint_update"
    PREFERENCE_UPDATE = "preference_update"
    DECISION_CONFIRMATION = "decision_confirmation"
    FORMALIZATION_REQUEST = "formalization_request"
    ACTION_REQUEST = "action_request"
    STATUS_QUERY = "status_query"


class FormalizationTarget(StrEnum):
    """First-version formalization target whitelist."""

    PLAN_REVISION = "plan_revision"


class FormalizationChangeType(StrEnum):
    """Candidate draft change type, without changing a PlanVersion."""

    ADD = "add"
    UPDATE = "update"
    REMOVE = "remove"


class DirectorResponseSource(StrEnum):
    """Origin of the response content."""

    PROVIDER = "provider"
    RULE_FALLBACK = "rule_fallback"
    SYSTEM = "system"


def _reject_duplicate_ids(value: list[UUID]) -> list[UUID]:
    if len(value) != len(set(value)):
        raise ValueError("Referenced IDs cannot contain duplicates.")
    return value


class TurnInterpretation(DomainModel):
    """Side-effect-free semantic interpretation of one conversation turn."""

    conversation_mode: ConversationMode
    primary_intent: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    formal_action_requested: bool = False
    hypothetical_action: bool = False
    referenced_option_ids: list[UUID] = Field(default_factory=list)
    referenced_entity_ids: list[UUID] = Field(default_factory=list)
    needs_formal_fact_context: bool = False
    needs_discussion_history: bool = False
    needs_retrieval: bool = False
    reason_summary: str = Field(min_length=1)

    @field_validator("primary_intent", "reason_summary", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text cannot be empty.")
        return normalized

    @field_validator("referenced_option_ids", "referenced_entity_ids")
    @classmethod
    def reject_duplicate_referenced_ids(cls, value: list[UUID]) -> list[UUID]:
        return _reject_duplicate_ids(value)

    @model_validator(mode="after")
    def reject_conflicting_action_flags(self) -> "TurnInterpretation":
        if self.formal_action_requested and self.hypothetical_action:
            raise ValueError(
                "formal_action_requested and hypothetical_action cannot both be true."
            )
        return self


class FormalizationChange(DomainModel):
    """One draft-only change proposed for later formalization."""

    change_type: FormalizationChangeType
    subject_key: str
    summary: str
    source_event_ids: list[UUID] = Field(default_factory=list)

    @field_validator("source_event_ids")
    @classmethod
    def reject_duplicate_source_event_ids(cls, value: list[UUID]) -> list[UUID]:
        return _reject_duplicate_ids(value)


def ordered_unique_formalization_source_event_ids(
    changes: list[FormalizationChange],
) -> list[UUID]:
    """Aggregate change lineage without losing the Provider's source order."""

    event_ids: list[UUID] = []
    for change in changes:
        for event_id in change.source_event_ids:
            if event_id not in event_ids:
                event_ids.append(event_id)
    return event_ids


class FormalizationProposal(DomainModel):
    """A proposed plan revision that remains pending user confirmation."""

    proposal_id: UUID
    target: FormalizationTarget
    workspace_version: int = Field(ge=1)
    summary: str
    changes: list[FormalizationChange] = Field(min_length=1)
    source_message_ids: list[UUID] = Field(min_length=1)
    source_event_ids: list[UUID] = Field(default_factory=list)
    risk_summary: str
    requires_confirmation: Literal[True] = True
    status: Literal["proposed"] = "proposed"

    @field_validator("source_message_ids", "source_event_ids")
    @classmethod
    def reject_duplicate_source_ids(cls, value: list[UUID]) -> list[UUID]:
        return _reject_duplicate_ids(value)

    @model_validator(mode="after")
    def derive_or_validate_source_event_ids(self) -> "FormalizationProposal":
        """Keep top-level lineage canonical while accepting legacy Provider output."""

        derived_event_ids = ordered_unique_formalization_source_event_ids(
            self.changes
        )
        if not derived_event_ids:
            raise ValueError("Formalization proposal source event lineage is required.")
        if "source_event_ids" not in self.model_fields_set:
            object.__setattr__(self, "source_event_ids", derived_event_ids)
        elif self.source_event_ids != derived_event_ids:
            raise ValueError(
                "Formalization proposal source event lineage must match changes."
            )
        return self


class DirectorResponseEnvelope(DomainModel):
    """A response contract that does not write messages or mutate a workspace."""

    answer: str = Field(min_length=1)
    turn_interpretation: TurnInterpretation
    discussion_delta: DiscussionDelta = Field(default_factory=DiscussionDelta)
    formalization_proposal: FormalizationProposal | None = None
    requires_confirmation: bool = False
    source: DirectorResponseSource
    source_detail: str = Field(min_length=1)

    @field_validator("answer", "source_detail", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text cannot be empty.")
        return normalized

    @model_validator(mode="after")
    def validate_response_invariants(self) -> "DirectorResponseEnvelope":
        if self.formalization_proposal is not None and not self.requires_confirmation:
            raise ValueError("Formalization proposals require confirmation.")
        if self.source == DirectorResponseSource.RULE_FALLBACK:
            if self.discussion_delta.operations:
                raise ValueError("rule_fallback responses cannot carry discussion operations.")
            if self.formalization_proposal is not None:
                raise ValueError("rule_fallback responses cannot carry formalization proposals.")
        return self
