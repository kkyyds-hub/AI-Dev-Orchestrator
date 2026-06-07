"""Read-only Project Director conversation aggregation.

P7-C1 treats ``ProjectDirectorSession.id`` as ``conversation_id`` and builds
conversation list/detail/timeline views from existing Project Director tables.
This service intentionally has no create/update/delete methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db_tables import (
    ProjectDirectorMessageTable,
)
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
)
from app.domain.project_director_plan_version import ProjectDirectorPlanVersion
from app.domain.project_director_session import ProjectDirectorSession
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.project_director_task_creation_repository import (
    ProjectDirectorTaskCreationRecordRepository,
)


class ConversationKind(StrEnum):
    """P7 conversation kind read model."""

    PROJECT_ONBOARDING = "project_onboarding"
    GENERAL_DISCUSSION = "general_discussion"
    PLAN_REVIEW = "plan_review"
    FOLLOW_UP = "follow_up"


class ConversationStatus(StrEnum):
    """P7 conversation status read model."""

    ACTIVE = "active"
    IDLE = "idle"
    AWAITING_USER = "awaiting_user"
    ARCHIVED = "archived"
    COMPLETED = "completed"


class ConversationTimelineItemKind(StrEnum):
    """Supported read-only conversation timeline item kinds for P7-C1."""

    MESSAGE = "message"
    PLAN_DRAFT = "plan_draft"
    PLAN_CONFIRMED = "plan_confirmed"
    TASK_CREATED = "task_created"


@dataclass(frozen=True)
class ConversationListItem:
    """Lightweight conversation row for list views."""

    conversation_id: UUID
    project_id: UUID | None
    title: str
    kind: ConversationKind
    status: ConversationStatus
    session_status: str
    last_message_preview: str
    last_message_at: datetime | None
    message_count: int
    pending_challenge_count: int
    pending_proposal_count: int
    requires_user_action: bool
    owner_scope: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ConversationDetail:
    """Full conversation read model."""

    conversation: ConversationListItem
    session: ProjectDirectorSession
    recent_messages: list[ProjectDirectorMessage] = field(default_factory=list)
    latest_plan_version: ProjectDirectorPlanVersion | None = None
    task_creation: object | None = None


@dataclass(frozen=True)
class ConversationTimelineItem:
    """One read-only conversation timeline event."""

    timestamp: datetime
    kind: ConversationTimelineItemKind
    summary_cn: str
    related_message_id: UUID | None = None
    related_plan_version_id: UUID | None = None
    related_task_id: UUID | None = None
    related_proposal_id: UUID | None = None


@dataclass(frozen=True)
class ConversationListResult:
    """Paginated conversation list result."""

    conversations: list[ConversationListItem]
    has_more: bool


@dataclass(frozen=True)
class _MessageStats:
    message_count: int
    last_message_id: UUID | None
    last_message_content: str
    last_message_at: datetime | None
    last_message_role: ProjectDirectorMessageRole | None
    last_message_requires_confirmation: bool


class ProjectDirectorConversationService:
    """Build read-only conversation views from existing Project Director data."""

    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._session_repo = ProjectDirectorSessionRepository(db_session)
        self._message_repo = ProjectDirectorMessageRepository(db_session)
        self._plan_repo = ProjectDirectorPlanVersionRepository(db_session)
        self._task_creation_repo = ProjectDirectorTaskCreationRecordRepository(
            db_session
        )

    def list_conversations(
        self,
        *,
        project_id: UUID | None = None,
        status: ConversationStatus | None = None,
        kind: ConversationKind | None = None,
        limit: int = 20,
        before: UUID | None = None,
    ) -> ConversationListResult:
        """Return conversations ordered by latest activity descending."""

        safe_limit = max(1, min(limit, 100))
        session_objects = self._session_repo.list_all(project_id=project_id)
        session_ids = [session_obj.id for session_obj in session_objects]
        message_stats = self._message_stats_by_session_id(session_ids)

        candidates = [
            self._build_list_item(
                session_obj=session_obj,
                stats=message_stats.get(
                    session_obj.id, self._empty_message_stats()
                ),
            )
            for session_obj in session_objects
        ]

        if kind is not None:
            candidates = [item for item in candidates if item.kind == kind]
        if status is not None:
            candidates = [item for item in candidates if item.status == status]

        candidates.sort(key=self._list_sort_key, reverse=True)
        if before is not None:
            cursor_index = next(
                (
                    index
                    for index, item in enumerate(candidates)
                    if item.conversation_id == before
                ),
                None,
            )
            if cursor_index is None:
                raise ValueError(
                    f"Project Director conversation cursor {before} not found"
                )
            candidates = candidates[cursor_index + 1 :]

        return ConversationListResult(
            conversations=candidates[:safe_limit],
            has_more=len(candidates) > safe_limit,
        )

    def get_conversation(
        self,
        *,
        conversation_id: UUID,
        project_id: UUID | None = None,
        recent_message_limit: int = 20,
    ) -> ConversationDetail | None:
        """Return one conversation detail without side effects."""

        session_obj = self._session_repo.get_by_id(conversation_id)
        if session_obj is None:
            return None
        if project_id is not None and session_obj.project_id != project_id:
            raise ValueError(
                "Selected Project Director conversation does not match the requested project"
            )

        messages, _has_more = self._message_repo.list_by_session_id(
            session_id=conversation_id,
            limit=max(1, min(recent_message_limit, 200)),
        )
        stats = self._message_stats_by_session_id([conversation_id]).get(
            conversation_id, self._empty_message_stats()
        )
        latest_plan_version = self._latest_plan_version(conversation_id)
        task_creation = (
            self._task_creation_repo.get_by_plan_version_id(latest_plan_version.id)
            if latest_plan_version is not None
            else None
        )
        return ConversationDetail(
            conversation=self._build_list_item(session_obj=session_obj, stats=stats),
            session=session_obj,
            recent_messages=messages,
            latest_plan_version=latest_plan_version,
            task_creation=task_creation,
        )

    def get_timeline(
        self,
        *,
        conversation_id: UUID,
        project_id: UUID | None = None,
    ) -> list[ConversationTimelineItem] | None:
        """Return message/plan/task timeline items for one conversation."""

        detail = self.get_conversation(
            conversation_id=conversation_id,
            project_id=project_id,
            recent_message_limit=200,
        )
        if detail is None:
            return None

        items: list[ConversationTimelineItem] = []
        for message in detail.recent_messages:
            items.append(
                ConversationTimelineItem(
                    timestamp=message.created_at,
                    kind=ConversationTimelineItemKind.MESSAGE,
                    summary_cn=self._truncate(
                        f"{message.role.value}: {message.content}",
                        200,
                    ),
                    related_message_id=message.id,
                    related_plan_version_id=message.related_plan_version_id,
                    related_task_id=message.related_task_id,
                )
            )

        if detail.latest_plan_version is not None:
            plan = detail.latest_plan_version
            items.append(
                ConversationTimelineItem(
                    timestamp=ensure_utc_datetime(plan.created_at) or utc_now(),
                    kind=ConversationTimelineItemKind.PLAN_DRAFT,
                    summary_cn=self._truncate(
                        f"生成计划草案 v{plan.version_no}: {plan.plan_summary}",
                        200,
                    ),
                    related_plan_version_id=plan.id,
                )
            )
            if plan.confirmed_at is not None:
                items.append(
                    ConversationTimelineItem(
                        timestamp=ensure_utc_datetime(plan.confirmed_at) or utc_now(),
                        kind=ConversationTimelineItemKind.PLAN_CONFIRMED,
                        summary_cn=f"计划草案 v{plan.version_no} 已确认。",
                        related_plan_version_id=plan.id,
                    )
                )

        if detail.task_creation is not None:
            record = detail.task_creation
            items.append(
                ConversationTimelineItem(
                    timestamp=ensure_utc_datetime(record.created_at) or utc_now(),
                    kind=ConversationTimelineItemKind.TASK_CREATED,
                    summary_cn=f"已创建正式任务队列，任务数 {record.task_count}。",
                    related_plan_version_id=record.plan_version_id,
                    related_task_id=record.task_ids[0] if record.task_ids else None,
                )
            )

        items.sort(key=lambda item: item.timestamp)
        return items

    def _build_list_item(
        self,
        *,
        session_obj: ProjectDirectorSession,
        stats: _MessageStats,
    ) -> ConversationListItem:
        latest_plan_version = self._latest_plan_version(session_obj.id)
        task_creation = (
            self._task_creation_repo.get_by_plan_version_id(latest_plan_version.id)
            if latest_plan_version is not None
            else None
        )
        conversation_status = self._conversation_status(
            session_obj=session_obj,
            stats=stats,
            has_task_creation=task_creation is not None,
        )
        last_message_at = ensure_utc_datetime(stats.last_message_at)
        session_updated_at = ensure_utc_datetime(session_obj.updated_at) or utc_now()
        updated_at = (
            max(session_updated_at, last_message_at)
            if last_message_at is not None
            else session_updated_at
        )
        return ConversationListItem(
            conversation_id=session_obj.id,
            project_id=session_obj.project_id,
            title=self._truncate(session_obj.goal_text.strip() or "未命名主管会话", 80),
            kind=self._conversation_kind(
                latest_plan_version=latest_plan_version,
                task_creation=task_creation,
            ),
            status=conversation_status,
            session_status=session_obj.status.value,
            last_message_preview=self._truncate(stats.last_message_content, 120),
            last_message_at=last_message_at,
            message_count=stats.message_count,
            pending_challenge_count=0,
            pending_proposal_count=0,
            requires_user_action=conversation_status
            == ConversationStatus.AWAITING_USER,
            owner_scope="project" if session_obj.project_id is not None else "user",
            created_at=ensure_utc_datetime(session_obj.created_at) or utc_now(),
            updated_at=updated_at,
        )

    @staticmethod
    def _conversation_kind(
        *,
        latest_plan_version: ProjectDirectorPlanVersion | None,
        task_creation: object | None,
    ) -> ConversationKind:
        if task_creation is not None:
            return ConversationKind.FOLLOW_UP
        if latest_plan_version is not None:
            return ConversationKind.PLAN_REVIEW
        return ConversationKind.PROJECT_ONBOARDING

    @staticmethod
    def _conversation_status(
        *,
        session_obj: ProjectDirectorSession,
        stats: _MessageStats,
        has_task_creation: bool,
    ) -> ConversationStatus:
        if session_obj.status.value == "confirmed" and has_task_creation:
            return ConversationStatus.COMPLETED
        if (
            stats.last_message_role == ProjectDirectorMessageRole.ASSISTANT
            and stats.last_message_requires_confirmation
        ):
            return ConversationStatus.AWAITING_USER
        if stats.last_message_at is not None:
            last_message_at = ensure_utc_datetime(stats.last_message_at) or utc_now()
            if utc_now() - last_message_at <= timedelta(minutes=30):
                return ConversationStatus.ACTIVE
        return ConversationStatus.IDLE

    def _latest_plan_version(
        self, session_id: UUID
    ) -> ProjectDirectorPlanVersion | None:
        versions = self._plan_repo.list_by_session_id(session_id)
        return versions[0] if versions else None

    def _message_stats_by_session_id(
        self, session_ids: list[UUID]
    ) -> dict[UUID, _MessageStats]:
        if not session_ids:
            return {}

        count_statement = (
            select(
                ProjectDirectorMessageTable.session_id,
                func.count(ProjectDirectorMessageTable.id),
            )
            .where(ProjectDirectorMessageTable.session_id.in_(session_ids))
            .group_by(ProjectDirectorMessageTable.session_id)
        )
        counts = {
            session_id: int(count)
            for session_id, count in self._db_session.execute(count_statement).all()
        }

        stats: dict[UUID, _MessageStats] = {}
        for session_id in session_ids:
            latest_statement = (
                select(ProjectDirectorMessageTable)
                .where(ProjectDirectorMessageTable.session_id == session_id)
                .order_by(
                    ProjectDirectorMessageTable.sequence_no.desc(),
                    ProjectDirectorMessageTable.created_at.desc(),
                )
                .limit(1)
            )
            latest = self._db_session.execute(latest_statement).scalars().first()
            if latest is None:
                stats[session_id] = self._empty_message_stats()
                continue
            stats[session_id] = _MessageStats(
                message_count=counts.get(session_id, 0),
                last_message_id=latest.id,
                last_message_content=latest.content,
                last_message_at=ensure_utc_datetime(latest.created_at),
                last_message_role=ProjectDirectorMessageRole(latest.role),
                last_message_requires_confirmation=latest.requires_confirmation,
            )
        return stats

    @staticmethod
    def _stats_from_messages(messages: list[ProjectDirectorMessage]) -> _MessageStats:
        if not messages:
            return ProjectDirectorConversationService._empty_message_stats()
        latest = max(messages, key=lambda message: message.sequence_no)
        return _MessageStats(
            message_count=len(messages),
            last_message_id=latest.id,
            last_message_content=latest.content,
            last_message_at=latest.created_at,
            last_message_role=latest.role,
            last_message_requires_confirmation=latest.requires_confirmation,
        )

    @staticmethod
    def _empty_message_stats() -> _MessageStats:
        return _MessageStats(
            message_count=0,
            last_message_id=None,
            last_message_content="",
            last_message_at=None,
            last_message_role=None,
            last_message_requires_confirmation=False,
        )

    @staticmethod
    def _truncate(value: str, limit: int) -> str:
        normalized = " ".join((value or "").split())
        if len(normalized) <= limit:
            return normalized
        return normalized[:limit]

    @staticmethod
    def _list_sort_key(item: ConversationListItem) -> tuple[datetime, datetime, str]:
        """Stable ConversationList cursor order.

        P7-C freezes the default ConversationList order as latest message activity
        descending. Sessions without messages still remain visible by falling back
        to the session-derived updated_at value.
        """

        activity_at = item.last_message_at or item.updated_at
        return (activity_at, item.created_at, item.conversation_id.hex)
