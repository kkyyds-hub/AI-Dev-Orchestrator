"""Pure domain model for Project Director user challenges.

This module is intentionally rule-based and side-effect free. It does not read
or write databases, call AI providers, create tasks, start workers, launch
external tools, or mutate repositories.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel
from app.domain.project_director_conversation_router import ConversationIntent


class UserChallengeType(StrEnum):
    """Structured challenge categories raised by a user."""

    PLAN_CHALLENGE = "plan_challenge"
    TASK_SCOPE_CHALLENGE = "task_scope_challenge"
    PRIORITY_CHALLENGE = "priority_challenge"
    RISK_CHALLENGE = "risk_challenge"
    DISPATCH_CHALLENGE = "dispatch_challenge"
    INBOX_ATTENTION_CHALLENGE = "inbox_attention_challenge"
    DELIVERABLE_CHALLENGE = "deliverable_challenge"
    GOVERNANCE_CHALLENGE = "governance_challenge"
    REQUIREMENT_CHANGE = "requirement_change"
    CLARIFICATION_REQUEST = "clarification_request"
    UNKNOWN = "unknown"


class UserChallengeSeverity(StrEnum):
    """Severity levels for a user challenge seed."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKING = "blocking"


class UserChallengeStatus(StrEnum):
    """Lifecycle states reserved for later persistence/workflow stages."""

    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONVERTED_TO_PLAN_REVISION = "converted_to_plan_revision"
    CONVERTED_TO_PROPOSAL = "converted_to_proposal"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class InterventionTargetType(StrEnum):
    """Target type that the challenge is about."""

    CONVERSATION = "conversation"
    PLAN_VERSION = "plan_version"
    TASK = "task"
    RUN = "run"
    INBOX_ITEM = "inbox_item"
    DISPATCH_DECISION = "dispatch_decision"
    DELIVERABLE = "deliverable"
    GOVERNANCE_RULE = "governance_rule"
    UNKNOWN = "unknown"


