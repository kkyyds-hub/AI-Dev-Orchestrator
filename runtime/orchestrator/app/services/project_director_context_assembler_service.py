"""Read-only Project Director context assembler service.

P7-E3 assembles deterministic context sections from existing Project Director
read-only services. It does not call providers, persist messages, create
sessions/tasks/runs, start workers or external tools, or modify repositories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.project_director_conversation_router import (
    ConversationIntent,
    RouteDecision,
)
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
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_context_builder_service import (
    ProjectDirectorContextBuilderService,
    ProjectDirectorConversationContext,
)
from app.services.project_director_conversation_service import (
    ConversationListItem,
    ProjectDirectorConversationService,
)
from app.services.project_director_inbox_service import (
    DirectorInboxItem,
    InboxItemKind,
    ProjectDirectorInboxService,
)


class DirectorContextAssemblerNotFoundError(ValueError):
    """Raised when a requested Project Director conversation cannot be read."""


@dataclass(frozen=True, slots=True)
class DirectorContextSection:
    """One deterministic context section selected by the route scope."""

    key: str
    label: str
    included: bool
    item_count: int
    summary: str
    source: str


@dataclass(frozen=True, slots=True)
class DirectorContextAssembly:
    """Assembled read-only context package for a routed conversation turn."""

    conversation_id: UUID
    session_id: UUID
    project_id: UUID | None
    route_intent: ConversationIntent
    source: str = "project_director_context_assembler"
    summary: str = ""
    sections: list[DirectorContextSection] = field(default_factory=list)
    recent_messages_count: int = 0
    inbox_attention_count: int = 0
    has_plan: bool = False
    has_task_creation: bool = False
    forbidden_actions: list[str] = field(default_factory=list)
    safe_next_actions: list[str] = field(default_factory=list)


_FORBIDDEN_ACTIONS_FALLBACK = [
    "不会自动执行任务",
    "不会自动创建任务",
    "不会修改仓库",
    "不会启动外部工具",
    "不会直接应用草案修改",
]

_SAFE_NEXT_ACTIONS_FALLBACK = ["继续提问", "要求解释原因"]

_TECHNICAL_WORDS = (
    "provider",
    "worker",
    "executor",
    "runtime",
    "API",
    "payload",
    "Git",
    "dispatch_question",
    "session_id",
    "project_id",
    "synthetic",
    "read model",
)

_EXECUTION_ACTION_WORDS = (
    "启动执行",
    "提交代码",
    "推送",
    "合并",
    "派发 Codex",
)


class DirectorContextAssemblerService:
    """Assemble route-scoped read-only context sections for Project Director."""

    def __init__(self, db_session: Session) -> None:
        session_repository = ProjectDirectorSessionRepository(db_session)
        message_repository = ProjectDirectorMessageRepository(db_session)
        self._context_builder = ProjectDirectorContextBuilderService(
            session_repository=session_repository,
            message_repository=message_repository,
            plan_version_repository=ProjectDirectorPlanVersionRepository(db_session),
            task_creation_repository=ProjectDirectorTaskCreationRecordRepository(
                db_session
            ),
            project_repository=ProjectRepository(db_session),
            task_repository=TaskRepository(db_session),
        )
        self._conversation_service = ProjectDirectorConversationService(db_session)
        self._inbox_service = ProjectDirectorInboxService(db_session)

    def assemble(
        self,
        *,
        conversation_id: UUID,
        route_decision: RouteDecision,
        project_id: UUID | None = None,
        recent_message_limit: int = 10,
        inbox_limit: int = 10,
    ) -> DirectorContextAssembly:
        """Return a deterministic read-only context assembly."""

        safe_recent_limit = self._clamp(recent_message_limit, lower=1, upper=50)
        safe_inbox_limit = self._clamp(inbox_limit, lower=1, upper=100)

        detail = self._conversation_service.get_conversation(
            conversation_id=conversation_id,
            project_id=project_id,
            recent_message_limit=safe_recent_limit,
        )
        if detail is None:
            raise DirectorContextAssemblerNotFoundError(
                f"Project Director conversation {conversation_id} not found"
            )

        context = self._context_builder.build_context(
            session_id=conversation_id,
            recent_message_limit=safe_recent_limit,
        )
        effective_project_id = context.project_id
        inbox_items = self._list_inbox_items(
            include=route_decision.context_scope.include_inbox,
            project_id=effective_project_id,
            limit=safe_inbox_limit,
        )
        dispatch_items = self._list_dispatch_items(
            include=route_decision.context_scope.include_dispatch_attention,
            project_id=effective_project_id,
            limit=safe_inbox_limit,
        )
        other_conversations = self._list_other_conversations(
            include=route_decision.context_scope.include_conversation_list,
            project_id=effective_project_id,
            current_conversation_id=conversation_id,
        )

        forbidden_actions = self._safe_user_actions(
            route_decision.safety_policy.forbidden_actions,
            fallback=_FORBIDDEN_ACTIONS_FALLBACK,
            remove_execution_words=False,
        )
        safe_next_actions = self._safe_user_actions(
            route_decision.safety_policy.safe_next_actions,
            fallback=_SAFE_NEXT_ACTIONS_FALLBACK,
            remove_execution_words=True,
        )

        sections = self._build_sections(
            context=context,
            route_decision=route_decision,
            inbox_items=inbox_items,
            dispatch_items=dispatch_items,
            other_conversations=other_conversations,
            forbidden_actions=forbidden_actions,
        )
        recent_messages_count = self._section_count(sections, "recent_messages")
        inbox_attention_count = self._section_count(sections, "inbox_attention")
        has_plan = self._section_count(sections, "latest_plan") > 0
        has_task_creation = self._section_count(sections, "task_creation") > 0
        warning = self._safe_warning(route_decision.safety_policy.user_visible_warning)

        return DirectorContextAssembly(
            conversation_id=conversation_id,
            session_id=context.session_id,
            project_id=context.project_id,
            route_intent=route_decision.intent,
            summary=self._build_summary(
                recent_messages_count=recent_messages_count,
                has_plan=has_plan,
                inbox_attention_count=inbox_attention_count,
                warning=warning,
            ),
            sections=sections,
            recent_messages_count=recent_messages_count,
            inbox_attention_count=inbox_attention_count,
            has_plan=has_plan,
            has_task_creation=has_task_creation,
            forbidden_actions=forbidden_actions,
            safe_next_actions=safe_next_actions,
        )

    @classmethod
    def _build_sections(
        cls,
        *,
        context: ProjectDirectorConversationContext,
        route_decision: RouteDecision,
        inbox_items: list[DirectorInboxItem],
        dispatch_items: list[DirectorInboxItem],
        other_conversations: list[ConversationListItem],
        forbidden_actions: list[str],
    ) -> list[DirectorContextSection]:
        scope = route_decision.context_scope
        return [
            cls._section(
                key="conversation",
                label="当前主管会话",
                included=scope.include_session,
                item_count=1 if scope.include_session else 0,
                summary=(
                    "已选择当前主管会话。"
                    if scope.include_session
                    else "本轮不需要使用当前主管会话详情。"
                ),
            ),
            cls._section(
                key="recent_messages",
                label="最近对话",
                included=scope.include_recent_messages,
                item_count=(
                    len(context.recent_messages)
                    if scope.include_recent_messages
                    else 0
                ),
                summary=cls._recent_messages_summary(
                    included=scope.include_recent_messages,
                    count=len(context.recent_messages),
                ),
            ),
            cls._section(
                key="latest_plan",
                label="项目草案",
                included=scope.include_latest_plan,
                item_count=(
                    1
                    if scope.include_latest_plan
                    and context.latest_plan_version is not None
                    else 0
                ),
                summary=cls._latest_plan_summary(
                    included=scope.include_latest_plan,
                    has_plan=context.latest_plan_version is not None,
                ),
            ),
            cls._section(
                key="task_creation",
                label="正式项目与任务",
                included=scope.include_task_creation,
                item_count=cls._task_creation_count(
                    context=context,
                    included=scope.include_task_creation,
                ),
                summary=cls._task_creation_summary(
                    context=context,
                    included=scope.include_task_creation,
                ),
            ),
            cls._section(
                key="project_snapshot",
                label="项目概况",
                included=scope.include_project_snapshot,
                item_count=(
                    1
                    if scope.include_project_snapshot
                    and context.project_snapshot is not None
                    else 0
                ),
                summary=cls._simple_presence_summary(
                    included=scope.include_project_snapshot,
                    present=context.project_snapshot is not None,
                    present_text="已有项目概况可参考。",
                    missing_text="暂无项目概况。",
                    skipped_text="本轮不需要使用项目概况。",
                ),
            ),
            cls._section(
                key="task_snapshot",
                label="任务状态",
                included=scope.include_task_snapshot,
                item_count=cls._task_snapshot_count(
                    context=context,
                    included=scope.include_task_snapshot,
                ),
                summary=cls._task_snapshot_summary(
                    context=context,
                    included=scope.include_task_snapshot,
                ),
            ),
            cls._section(
                key="conversation_list",
                label="其他主管会话",
                included=scope.include_conversation_list,
                item_count=(
                    len(other_conversations)
                    if scope.include_conversation_list
                    else 0
                ),
                summary=cls._conversation_list_summary(
                    included=scope.include_conversation_list,
                    count=len(other_conversations),
                ),
            ),
            cls._section(
                key="inbox_attention",
                label="需要关注的提醒",
                included=scope.include_inbox,
                item_count=len(inbox_items) if scope.include_inbox else 0,
                summary=cls._inbox_summary(
                    included=scope.include_inbox,
                    count=len(inbox_items),
                ),
            ),
            cls._section(
                key="dispatch_attention",
                label="调度建议提醒",
                included=scope.include_dispatch_attention,
                item_count=(
                    len(dispatch_items)
                    if scope.include_dispatch_attention
                    else 0
                ),
                summary=cls._dispatch_summary(
                    included=scope.include_dispatch_attention,
                    count=len(dispatch_items),
                ),
            ),
            cls._section(
                key="safety_boundary",
                label="安全边界",
                included=scope.include_safety_boundary,
                item_count=(
                    len(forbidden_actions)
                    if scope.include_safety_boundary
                    else 0
                ),
                summary=(
                    "系统只会基于已保存的信息回答，不会自动执行或修改。"
                    if scope.include_safety_boundary
                    else "本轮不需要额外安全边界说明。"
                ),
            ),
        ]

    @staticmethod
    def _section(
        *,
        key: str,
        label: str,
        included: bool,
        item_count: int,
        summary: str,
    ) -> DirectorContextSection:
        return DirectorContextSection(
            key=key,
            label=label,
            included=included,
            item_count=max(0, item_count),
            summary=summary,
            source="已保存信息" if included else "未选用",
        )

    def _list_inbox_items(
        self,
        *,
        include: bool,
        project_id: UUID | None,
        limit: int,
    ) -> list[DirectorInboxItem]:
        if not include:
            return []
        return self._inbox_service.list_inbox_items(
            project_id=project_id,
            limit=limit,
        ).items

    def _list_dispatch_items(
        self,
        *,
        include: bool,
        project_id: UUID | None,
        limit: int,
    ) -> list[DirectorInboxItem]:
        if not include:
            return []
        return self._inbox_service.list_inbox_items(
            project_id=project_id,
            kind=InboxItemKind.DISPATCH_QUESTION,
            limit=limit,
        ).items

    def _list_other_conversations(
        self,
        *,
        include: bool,
        project_id: UUID | None,
        current_conversation_id: UUID,
    ) -> list[ConversationListItem]:
        if not include:
            return []
        result = self._conversation_service.list_conversations(
            project_id=project_id,
            limit=20,
        )
        return [
            item
            for item in result.conversations
            if item.conversation_id != current_conversation_id
        ]

    @staticmethod
    def _clamp(value: int, *, lower: int, upper: int) -> int:
        return max(lower, min(value, upper))

    @staticmethod
    def _section_count(sections: list[DirectorContextSection], key: str) -> int:
        for section in sections:
            if section.key == key:
                return section.item_count if section.included else 0
        return 0

    @staticmethod
    def _recent_messages_summary(*, included: bool, count: int) -> str:
        if not included:
            return "本轮不需要使用最近对话。"
        if count <= 0:
            return "暂无最近对话。"
        return f"包含最近 {count} 条对话。"

    @staticmethod
    def _latest_plan_summary(*, included: bool, has_plan: bool) -> str:
        if not included:
            return "本轮不需要使用项目草案。"
        return "存在项目草案。" if has_plan else "暂无项目草案。"

    @staticmethod
    def _task_creation_count(
        *,
        context: ProjectDirectorConversationContext,
        included: bool,
    ) -> int:
        if not included or context.task_creation is None:
            return 0
        raw_count = context.task_creation.get("task_count", 0)
        return int(raw_count) if isinstance(raw_count, int) else 1

    @classmethod
    def _task_creation_summary(
        cls,
        *,
        context: ProjectDirectorConversationContext,
        included: bool,
    ) -> str:
        if not included:
            return "本轮不需要使用正式项目与任务记录。"
        count = cls._task_creation_count(context=context, included=included)
        if count <= 0:
            return "暂无正式项目与任务创建记录。"
        return f"已创建正式项目与 {count} 个任务。"

    @staticmethod
    def _task_snapshot_count(
        *,
        context: ProjectDirectorConversationContext,
        included: bool,
    ) -> int:
        if not included or context.task_snapshot is None:
            return 0
        total = context.task_snapshot.get("total", 0)
        return int(total) if isinstance(total, int) else 0

    @classmethod
    def _task_snapshot_summary(
        cls,
        *,
        context: ProjectDirectorConversationContext,
        included: bool,
    ) -> str:
        if not included:
            return "本轮不需要使用任务状态。"
        count = cls._task_snapshot_count(context=context, included=included)
        if count <= 0:
            return "暂无任务状态。"
        return f"共有 {count} 个任务状态可参考。"

    @staticmethod
    def _simple_presence_summary(
        *,
        included: bool,
        present: bool,
        present_text: str,
        missing_text: str,
        skipped_text: str,
    ) -> str:
        if not included:
            return skipped_text
        return present_text if present else missing_text

    @staticmethod
    def _conversation_list_summary(*, included: bool, count: int) -> str:
        if not included:
            return "本轮不需要使用其他主管会话。"
        if count <= 0:
            return "暂无其他主管会话。"
        return f"有 {count} 个其他主管会话可参考。"

    @staticmethod
    def _inbox_summary(*, included: bool, count: int) -> str:
        if not included:
            return "本轮不需要使用提醒。"
        if count <= 0:
            return "暂无需要关注的提醒。"
        return f"有 {count} 条需要关注的提醒。"

    @staticmethod
    def _dispatch_summary(*, included: bool, count: int) -> str:
        if not included:
            return "本轮不需要使用调度建议提醒。"
        if count <= 0:
            return "暂无调度建议提醒。"
        return f"有 {count} 条调度建议需要关注。"

    @staticmethod
    def _build_summary(
        *,
        recent_messages_count: int,
        has_plan: bool,
        inbox_attention_count: int,
        warning: str,
    ) -> str:
        plan_text = "存在项目草案" if has_plan else "暂无项目草案"
        inbox_text = (
            f"并有 {inbox_attention_count} 条需要关注的提醒"
            if inbox_attention_count > 0
            else "暂无需要关注的提醒"
        )
        return (
            f"当前主管会话已有 {recent_messages_count} 条消息，"
            f"{plan_text}，{inbox_text}。{warning}"
        )

    @classmethod
    def _safe_warning(cls, warning: str) -> str:
        normalized = " ".join((warning or "").split())
        if not normalized or cls._contains_technical_word(normalized):
            return "系统只会基于当前已保存信息回答。"
        return normalized

    @classmethod
    def _safe_user_actions(
        cls,
        actions: list[str],
        *,
        fallback: list[str],
        remove_execution_words: bool,
    ) -> list[str]:
        cleaned: list[str] = []
        for action in actions:
            normalized = " ".join((action or "").split())
            if not normalized:
                continue
            if cls._contains_technical_word(normalized):
                continue
            if remove_execution_words and any(
                word in normalized for word in _EXECUTION_ACTION_WORDS
            ):
                continue
            cleaned.append(normalized)
        return cleaned or list(fallback)

    @staticmethod
    def _contains_technical_word(value: str) -> bool:
        normalized = value.lower()
        return any(word.lower() in normalized for word in _TECHNICAL_WORDS)
