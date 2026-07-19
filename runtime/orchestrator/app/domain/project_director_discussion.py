"""Pure domain contracts for Project Director discussions.

This module is pure domain and side-effect free. It does not persist discussion
state, create plans/tasks/runs, start workers/executors, or mutate repositories.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class DiscussionStatus(StrEnum):
    """Lifecycle state for a discussion, independent of reply wording."""

    EXPLORING = "exploring"
    COMPARING = "comparing"
    CONVERGING = "converging"
    READY_TO_FORMALIZE = "ready_to_formalize"
    FORMALIZED = "formalized"
    PAUSED = "paused"


class DiscussionEventStatus(StrEnum):
    """Current status of an immutable discussion event."""

    ACTIVE = "active"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    CONFIRMED = "confirmed"
    HISTORICAL = "historical"


class DiscussionEventType(StrEnum):
    """Whitelisted discussion event semantics."""

    TOPIC_SET = "topic_set"
    OPTION_ADDED = "option_added"
    OPTION_UPDATED = "option_updated"
    OPTION_PREFERRED = "option_preferred"
    OPTION_REJECTED = "option_rejected"
    CONSTRAINT_ADDED = "constraint_added"
    CONSTRAINT_UPDATED = "constraint_updated"
    CONSTRAINT_SUPERSEDED = "constraint_superseded"
    CONCERN_ADDED = "concern_added"
    ASSUMPTION_ADDED = "assumption_added"
    ASSUMPTION_REJECTED = "assumption_rejected"
    OPEN_QUESTION_ADDED = "open_question_added"
    OPEN_QUESTION_RESOLVED = "open_question_resolved"
    TEMPORARY_CONCLUSION_ADDED = "temporary_conclusion_added"
    USER_CORRECTION_RECORDED = "user_correction_recorded"
    DECISION_CONFIRMED = "decision_confirmed"
    FORMALIZATION_REQUESTED = "formalization_requested"
    FORMALIZATION_CANCELLED = "formalization_cancelled"


class DiscussionActorClaim(StrEnum):
    """Provenance asserted for a discussion operation or event."""

    USER_EXPLICIT = "user_explicit"
    USER_INFERRED = "user_inferred"
    ASSISTANT_PROPOSAL = "assistant_proposal"
    SYSTEM_FACT = "system_fact"
    FORMAL_PROJECT_FACT = "formal_project_fact"


class DiscussionOptionStatus(StrEnum):
    """Status of one candidate option in a discussion workspace."""

    ACTIVE = "active"
    PREFERRED = "preferred"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    HISTORICAL = "historical"


class DiscussionDeltaOperationType(StrEnum):
    """Whitelisted candidate operations proposed by a model."""

    SET_TOPIC = "set_topic"
    ADD_OPTION = "add_option"
    UPDATE_OPTION = "update_option"
    PREFER_OPTION = "prefer_option"
    REJECT_OPTION = "reject_option"
    ADD_CONSTRAINT = "add_constraint"
    UPDATE_CONSTRAINT = "update_constraint"
    SUPERSEDE_CONSTRAINT = "supersede_constraint"
    ADD_CONCERN = "add_concern"
    ADD_ASSUMPTION = "add_assumption"
    REJECT_ASSUMPTION = "reject_assumption"
    ADD_OPEN_QUESTION = "add_open_question"
    RESOLVE_OPEN_QUESTION = "resolve_open_question"
    ADD_TEMPORARY_CONCLUSION = "add_temporary_conclusion"
    RECORD_USER_CORRECTION = "record_user_correction"
    CONFIRM_DECISION = "confirm_decision"
    REQUEST_FORMALIZATION = "request_formalization"
    CANCEL_FORMALIZATION = "cancel_formalization"


def _reject_duplicate_ids(value: list[UUID]) -> list[UUID]:
    if len(value) != len(set(value)):
        raise ValueError("ID collections cannot contain duplicates.")
    return value


class DiscussionOption(DomainModel):
    """A candidate option represented within a discussion."""

    option_id: UUID
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    status: DiscussionOptionStatus = DiscussionOptionStatus.ACTIVE
    advantages: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    source_event_ids: list[UUID] = Field(default_factory=list)

    @field_validator("title", "summary", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text cannot be empty.")
        return normalized

    @field_validator("advantages", "concerns", mode="before")
    @classmethod
    def normalize_text_items(cls, value: list[str] | tuple[str, ...] | None) -> list[str]:
        return [item.strip() for item in (value or []) if item and item.strip()]

    @field_validator("source_event_ids")
    @classmethod
    def reject_duplicate_source_event_ids(cls, value: list[UUID]) -> list[UUID]:
        return _reject_duplicate_ids(value)


class DiscussionEvent(DomainModel):
    """Append-only discussion evidence; supersession is interpreted downstream."""

    id: UUID
    session_id: UUID
    project_id: UUID | None = None
    sequence_no: int = Field(ge=1)
    event_type: DiscussionEventType
    subject_key: str
    content: str
    status: DiscussionEventStatus = DiscussionEventStatus.ACTIVE
    payload: dict[str, Any] = Field(default_factory=dict)
    source_message_ids: list[UUID] = Field(default_factory=list)
    supersedes_event_id: UUID | None = None
    created_by: DiscussionActorClaim
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)

    # P27 provenance reservations only; this module does not implement P27 cases.
    source_surface: str | None = None
    source_entity_type: str | None = None
    source_entity_id: UUID | None = None
    trigger_type: str | None = None
    interaction_case_id: UUID | None = None
    external_context_pack_id: UUID | None = None

    @field_validator("source_message_ids")
    @classmethod
    def reject_duplicate_source_message_ids(cls, value: list[UUID]) -> list[UUID]:
        return _reject_duplicate_ids(value)

    @model_validator(mode="after")
    def validate_event_invariants(self) -> "DiscussionEvent":
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        if self.id == self.supersedes_event_id:
            raise ValueError("An event cannot supersede itself.")
        if self.created_by == DiscussionActorClaim.USER_EXPLICIT and self.confidence != 1.0:
            raise ValueError("user_explicit events must have confidence 1.0.")
        if self.created_by in {
            DiscussionActorClaim.USER_EXPLICIT,
            DiscussionActorClaim.USER_INFERRED,
            DiscussionActorClaim.ASSISTANT_PROPOSAL,
        } and not self.source_message_ids:
            raise ValueError("User or assistant events require source_message_ids.")
        return self


class DiscussionWorkspace(DomainModel):
    """Derived session snapshot, not the final source of project facts."""

    session_id: UUID
    project_id: UUID | None = None
    topic: str
    discussion_status: DiscussionStatus = DiscussionStatus.EXPLORING
    active_option_ids: list[UUID] = Field(default_factory=list)
    preferred_option_id: UUID | None = None
    active_constraint_ids: list[UUID] = Field(default_factory=list)
    open_question_ids: list[UUID] = Field(default_factory=list)
    temporary_conclusion_ids: list[UUID] = Field(default_factory=list)
    confirmed_decision_ids: list[UUID] = Field(default_factory=list)
    latest_user_correction_event_id: UUID | None = None
    version_no: int = Field(ge=0)
    last_event_sequence_no: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "active_option_ids",
        "active_constraint_ids",
        "open_question_ids",
        "temporary_conclusion_ids",
        "confirmed_decision_ids",
    )
    @classmethod
    def reject_duplicate_workspace_ids(cls, value: list[UUID]) -> list[UUID]:
        return _reject_duplicate_ids(value)

    @model_validator(mode="after")
    def validate_workspace_invariants(self) -> "DiscussionWorkspace":
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at.")
        if (
            self.preferred_option_id is not None
            and self.preferred_option_id not in self.active_option_ids
        ):
            raise ValueError("preferred_option_id must be active.")
        return self


class DiscussionDeltaOperation(DomainModel):
    """A side-effect-free candidate operation proposed for a discussion."""

    op: DiscussionDeltaOperationType
    target_id: UUID | None = None
    subject_key: str | None = None
    content: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    source_message_ids: list[UUID] = Field(default_factory=list)
    actor_claim: DiscussionActorClaim
    supersedes_event_id: UUID | None = None

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content cannot be empty.")
        return normalized

    @field_validator("source_message_ids")
    @classmethod
    def reject_duplicate_delta_source_message_ids(cls, value: list[UUID]) -> list[UUID]:
        return _reject_duplicate_ids(value)

    @model_validator(mode="after")
    def validate_delta_provenance(self) -> "DiscussionDeltaOperation":
        if self.actor_claim in {
            DiscussionActorClaim.USER_EXPLICIT,
            DiscussionActorClaim.USER_INFERRED,
            DiscussionActorClaim.ASSISTANT_PROPOSAL,
        } and not self.source_message_ids:
            raise ValueError("User and assistant proposals require source_message_ids.")
        return self


class DiscussionDelta(DomainModel):
    """An unpersisted collection of candidate discussion operations."""

    operations: list[DiscussionDeltaOperation] = Field(default_factory=list, max_length=50)
