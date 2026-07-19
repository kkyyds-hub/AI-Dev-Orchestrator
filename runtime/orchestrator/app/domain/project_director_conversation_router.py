"""Pure domain router for Project Director conversation input.

This module intentionally performs only local, rule-based classification.  It
does not call providers, read or write repositories/databases, create tasks,
start workers, launch external tools, or mutate project files.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from app.domain._base import DomainModel


class ConversationIntent(StrEnum):
    """Input-side intent categories for one Project Director user message."""

    GENERAL_DISCUSSION = "general_discussion"
    ASK_CURRENT_CONTEXT = "ask_current_context"
    ASK_PLAN = "ask_plan"
    ASK_RISKS = "ask_risks"
    ASK_NEXT_STEP = "ask_next_step"
    ASK_INBOX = "ask_inbox"
    ASK_CONVERSATION_LIST = "ask_conversation_list"
    ASK_TASK_OR_RUN = "ask_task_or_run"
    CHALLENGE_PLAN = "challenge_plan"
    REQUEST_PLAN_CHANGE = "request_plan_change"
    REQUEST_ACTION = "request_action"
    RESTART_OR_NEW_GOAL = "restart_or_new_goal"
    NAVIGATION_HELP = "navigation_help"
    UNKNOWN = "unknown"


class SafetyRiskLevel(StrEnum):
    """Risk level for routing-side safety guidance."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ContextScope(DomainModel):
    """Read-only context categories recommended for answering an intent."""

    include_session: bool = False
    include_recent_messages: bool = False
    include_latest_plan: bool = False
    include_task_creation: bool = False
    include_project_snapshot: bool = False
    include_task_snapshot: bool = False
    include_conversation_list: bool = False
    include_inbox: bool = False
    include_dispatch_attention: bool = False
    include_safety_boundary: bool = False