class UserChallengeSeed(DomainModel):
    """Side-effect-free seed that can later be reviewed or converted."""

    challenge_type: UserChallengeType
    severity: UserChallengeSeverity
    status: UserChallengeStatus
    target_type: InterventionTargetType
    target_id: UUID | None = None
    conversation_id: UUID | None = None
    project_id: UUID | None = None
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=600)
    user_statement: str = Field(min_length=1, max_length=10_000)
    extracted_reason: str = Field(min_length=1, max_length=600)
    requires_response: bool
    requires_plan_revision: bool
    requires_human_confirmation: bool
    safe_next_actions: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)

    @field_validator(
        "title", "summary", "user_statement", "extracted_reason", mode="before"
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("text fields must not be empty")
        return normalized

    @field_validator("safe_next_actions", "forbidden_actions")
    @classmethod
    def normalize_action_texts(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


_FORBIDDEN_ACTIONS_CN = [
    "不会自动修改草案",
    "不会自动创建任务",
    "不会自动执行任务",
    "不会修改仓库",
    "不会启动外部工具",
]

_EXECUTION_ACTION_TEXTS = (
    "启动执行",
    "创建任务",
    "推送",
    "合并",
    "提交代码",
    "重试",
)

_BLOCKING_KEYWORDS = ("阻塞", "不能继续", "卡住", "必须先解决")

_CHALLENGE_SIGNAL_KEYWORDS = (
    "不同意",
    "不合理",
    "不对",
    "有问题",
    "为什么这样",
    "不应该",
)

_CLARIFICATION_KEYWORDS = ("解释", "为什么", "依据", "原因")

_KEYWORDS_BY_TYPE: tuple[tuple[UserChallengeType, tuple[str, ...]], ...] = (
    (
        UserChallengeType.REQUIREMENT_CHANGE,
        ("改需求", "换需求", "新需求", "需求变了"),
    ),
    (
        UserChallengeType.DISPATCH_CHALLENGE,
        ("调度", "派给", "Codex", "Claude", "DeepSeek", "外部工具"),
    ),
    (
        UserChallengeType.GOVERNANCE_CHALLENGE,
        ("成本", "角色", "Skill", "skill", "权限", "治理"),
    ),
    (
        UserChallengeType.PLAN_CHALLENGE,
        ("计划", "草案", "拆分", "阶段"),
    ),
    (
        UserChallengeType.TASK_SCOPE_CHALLENGE,
        ("任务", "范围", "验收", "做多了", "做少了"),
    ),
    (
        UserChallengeType.RISK_CHALLENGE,
        ("风险", "隐患", "坑", "不安全"),
    ),
    (
        UserChallengeType.PRIORITY_CHALLENGE,
        ("优先级", "先后", "顺序", "先做", "后做"),
    ),
    (
        UserChallengeType.INBOX_ATTENTION_CHALLENGE,
        ("提醒", "待处理", "收件箱"),
    ),
    (
        UserChallengeType.DELIVERABLE_CHALLENGE,
        ("交付物", "文档", "报告", "产物"),
    ),
)

_TITLES_CN = {
    UserChallengeType.PLAN_CHALLENGE: "质疑项目草案",
    UserChallengeType.TASK_SCOPE_CHALLENGE: "质疑任务范围",
    UserChallengeType.PRIORITY_CHALLENGE: "质疑优先级",
    UserChallengeType.RISK_CHALLENGE: "质疑风险判断",
    UserChallengeType.DISPATCH_CHALLENGE: "质疑调度建议",
    UserChallengeType.INBOX_ATTENTION_CHALLENGE: "质疑提醒事项",
    UserChallengeType.DELIVERABLE_CHALLENGE: "质疑交付物",
    UserChallengeType.GOVERNANCE_CHALLENGE: "质疑治理设置",
    UserChallengeType.REQUIREMENT_CHANGE: "需求变更",
    UserChallengeType.CLARIFICATION_REQUEST: "要求解释",
    UserChallengeType.UNKNOWN: "无法判断的反馈",
}

_REASONS_CN = {
    UserChallengeType.PLAN_CHALLENGE: "用户认为当前项目草案需要复核。",
    UserChallengeType.TASK_SCOPE_CHALLENGE: "用户认为任务范围或验收标准需要复核。",
    UserChallengeType.PRIORITY_CHALLENGE: "用户认为先后顺序或优先级需要复核。",
    UserChallengeType.RISK_CHALLENGE: "用户认为风险判断需要复核。",
    UserChallengeType.DISPATCH_CHALLENGE: "用户认为调度建议需要人工确认。",
    UserChallengeType.INBOX_ATTENTION_CHALLENGE: "用户认为提醒事项需要重新检查。",
    UserChallengeType.DELIVERABLE_CHALLENGE: "用户认为交付物内容需要复核。",
    UserChallengeType.GOVERNANCE_CHALLENGE: "用户认为成本、角色、技能或权限设置需要复核。",
    UserChallengeType.REQUIREMENT_CHANGE: "用户表达了需求变化，需要重新确认范围。",
    UserChallengeType.CLARIFICATION_REQUEST: "用户希望先了解原因和依据。",
    UserChallengeType.UNKNOWN: "暂时无法判断用户反馈指向哪一类事项。",
}

_SAFE_NEXT_ACTIONS_BY_TYPE = {
    UserChallengeType.PLAN_CHALLENGE: [
        "解释当前草案",
        "标记为需要复核",
        "准备修改建议",
    ],
    UserChallengeType.TASK_SCOPE_CHALLENGE: [
        "检查任务范围",
        "补充验收标准",
        "标记为需要复核",
    ],
    UserChallengeType.PRIORITY_CHALLENGE: [
        "解释先后顺序",
        "标记为需要复核",
        "准备调整建议",
    ],
    UserChallengeType.RISK_CHALLENGE: [
        "解释风险依据",
        "补充风险说明",
        "标记为需要复核",
    ],
    UserChallengeType.DISPATCH_CHALLENGE: [
        "解释调度依据",
        "等待人工确认",
    ],
    UserChallengeType.INBOX_ATTENTION_CHALLENGE: [
        "检查提醒事项",
        "解释提醒原因",
        "标记为需要复核",
    ],
    UserChallengeType.DELIVERABLE_CHALLENGE: [
        "检查交付物内容",
        "补充验收标准",
        "标记为需要复核",
    ],
    UserChallengeType.GOVERNANCE_CHALLENGE: [
        "解释治理依据",
        "等待人工确认",
        "标记为需要复核",
    ],
    UserChallengeType.REQUIREMENT_CHANGE: [
        "确认新需求范围",
        "准备草案调整",
    ],
    UserChallengeType.CLARIFICATION_REQUEST: [
        "解释原因",
        "展开依据",
    ],
    UserChallengeType.UNKNOWN: [
        "要求补充说明",
        "继续澄清问题",
    ],
}

_VISIBLE_REPLACEMENTS = {
    "Codex": "外部工具",
    "Claude": "外部工具",
    "DeepSeek": "外部工具",
    "provider": "回答服务",
    "Provider": "回答服务",
    "worker": "外部工具",
    "Worker": "外部工具",
    "executor": "外部工具",
    "Executor": "外部工具",
    "runtime": "运行环境",
    "Runtime": "运行环境",
    "API": "接口",
    "payload": "数据",
    "Git": "仓库",
    "dispatch_question": "调度提醒",
    "session_id": "会话标识",
    "project_id": "项目标识",
    "synthetic": "汇总信息",
    "read model": "只读视图",
    "intent": "意图",
    "source_detail": "来源说明",
    "risk_level": "风险等级",
    "suggested_actions": "建议动作",
    "Skill": "技能",
    "skill": "技能",
}


class UserChallengeClassifier:
    """Rule-based user challenge classifier with no side effects."""

    @classmethod
    def classify(
        cls,
        *,
        user_content: str,
        route_intent: ConversationIntent | None = None,
        target_type: InterventionTargetType | None = None,
        target_id: UUID | None = None,
        conversation_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> UserChallengeSeed:
        normalized = (user_content or "").strip()
        if not normalized:
            normalized = "用户未提供具体内容"

        challenge_type = cls._classify_type(normalized, route_intent)
        severity = cls._classify_severity(normalized, challenge_type)
        status = cls._status_for(challenge_type, severity)
        safe_next_actions = cls._safe_next_actions_for(challenge_type)

        return UserChallengeSeed(
            challenge_type=challenge_type,
            severity=severity,
            status=status,
            target_type=target_type or InterventionTargetType.UNKNOWN,
            target_id=target_id,
            conversation_id=conversation_id,
            project_id=project_id,
            title=_TITLES_CN[challenge_type],
            summary=cls._build_summary(challenge_type, normalized),
            user_statement=normalized,
            extracted_reason=cls._build_reason(challenge_type, normalized),
            requires_response=challenge_type != UserChallengeType.UNKNOWN,
            requires_plan_revision=challenge_type
            in {
                UserChallengeType.REQUIREMENT_CHANGE,
                UserChallengeType.PLAN_CHALLENGE,
                UserChallengeType.TASK_SCOPE_CHALLENGE,
                UserChallengeType.PRIORITY_CHALLENGE,
            },
            requires_human_confirmation=cls._requires_human_confirmation(
                challenge_type, severity
            ),
            safe_next_actions=safe_next_actions,
            forbidden_actions=list(_FORBIDDEN_ACTIONS_CN),
        )

    @classmethod
    def _classify_type(
        cls,
        normalized: str,
        route_intent: ConversationIntent | None,
    ) -> UserChallengeType:
        for challenge_type, keywords in _KEYWORDS_BY_TYPE:
            if any(keyword in normalized for keyword in keywords):
                return challenge_type

        has_challenge_signal = any(
            keyword in normalized for keyword in _CHALLENGE_SIGNAL_KEYWORDS
        )
        asks_for_explanation = any(
            keyword in normalized for keyword in _CLARIFICATION_KEYWORDS
        )

        if route_intent == ConversationIntent.REQUEST_ACTION:
            return UserChallengeType.CLARIFICATION_REQUEST
        if route_intent == ConversationIntent.REQUEST_PLAN_CHANGE:
            return UserChallengeType.PLAN_CHALLENGE
        if route_intent == ConversationIntent.CHALLENGE_PLAN:
            if asks_for_explanation and not has_challenge_signal:
                return UserChallengeType.CLARIFICATION_REQUEST
            return UserChallengeType.PLAN_CHALLENGE

        if has_challenge_signal:
            return UserChallengeType.PLAN_CHALLENGE
        if asks_for_explanation:
            return UserChallengeType.CLARIFICATION_REQUEST
        return UserChallengeType.UNKNOWN

    @staticmethod
    def _classify_severity(
        normalized: str,
        challenge_type: UserChallengeType,
    ) -> UserChallengeSeverity:
        if any(keyword in normalized for keyword in _BLOCKING_KEYWORDS):
            return UserChallengeSeverity.BLOCKING
        if challenge_type in {
            UserChallengeType.REQUIREMENT_CHANGE,
            UserChallengeType.DISPATCH_CHALLENGE,
            UserChallengeType.GOVERNANCE_CHALLENGE,
        }:
            return UserChallengeSeverity.HIGH
        if challenge_type in {
            UserChallengeType.PLAN_CHALLENGE,
            UserChallengeType.TASK_SCOPE_CHALLENGE,
            UserChallengeType.RISK_CHALLENGE,
        }:
            return UserChallengeSeverity.MEDIUM
        return UserChallengeSeverity.LOW

    @staticmethod
    def _status_for(
        challenge_type: UserChallengeType,
        severity: UserChallengeSeverity,
    ) -> UserChallengeStatus:
        if challenge_type == UserChallengeType.UNKNOWN:
            return UserChallengeStatus.DRAFT
        if severity in {UserChallengeSeverity.HIGH, UserChallengeSeverity.BLOCKING}:
            return UserChallengeStatus.NEEDS_REVIEW
        if challenge_type in {
            UserChallengeType.PLAN_CHALLENGE,
            UserChallengeType.TASK_SCOPE_CHALLENGE,
            UserChallengeType.PRIORITY_CHALLENGE,
            UserChallengeType.RISK_CHALLENGE,
            UserChallengeType.INBOX_ATTENTION_CHALLENGE,
            UserChallengeType.DELIVERABLE_CHALLENGE,
        }:
            return UserChallengeStatus.NEEDS_REVIEW
        return UserChallengeStatus.DRAFT

    @staticmethod
    def _requires_human_confirmation(
        challenge_type: UserChallengeType,
        severity: UserChallengeSeverity,
    ) -> bool:
        return severity in {
            UserChallengeSeverity.BLOCKING,
            UserChallengeSeverity.HIGH,
        } or challenge_type in {
            UserChallengeType.REQUIREMENT_CHANGE,
            UserChallengeType.DISPATCH_CHALLENGE,
            UserChallengeType.GOVERNANCE_CHALLENGE,
        }

    @staticmethod
    def _safe_next_actions_for(challenge_type: UserChallengeType) -> list[str]:
        return [
            action
            for action in _SAFE_NEXT_ACTIONS_BY_TYPE[challenge_type]
            if not any(blocked in action for blocked in _EXECUTION_ACTION_TEXTS)
        ]

    @classmethod
    def _build_summary(cls, challenge_type: UserChallengeType, normalized: str) -> str:
        snippet = cls._sanitize_visible_text(normalized)
        if len(snippet) > 120:
            snippet = f"{snippet[:117]}..."
        if challenge_type == UserChallengeType.UNKNOWN:
            return f"收到一条需要澄清的反馈：{snippet}"
        return f"收到用户反馈，需要处理“{_TITLES_CN[challenge_type]}”：{snippet}"

    @classmethod
    def _build_reason(cls, challenge_type: UserChallengeType, normalized: str) -> str:
        reason = _REASONS_CN[challenge_type]
        if any(keyword in normalized for keyword in _BLOCKING_KEYWORDS):
            reason = f"{reason} 用户表示这会阻塞后续推进。"
        return cls._sanitize_visible_text(reason)

    @staticmethod
    def _sanitize_visible_text(value: str) -> str:
        sanitized = value
        for old, new in _VISIBLE_REPLACEMENTS.items():
            sanitized = sanitized.replace(old, new)
        return sanitized
