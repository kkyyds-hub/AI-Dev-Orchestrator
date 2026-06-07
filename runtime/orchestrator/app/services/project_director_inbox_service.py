"""Synthetic read-only Project Director inbox aggregation.

P7-D1 does not persist inbox items. It builds deterministic read models from
existing Project Director conversations, plan versions, tasks and latest runs.
This service intentionally has no create/update/delete methods.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import AgentMessageTable, ProjectDirectorMessageTable
from app.domain.agent_dispatch_decision import (
    P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE,
)
from app.domain.agent_message import AgentMessageType
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.project_director_message import ProjectDirectorMessageRole
from app.domain.project_director_plan_version import PlanVersionStatus
from app.domain.run import Run, RunStatus
from app.domain.task import Task, TaskStatus
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository


class InboxItemKind(StrEnum):
    NOTE = "note"
    USER_CHALLENGE_SEED = "user_challenge_seed"
    PLAN_QUESTION = "plan_question"
    DISPATCH_QUESTION = "dispatch_question"
    APPROVAL_ATTENTION = "approval_attention"
    RUN_BLOCKER = "run_blocker"
    FAILURE_RECOVERY_ATTENTION = "failure_recovery_attention"
    PROPOSAL_ATTENTION = "proposal_attention"
    GOVERNANCE_WARNING = "governance_warning"
    SYSTEM_NOTICE = "system_notice"


class InboxItemStatus(StrEnum):
    UNREAD = "unread"
    READ = "read"
    NEEDS_RESPONSE = "needs_response"
    LINKED_TO_CONVERSATION = "linked_to_conversation"
    CONVERTED_TO_CHALLENGE = "converted_to_challenge"
    CONVERTED_TO_PROPOSAL = "converted_to_proposal"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class InboxItemPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class DirectorInboxItem:
    id: UUID
    conversation_id: UUID | None
    session_id: UUID | None
    project_id: UUID | None
    source_page: str
    source_entity_type: str
    source_entity_id: UUID | None
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
    created_at: datetime = datetime.min
    updated_at: datetime = datetime.min


@dataclass(frozen=True)
class DirectorInboxResult:
    items: list[DirectorInboxItem]
    has_more: bool


class ProjectDirectorInboxService:
    """Build synthetic DirectorInbox read models from existing state."""

    def __init__(self, db_session: Session) -> None:
        self._db_session = db_session
        self._session_repo = ProjectDirectorSessionRepository(db_session)
        self._plan_repo = ProjectDirectorPlanVersionRepository(db_session)
        self._task_repo = TaskRepository(db_session)

    def list_inbox_items(
        self,
        *,
        project_id: UUID | None = None,
        kind: InboxItemKind | None = None,
        status: InboxItemStatus | None = None,
        priority: InboxItemPriority | None = None,
        limit: int = 50,
    ) -> DirectorInboxResult:
        """Return a filtered synthetic inbox list without side effects."""

        safe_limit = max(1, min(limit, 100))
        items = [
            *self._conversation_requires_user_action_items(project_id=project_id),
            *self._pending_plan_items(project_id=project_id),
            *self._task_and_run_attention_items(project_id=project_id),
            *self._dispatch_question_items(project_id=project_id),
        ]

        if kind is not None:
            items = [item for item in items if item.kind == kind]
        if status is not None:
            items = [item for item in items if item.status == status]
        if priority is not None:
            items = [item for item in items if item.priority == priority]

        items.sort(key=self._sort_key, reverse=True)
        return DirectorInboxResult(
            items=items[:safe_limit],
            has_more=len(items) > safe_limit,
        )

    def _conversation_requires_user_action_items(
        self, *, project_id: UUID | None
    ) -> list[DirectorInboxItem]:
        sessions = self._session_repo.list_all(project_id=project_id)
        items: list[DirectorInboxItem] = []

        for session_obj in sessions:
            latest = self._latest_message_row(session_obj.id)
            if latest is None:
                continue
            if latest.role != ProjectDirectorMessageRole.ASSISTANT:
                continue
            if not latest.requires_confirmation:
                continue

            timestamp = ensure_utc_datetime(latest.created_at) or utc_now()
            items.append(
                DirectorInboxItem(
                    id=self._synthetic_id(
                        "message", latest.id, InboxItemKind.PLAN_QUESTION
                    ),
                    conversation_id=session_obj.id,
                    session_id=session_obj.id,
                    project_id=session_obj.project_id,
                    source_page="workbench",
                    source_entity_type="message",
                    source_entity_id=latest.id,
                    kind=InboxItemKind.PLAN_QUESTION,
                    title="主管会话需要用户回应",
                    summary=self._truncate(latest.content, 500),
                    status=InboxItemStatus.NEEDS_RESPONSE,
                    priority=InboxItemPriority.NORMAL,
                    requires_user_action=True,
                    related_message_id=latest.id,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )

        return items

    def _pending_plan_items(
        self, *, project_id: UUID | None
    ) -> list[DirectorInboxItem]:
        plan_versions = self._plan_repo.list_by_status(
            PlanVersionStatus.PENDING_CONFIRMATION
        )
        items: list[DirectorInboxItem] = []

        for plan in plan_versions:
            if project_id is not None and plan.project_id != project_id:
                continue
            timestamp = ensure_utc_datetime(plan.updated_at) or utc_now()
            items.append(
                DirectorInboxItem(
                    id=self._synthetic_id(
                        "plan_version", plan.id, InboxItemKind.APPROVAL_ATTENTION
                    ),
                    conversation_id=plan.session_id,
                    session_id=plan.session_id,
                    project_id=plan.project_id,
                    source_page="workbench",
                    source_entity_type="plan_version",
                    source_entity_id=plan.id,
                    kind=InboxItemKind.APPROVAL_ATTENTION,
                    title=f"项目草案 v{plan.version_no} 待确认",
                    summary=self._truncate(plan.plan_summary, 500),
                    status=InboxItemStatus.NEEDS_RESPONSE,
                    priority=InboxItemPriority.HIGH,
                    requires_user_action=True,
                    related_plan_version_id=plan.id,
                    created_at=ensure_utc_datetime(plan.created_at) or timestamp,
                    updated_at=timestamp,
                )
            )

        return items

    def _task_and_run_attention_items(
        self, *, project_id: UUID | None
    ) -> list[DirectorInboxItem]:
        task_runs = self._task_repo.list_with_latest_run()
        items: list[DirectorInboxItem] = []

        for task, latest_run in task_runs:
            if project_id is not None and task.project_id != project_id:
                continue
            task_item = self._task_attention_item(task)
            if task_item is not None:
                items.append(task_item)
            run_item = self._run_attention_item(task, latest_run)
            if run_item is not None:
                items.append(run_item)

        return items

    def _dispatch_question_items(
        self, *, project_id: UUID | None
    ) -> list[DirectorInboxItem]:
        """Build read-only inbox items from P6 dispatch audit timeline messages."""

        statement = select(AgentMessageTable).where(
            AgentMessageTable.message_type == AgentMessageType.TIMELINE
        )
        if project_id is not None:
            statement = statement.where(AgentMessageTable.project_id == project_id)
        statement = statement.order_by(
            AgentMessageTable.created_at.desc(),
            AgentMessageTable.sequence_no.desc(),
        )

        rows = self._db_session.execute(statement).scalars().all()
        items: list[DirectorInboxItem] = []
        seen_message_ids: set[UUID] = set()

        for message in rows:
            if message.id in seen_message_ids:
                continue
            detail = self._parse_json_object(message.content_detail)
            if not self._is_dispatch_decision_message(message, detail):
                continue

            decision = detail.get("decision")
            if not isinstance(decision, dict):
                decision = {}
            recommended_agent = self._normalized_detail_text(
                decision.get("recommended_agent")
                or detail.get("recommended_agent")
            ).lower()
            dispatch_status = self._normalized_detail_text(
                decision.get("dispatch_status")
                or detail.get("dispatch_status")
                or message.state_to
            ).lower()
            priority = self._dispatch_priority(
                recommended_agent=recommended_agent,
                dispatch_status=dispatch_status,
            )
            requires_user_action = recommended_agent in {"user", "blocked"}
            summary = self._dispatch_summary(message, decision)
            timestamp = ensure_utc_datetime(message.created_at) or utc_now()

            items.append(
                DirectorInboxItem(
                    id=self._synthetic_id(
                        "agent_message", message.id, InboxItemKind.DISPATCH_QUESTION
                    ),
                    conversation_id=None,
                    session_id=None,
                    project_id=message.project_id,
                    source_page="worker_timeline",
                    source_entity_type="agent_message",
                    source_entity_id=message.id,
                    kind=InboxItemKind.DISPATCH_QUESTION,
                    title="P6 调度建议需要主管关注",
                    summary=self._truncate(summary, 500),
                    status=InboxItemStatus.NEEDS_RESPONSE,
                    priority=priority,
                    requires_user_action=requires_user_action,
                    related_task_id=message.task_id,
                    related_run_id=message.run_id,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
            seen_message_ids.add(message.id)

        return items

    def _task_attention_item(self, task: Task) -> DirectorInboxItem | None:
        if task.status not in {
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.WAITING_HUMAN,
        }:
            return None

        if task.status == TaskStatus.FAILED:
            kind = InboxItemKind.FAILURE_RECOVERY_ATTENTION
            priority = InboxItemPriority.CRITICAL
            title = "任务失败，需要主管关注"
        elif task.status == TaskStatus.BLOCKED:
            kind = InboxItemKind.RUN_BLOCKER
            priority = InboxItemPriority.CRITICAL
            title = "任务阻塞，需要主管关注"
        else:
            kind = InboxItemKind.RUN_BLOCKER
            priority = InboxItemPriority.HIGH
            title = "任务等待人工处理"

        timestamp = ensure_utc_datetime(task.updated_at) or utc_now()
        return DirectorInboxItem(
            id=self._synthetic_id("task", task.id, kind),
            conversation_id=None,
            session_id=None,
            project_id=task.project_id,
            source_page="task_detail",
            source_entity_type="task",
            source_entity_id=task.id,
            kind=kind,
            title=title,
            summary=self._truncate(f"{task.title}: {task.input_summary}", 500),
            status=InboxItemStatus.NEEDS_RESPONSE,
            priority=priority,
            requires_user_action=True,
            related_task_id=task.id,
            created_at=ensure_utc_datetime(task.created_at) or timestamp,
            updated_at=timestamp,
        )

    def _run_attention_item(
        self, task: Task, latest_run: Run | None
    ) -> DirectorInboxItem | None:
        if latest_run is None:
            return None
        if latest_run.status not in {RunStatus.FAILED, RunStatus.CANCELLED}:
            return None

        timestamp = (
            ensure_utc_datetime(latest_run.finished_at)
            or ensure_utc_datetime(latest_run.created_at)
            or utc_now()
        )
        return DirectorInboxItem(
            id=self._synthetic_id(
                "run", latest_run.id, InboxItemKind.FAILURE_RECOVERY_ATTENTION
            ),
            conversation_id=None,
            session_id=None,
            project_id=task.project_id,
            source_page="run_detail",
            source_entity_type="run",
            source_entity_id=latest_run.id,
            kind=InboxItemKind.FAILURE_RECOVERY_ATTENTION,
            title="运行失败或取消，需要失败回流关注",
            summary=self._truncate(
                latest_run.result_summary
                or latest_run.route_reason
                or f"任务 {task.title} 的最近运行状态为 {latest_run.status.value}",
                500,
            ),
            status=InboxItemStatus.NEEDS_RESPONSE,
            priority=InboxItemPriority.CRITICAL,
            requires_user_action=True,
            related_task_id=task.id,
            related_run_id=latest_run.id,
            created_at=ensure_utc_datetime(latest_run.created_at) or timestamp,
            updated_at=timestamp,
        )

    def _latest_message_row(
        self, session_id: UUID
    ) -> ProjectDirectorMessageTable | None:
        statement = (
            select(ProjectDirectorMessageTable)
            .where(ProjectDirectorMessageTable.session_id == session_id)
            .order_by(
                ProjectDirectorMessageTable.sequence_no.desc(),
                ProjectDirectorMessageTable.created_at.desc(),
            )
            .limit(1)
        )
        return self._db_session.execute(statement).scalars().first()

    @staticmethod
    def _synthetic_id(
        source_entity_type: str,
        source_entity_id: UUID,
        kind: InboxItemKind,
    ) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"project-director-inbox:{source_entity_type}:{source_entity_id}:{kind.value}",
        )

    @staticmethod
    def _parse_json_object(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    @staticmethod
    def _is_dispatch_decision_message(
        message: AgentMessageTable, detail: dict[str, Any]
    ) -> bool:
        if detail.get("p6_stage") == "P6-D":
            return True
        if detail.get("event_type") == P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE:
            return True
        if message.event_type == P6_AGENT_DISPATCH_DECISION_AUDIT_EVENT_TYPE:
            return True
        return "P6 调度建议" in (message.content_summary or "")

    @classmethod
    def _dispatch_priority(
        cls, *, recommended_agent: str, dispatch_status: str
    ) -> InboxItemPriority:
        if recommended_agent == "blocked" or dispatch_status in {
            "blocked",
            "not_applicable",
        }:
            return InboxItemPriority.CRITICAL
        if recommended_agent == "user" or dispatch_status in {
            "needs_user_decision",
            "needs_human",
            "waiting_human",
        }:
            return InboxItemPriority.HIGH
        return InboxItemPriority.NORMAL

    @classmethod
    def _dispatch_summary(
        cls, message: AgentMessageTable, decision: dict[str, Any]
    ) -> str:
        summary = cls._normalized_detail_text(message.content_summary)
        if summary:
            return summary
        instruction_draft = cls._normalized_detail_text(decision.get("instruction_draft"))
        if instruction_draft:
            return instruction_draft
        reason = cls._normalized_detail_text(decision.get("dispatch_reason_cn"))
        if reason:
            return reason
        return "P6 调度建议需要主管关注；当前仅为只读 readback，未派发、未重试。"

    @staticmethod
    def _normalized_detail_text(value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return " ".join(value.split())

    @staticmethod
    def _sort_key(item: DirectorInboxItem) -> tuple[int, datetime, str]:
        return (
            {
                InboxItemPriority.LOW: 0,
                InboxItemPriority.NORMAL: 1,
                InboxItemPriority.HIGH: 2,
                InboxItemPriority.CRITICAL: 3,
            }[item.priority],
            item.updated_at,
            item.id.hex,
        )

    @staticmethod
    def _truncate(value: str, limit: int) -> str:
        normalized = " ".join((value or "").split())
        if len(normalized) <= limit:
            return normalized
        return normalized[:limit]
