"""Durable, session-bound formalization proposals."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel, utc_now
from app.domain.project_director_conversation_intelligence import (
    FormalizationChange,
    FormalizationProposal,
    FormalizationTarget,
)


class FormalizationProposalStatus(StrEnum):
    """Lifecycle states for an immutable proposed formalization."""

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"


class ProjectDirectorFormalizationProposal(DomainModel):
    """A persisted Provider proposal bound to its exact assistant turn."""

    proposal_id: UUID
    session_id: UUID
    project_id: UUID | None = None
    assistant_message_id: UUID
    workspace_version: int = Field(ge=1)
    target: FormalizationTarget
    summary: str = Field(min_length=1)
    changes: list[FormalizationChange] = Field(min_length=1)
    source_message_ids: list[UUID] = Field(min_length=1)
    source_event_ids: list[UUID] = Field(min_length=1)
    risk_summary: str = Field(min_length=1)
    requires_confirmation: Literal[True] = True
    status: FormalizationProposalStatus = FormalizationProposalStatus.PROPOSED
    confirmed_plan_version_id: UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    confirmed_at: datetime | None = None

    @field_validator("source_message_ids", "source_event_ids")
    @classmethod
    def reject_duplicate_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Formalization proposal source IDs cannot contain duplicates.")
        return value

    def to_response_proposal(self) -> FormalizationProposal:
        """Expose only the Provider proposal contract to API consumers."""

        return FormalizationProposal(
            proposal_id=self.proposal_id,
            target=self.target,
            workspace_version=self.workspace_version,
            summary=self.summary,
            changes=self.changes,
            source_message_ids=self.source_message_ids,
            risk_summary=self.risk_summary,
            requires_confirmation=True,
            status="proposed",
        )
