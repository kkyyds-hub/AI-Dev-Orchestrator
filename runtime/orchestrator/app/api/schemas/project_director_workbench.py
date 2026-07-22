"""Project Director workbench read-model response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.project_director_plan_version import PlanVersionStatus
from app.domain.project_director_discussion import DiscussionWorkspace
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.services.project_director_conversation_service import (
    ConversationKind,
    ConversationListItem,
    ConversationStatus,
    ConversationTimelineItem,
)
from app.services.project_director_inbox_service import (
    DirectorInboxItem,
    InboxItemKind,
    InboxItemPriority,
    InboxItemStatus,
)


class TaskCreationResponse(BaseModel):
    plan_version_id: UUID
    session_id: UUID
    project_id: UUID
    project_name: str | None = None
    created_task_ids: list[UUID] = Field(default_factory=list)
    task_count: int = Field(default=0)
    status: str
    already_created: bool = False
    next_action: str
    warnings: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    gate_conclusion: str


class DiscussionWorkspaceResponse(BaseModel):
    """Read-only discussion workspace projection for the workbench."""

    session_id: UUID
    project_id: UUID | None
    topic: str
    discussion_status: str
    active_option_ids: list[UUID] = Field(default_factory=list)
    preferred_option_id: UUID | None = None
    active_constraint_ids: list[UUID] = Field(default_factory=list)
    open_question_ids: list[UUID] = Field(default_factory=list)
    temporary_conclusion_ids: list[UUID] = Field(default_factory=list)
    confirmed_decision_ids: list[UUID] = Field(default_factory=list)
    latest_user_correction_event_id: UUID | None = None
    version_no: int
    last_event_sequence_no: int
    created_at: str
    updated_at: str

    @classmethod
    def from_domain(
        cls, workspace: DiscussionWorkspace
    ) -> "DiscussionWorkspaceResponse":
        return cls(
            session_id=workspace.session_id,
            project_id=workspace.project_id,
            topic=workspace.topic,
            discussion_status=workspace.discussion_status.value,
            active_option_ids=workspace.active_option_ids,
            preferred_option_id=workspace.preferred_option_id,
            active_constraint_ids=workspace.active_constraint_ids,
            open_question_ids=workspace.open_question_ids,
            temporary_conclusion_ids=workspace.temporary_conclusion_ids,
            confirmed_decision_ids=workspace.confirmed_decision_ids,
            latest_user_correction_event_id=workspace.latest_user_correction_event_id,
            version_no=workspace.version_no,
            last_event_sequence_no=workspace.last_event_sequence_no,
            created_at=workspace.created_at.isoformat(),
            updated_at=workspace.updated_at.isoformat(),
        )


class ConversationListItemResponse(BaseModel):
    conversation_id: UUID
    project_id: UUID | None = None
    title: str
    kind: ConversationKind
    status: ConversationStatus
    session_status: str
    last_message_preview: str
    last_message_at: str | None = None
    message_count: int
    pending_challenge_count: int
    pending_proposal_count: int
    requires_user_action: bool
    owner_scope: str
    created_at: str
    updated_at: str

    @classmethod
    def from_domain(
        cls, item: ConversationListItem
    ) -> "ConversationListItemResponse":
        return cls(
            conversation_id=item.conversation_id,
            project_id=item.project_id,
            title=item.title,
            kind=item.kind,
            status=item.status,
            session_status=item.session_status,
            last_message_preview=item.last_message_preview,
            last_message_at=(
                item.last_message_at.isoformat()
                if item.last_message_at is not None
                else None
            ),
            message_count=item.message_count,
            pending_challenge_count=item.pending_challenge_count,
            pending_proposal_count=item.pending_proposal_count,
            requires_user_action=item.requires_user_action,
            owner_scope=item.owner_scope,
            created_at=item.created_at.isoformat(),
            updated_at=item.updated_at.isoformat(),
        )


class ConversationListResponse(BaseModel):
    conversations: list[ConversationListItemResponse] = Field(default_factory=list)
    has_more: bool = False
    source: str = Field(default="project_director_sessions_read_model")


class ConversationTaskCreationResponse(BaseModel):
    id: UUID
    plan_version_id: UUID
    session_id: UUID
    project_id: UUID
    version_no: int
    source_type: str
    created_task_ids: list[UUID] = Field(default_factory=list)
    task_count: int
    created_at: str

    @classmethod
    def from_record(cls, record) -> "ConversationTaskCreationResponse":
        return cls(
            id=record.id,
            plan_version_id=record.plan_version_id,
            session_id=record.session_id,
            project_id=record.project_id,
            version_no=record.version_no,
            source_type=record.source_type,
            created_task_ids=record.task_ids,
            task_count=record.task_count,
            created_at=record.created_at.isoformat(),
        )


class ConversationTimelineItemResponse(BaseModel):
    timestamp: str
    kind: str
    summary_cn: str
    related_message_id: UUID | None = None
    related_plan_version_id: UUID | None = None
    related_task_id: UUID | None = None
    related_proposal_id: UUID | None = None

    @classmethod
    def from_domain(
        cls, item: ConversationTimelineItem
    ) -> "ConversationTimelineItemResponse":
        return cls(
            timestamp=item.timestamp.isoformat(),
            kind=item.kind.value,
            summary_cn=item.summary_cn,
            related_message_id=item.related_message_id,
            related_plan_version_id=item.related_plan_version_id,
            related_task_id=item.related_task_id,
            related_proposal_id=item.related_proposal_id,
        )


class ConversationTimelineResponse(BaseModel):
    conversation_id: UUID
    items: list[ConversationTimelineItemResponse] = Field(default_factory=list)
    source: str = Field(default="project_director_conversation_timeline_read_model")


class DirectorInboxItemResponse(BaseModel):
    id: UUID
    conversation_id: UUID | None = None
    session_id: UUID | None = None
    project_id: UUID | None = None
    source_page: str
    source_entity_type: str
    source_entity_id: UUID | None = None
    kind: InboxItemKind
    title: str
    summary: str
    status: InboxItemStatus
    priority: InboxItemPriority
    requires_user_action: bool
    related_message_id: UUID | None = None
    related_plan_version_id: UUID | None = None
    related_task_id: UUID | None = None
    related_run_id: UUID | None = None
    related_approval_id: UUID | None = None
    related_dispatch_decision_id: UUID | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_domain(cls, item: DirectorInboxItem) -> "DirectorInboxItemResponse":
        return cls(
            id=item.id,
            conversation_id=item.conversation_id,
            session_id=item.session_id,
            project_id=item.project_id,
            source_page=item.source_page,
            source_entity_type=item.source_entity_type,
            source_entity_id=item.source_entity_id,
            kind=item.kind,
            title=item.title,
            summary=item.summary,
            status=item.status,
            priority=item.priority,
            requires_user_action=item.requires_user_action,
            related_message_id=item.related_message_id,
            related_plan_version_id=item.related_plan_version_id,
            related_task_id=item.related_task_id,
            related_run_id=item.related_run_id,
            related_approval_id=item.related_approval_id,
            related_dispatch_decision_id=item.related_dispatch_decision_id,
            created_at=item.created_at.isoformat(),
            updated_at=item.updated_at.isoformat(),
        )


class DirectorInboxResponse(BaseModel):
    items: list[DirectorInboxItemResponse] = Field(default_factory=list)
    has_more: bool = False
    source: str = Field(default="synthetic_project_director_inbox_read_model")


class WorkbenchResumableSessionSummary(BaseModel):
    session_id: UUID
    project_id: UUID | None = None
    project_name: str | None = None
    status: ProjectDirectorSessionStatus
    goal_text: str
    goal_summary: str = ""
    updated_at: str
    plan_version_id: UUID | None = None
    plan_version_status: PlanVersionStatus | None = None
    source: str = Field(default="backend_recent_session")
    next_action: str


class WorkbenchResumableSessionsResponse(BaseModel):
    sessions: list[WorkbenchResumableSessionSummary] = Field(default_factory=list)
    source: str = Field(default="project_director_session_repository")
