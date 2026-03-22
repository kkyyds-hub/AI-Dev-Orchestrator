"""Approval domain models introduced for V3 Day10."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.deliverable import DeliverableType
from app.domain.project import ProjectStage
from app.domain.project_role import ProjectRoleCode


class ApprovalStatus(StrEnum):
    """Stable approval-request statuses used by the boss gate."""

    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class ApprovalDecisionAction(StrEnum):
    """Stable boss decision actions."""

    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"


def map_approval_action_to_status(action: ApprovalDecisionAction) -> ApprovalStatus:
    """Translate one decision action into the persisted approval status."""

    mapping = {
        ApprovalDecisionAction.APPROVE: ApprovalStatus.APPROVED,
        ApprovalDecisionAction.REJECT: ApprovalStatus.REJECTED,
        ApprovalDecisionAction.REQUEST_CHANGES: ApprovalStatus.CHANGES_REQUESTED,
    }
    return mapping[action]


class ApprovalRequest(DomainModel):
    """One explicit boss-approval request bound to a deliverable version."""

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    deliverable_id: UUID
    deliverable_version_id: UUID | None = None
    deliverable_title: str = Field(min_length=1, max_length=200)
    deliverable_type: DeliverableType
    deliverable_stage: ProjectStage
    deliverable_version_number: int = Field(ge=1)
    requester_role_code: ProjectRoleCode
    request_note: str | None = Field(default=None, max_length=1_000)
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING_APPROVAL)
    requested_at: datetime = Field(default_factory=utc_now)
    due_at: datetime = Field(
        default_factory=lambda: utc_now() + timedelta(hours=24)
    )
    decided_at: datetime | None = None
    latest_summary: str | None = Field(default=None, max_length=500)

    @field_validator("deliverable_title")
    @classmethod
    def normalize_deliverable_title(cls, value: str) -> str:
        """Trim the deliverable title snapshot and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Approval deliverable title cannot be blank.")

        return normalized_value

    @field_validator("request_note", "latest_summary")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Collapse blank optional fields into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @model_validator(mode="after")
    def validate_timestamps(self) -> "ApprovalRequest":
        """Normalize timestamps and keep the request timeline ordered."""

        object.__setattr__(self, "requested_at", ensure_utc_datetime(self.requested_at))
        object.__setattr__(self, "due_at", ensure_utc_datetime(self.due_at))
        object.__setattr__(self, "decided_at", ensure_utc_datetime(self.decided_at))

        if self.due_at < self.requested_at:
            raise ValueError("Approval due_at cannot be earlier than requested_at.")

        if self.decided_at is not None and self.decided_at < self.requested_at:
            raise ValueError("Approval decided_at cannot be earlier than requested_at.")

        return self


class ApprovalDecision(DomainModel):
    """One structured boss decision stored under an approval request."""

    id: UUID = Field(default_factory=uuid4)
    approval_id: UUID
    action: ApprovalDecisionAction
    actor_name: str = Field(default="老板", min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    comment: str | None = Field(default=None, max_length=2_000)
    highlighted_risks: list[str] = Field(default_factory=list, max_length=10)
    requested_changes: list[str] = Field(default_factory=list, max_length=10)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("actor_name", "summary")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Trim required text fields and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Approval decision text fields cannot be blank.")

        return normalized_value

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        """Collapse blank decision comments into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("highlighted_risks", "requested_changes")
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate structured decision lists."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for item in value:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_items:
                continue

            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)

        return normalized_items

    @model_validator(mode="after")
    def validate_created_at(self) -> "ApprovalDecision":
        """Normalize persisted timestamps."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        return self