class SafetyPolicy(DomainModel):
    """User-visible safety policy returned by the pure router."""

    risk_level: SafetyRiskLevel
    requires_confirmation: bool
    forbidden_actions: list[str] = Field(default_factory=list)
    safe_next_actions: list[str] = Field(default_factory=list)
    user_visible_warning: str

    @field_validator("forbidden_actions", "safe_next_actions")
    @classmethod
    def reject_empty_actions(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class RouteDecision(DomainModel):
    """Pure routing decision for one incoming Project Director message."""

    intent: ConversationIntent
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    context_scope: ContextScope
    safety_policy: SafetyPolicy
    should_call_provider: bool = False
    should_persist_user_message: bool = True
    should_create_conversation: bool = False
    should_create_task: bool = False
    should_start_worker: bool = False
    should_launch_executor: bool = False
    should_modify_repository: bool = False


_FORBIDDEN_ACTIONS_CN = [
    "不会自动执行任务",
    "不会自动创建任务",
    "不会修改仓库",
    "不会启动外部工具",
    "不会直接应用草案修改",
]

_EXECUTION_SAFE_NEXT_ACTIONS_BLOCKLIST = {
    "启动执行",
    "提交代码",
    "推送",
    "合并",
    "派发 Codex",
}


class ConversationRouter:
    """Rule-based pure domain router for Project Director conversations."""

    _REQUEST_ACTION_KEYWORDS = (
        "执行",
        "启动",
        "开始跑",
        "创建任务",
        "提交",
        "推送",
        "合并",
    )
    _RESTART_OR_NEW_GOAL_KEYWORDS = (
        "重新开始",
        "新目标",
        "换一个需求",
        "新建主管会话",
    )
    _REQUEST_PLAN_CHANGE_KEYWORDS = (
        "修改草案",
        "改计划",
        "调整计划",
        "重新拆",
    )
    _CHALLENGE_PLAN_KEYWORDS = (
        "我不同意",
        "不合理",
        "质疑",
        "为什么这样",
        "这样不对",
    )
    _ASK_TASK_OR_RUN_KEYWORDS = (
        "任务",
        "运行",
        "执行记录",
        "失败",
        "阻塞",
    )
    _ASK_INBOX_KEYWORDS = (
        "提醒",
        "收件箱",
        "待处理",
        "需要我处理",
    )
    _ASK_CONVERSATION_LIST_KEYWORDS = (
        "会话",
        "对话",
        "历史讨论",
    )
    _ASK_PLAN_KEYWORDS = (
        "草案",
        "计划",
        "规划",
        "怎么拆",
    )
    _ASK_RISKS_KEYWORDS = (
        "风险",
        "问题",
        "隐患",
        "坑",
    )
    _ASK_CURRENT_CONTEXT_KEYWORDS = (
        "当前状态",
        "现在进度",
        "做到哪",
        "项目情况",
    )
    _ASK_NEXT_STEP_KEYWORDS = (
        "下一步",
        "接下来",
        "继续做什么",
    )
    _NAVIGATION_HELP_KEYWORDS = (
        "去哪看",
        "打开哪里",
        "怎么进入",
        "页面在哪",
    )

    @classmethod
    def classify(
        cls,
        content: str,
        current_session_exists: bool = True,
    ) -> RouteDecision:
        """Classify user input without side effects."""

        normalized = (content or "").strip()
        if not normalized:
            return cls._build_decision(
                intent=ConversationIntent.UNKNOWN,
                confidence=0.05,
                reason="输入为空，无法判断意图。",
                should_call_provider=False,
            )

        intent, matched_keyword = cls._match_intent(normalized)
        should_call_provider = intent not in {
            ConversationIntent.UNKNOWN,
            ConversationIntent.REQUEST_ACTION,
            ConversationIntent.RESTART_OR_NEW_GOAL,
        }
        reason = (
            f"匹配关键词“{matched_keyword}”。"
            if matched_keyword
            else "未匹配特定关键词，按普通讨论处理。"
        )
        if not current_session_exists:
            reason = f"{reason} 当前没有已选择的主管会话。"

        return cls._build_decision(
            intent=intent,
            confidence=0.9 if matched_keyword else 0.45,
            reason=reason,
            should_call_provider=should_call_provider,
        )

    @classmethod
    def build_decision_for_intent(
        cls,
        *,
        intent: ConversationIntent,
        confidence: float,
        reason: str,
        should_call_provider: bool,
    ) -> RouteDecision:
        """Build a compatible decision without re-running keyword classification."""

        return cls._build_decision(
            intent=intent,
            confidence=confidence,
            reason=reason,
            should_call_provider=should_call_provider,
        )

    @classmethod
    def _match_intent(cls, normalized: str) -> tuple[ConversationIntent, str | None]:
        """Return the highest-priority matching intent and keyword."""

        priority_rules: tuple[tuple[ConversationIntent, tuple[str, ...]], ...] = (
            (ConversationIntent.REQUEST_ACTION, cls._REQUEST_ACTION_KEYWORDS),
            (ConversationIntent.RESTART_OR_NEW_GOAL, cls._RESTART_OR_NEW_GOAL_KEYWORDS),
            (ConversationIntent.REQUEST_PLAN_CHANGE, cls._REQUEST_PLAN_CHANGE_KEYWORDS),
            (ConversationIntent.CHALLENGE_PLAN, cls._CHALLENGE_PLAN_KEYWORDS),
            (ConversationIntent.ASK_TASK_OR_RUN, cls._ASK_TASK_OR_RUN_KEYWORDS),
            (ConversationIntent.ASK_INBOX, cls._ASK_INBOX_KEYWORDS),
            (
                ConversationIntent.ASK_CONVERSATION_LIST,
                cls._ASK_CONVERSATION_LIST_KEYWORDS,
            ),
            (ConversationIntent.ASK_PLAN, cls._ASK_PLAN_KEYWORDS),
            (ConversationIntent.ASK_RISKS, cls._ASK_RISKS_KEYWORDS),
            (
                ConversationIntent.ASK_CURRENT_CONTEXT,
                cls._ASK_CURRENT_CONTEXT_KEYWORDS,
            ),
            (ConversationIntent.ASK_NEXT_STEP, cls._ASK_NEXT_STEP_KEYWORDS),
            (ConversationIntent.NAVIGATION_HELP, cls._NAVIGATION_HELP_KEYWORDS),
        )
        for intent, keywords in priority_rules:
            for keyword in keywords:
                if keyword in normalized:
                    return intent, keyword
        return ConversationIntent.GENERAL_DISCUSSION, None

    @classmethod
    def _build_decision(
        cls,
        *,
        intent: ConversationIntent,
        confidence: float,
        reason: str,
        should_call_provider: bool,
    ) -> RouteDecision:
        return RouteDecision(
            intent=intent,
            confidence=confidence,
            reason=reason,
            context_scope=cls._context_scope_for_intent(intent),
            safety_policy=cls._safety_policy_for_intent(intent),
            should_call_provider=should_call_provider,
            should_persist_user_message=True,
            should_create_conversation=False,
            should_create_task=False,
            should_start_worker=False,
            should_launch_executor=False,
            should_modify_repository=False,
        )

    @staticmethod
    def _context_scope_for_intent(intent: ConversationIntent) -> ContextScope:
        if intent == ConversationIntent.ASK_CURRENT_CONTEXT:
            return ContextScope(
                include_session=True,
                include_recent_messages=True,
                include_latest_plan=True,
                include_task_creation=True,
                include_project_snapshot=True,
                include_task_snapshot=True,
                include_inbox=True,
            )
        if intent in {
            ConversationIntent.ASK_PLAN,
            ConversationIntent.ASK_RISKS,
            ConversationIntent.REQUEST_PLAN_CHANGE,
            ConversationIntent.CHALLENGE_PLAN,
        }:
            return ContextScope(
                include_latest_plan=True,
                include_recent_messages=True,
                include_safety_boundary=True,
            )
        if intent == ConversationIntent.ASK_NEXT_STEP:
            return ContextScope(
                include_latest_plan=True,
                include_task_creation=True,
                include_inbox=True,
                include_dispatch_attention=True,
                include_safety_boundary=True,
            )
        if intent == ConversationIntent.ASK_INBOX:
            return ContextScope(
                include_inbox=True,
                include_dispatch_attention=True,
                include_safety_boundary=True,
            )
        if intent == ConversationIntent.ASK_CONVERSATION_LIST:
            return ContextScope(
                include_conversation_list=True,
                include_recent_messages=True,
            )
        if intent == ConversationIntent.ASK_TASK_OR_RUN:
            return ContextScope(
                include_task_snapshot=True,
                include_task_creation=True,
                include_inbox=True,
                include_dispatch_attention=True,
            )
        if intent == ConversationIntent.REQUEST_ACTION:
            return ContextScope(
                include_safety_boundary=True,
                include_inbox=True,
                include_dispatch_attention=True,
            )
        if intent == ConversationIntent.RESTART_OR_NEW_GOAL:
            return ContextScope(include_safety_boundary=True)
        return ContextScope(
            include_session=True,
            include_recent_messages=True,
            include_latest_plan=True,
        )

    @classmethod
    def _safety_policy_for_intent(cls, intent: ConversationIntent) -> SafetyPolicy:
        if intent == ConversationIntent.REQUEST_ACTION:
            return SafetyPolicy(
                risk_level=SafetyRiskLevel.HIGH,
                requires_confirmation=True,
                forbidden_actions=list(_FORBIDDEN_ACTIONS_CN),
                safe_next_actions=cls._safe_next_actions_for_intent(intent),
                user_visible_warning=(
                    "这听起来像要执行操作。系统不会自动执行任务，也不会修改仓库。"
                ),
            )
        if intent == ConversationIntent.REQUEST_PLAN_CHANGE:
            return SafetyPolicy(
                risk_level=SafetyRiskLevel.MEDIUM,
                requires_confirmation=True,
                forbidden_actions=list(_FORBIDDEN_ACTIONS_CN),
                safe_next_actions=cls._safe_next_actions_for_intent(intent),
                user_visible_warning="这可能会修改项目草案，需要你确认。",
            )
        if intent == ConversationIntent.CHALLENGE_PLAN:
            return SafetyPolicy(
                risk_level=SafetyRiskLevel.MEDIUM,
                requires_confirmation=False,
                forbidden_actions=list(_FORBIDDEN_ACTIONS_CN),
                safe_next_actions=cls._safe_next_actions_for_intent(intent),
                user_visible_warning=(
                    "这是对计划的质疑，系统会先记录和解释，不会直接修改草案。"
                ),
            )
        if intent == ConversationIntent.RESTART_OR_NEW_GOAL:
            return SafetyPolicy(
                risk_level=SafetyRiskLevel.MEDIUM,
                requires_confirmation=True,
                forbidden_actions=list(_FORBIDDEN_ACTIONS_CN),
                safe_next_actions=cls._safe_next_actions_for_intent(intent),
                user_visible_warning=(
                    "新目标会开始新的主管对话，不会自动创建正式项目或任务。"
                ),
            )
        return SafetyPolicy(
            risk_level=SafetyRiskLevel.LOW,
            requires_confirmation=False,
            forbidden_actions=list(_FORBIDDEN_ACTIONS_CN),
            safe_next_actions=cls._safe_next_actions_for_intent(intent),
            user_visible_warning="系统只会基于当前已保存信息回答。",
        )

    @staticmethod
    def _safe_next_actions_for_intent(intent: ConversationIntent) -> list[str]:
        actions_by_intent = {
            ConversationIntent.ASK_PLAN: ["继续提问", "查看项目草案", "要求解释原因"],
            ConversationIntent.ASK_RISKS: ["继续提问", "查看项目草案", "要求解释原因"],
            ConversationIntent.REQUEST_PLAN_CHANGE: [
                "继续提问",
                "查看项目草案",
                "要求解释原因",
            ],
            ConversationIntent.CHALLENGE_PLAN: [
                "继续提问",
                "查看项目草案",
                "要求解释原因",
            ],
            ConversationIntent.ASK_INBOX: ["继续提问", "查看提醒"],
            ConversationIntent.ASK_TASK_OR_RUN: ["继续提问", "查看任务状态"],
            ConversationIntent.ASK_NEXT_STEP: [
                "继续提问",
                "查看项目草案",
                "查看提醒",
                "查看任务状态",
            ],
            ConversationIntent.REQUEST_ACTION: ["继续提问", "要求解释原因"],
        }
        actions = actions_by_intent.get(intent, ["继续提问", "要求解释原因"])
        return [
            action
            for action in actions
            if action not in _EXECUTION_SAFE_NEXT_ACTIONS_BLOCKLIST
        ]
