"""Session-scoped Project Director conversational message service.

Stage 7-B2: persists user messages, builds read-only context, and returns a
provider-first assistant chat response with explicit rule fallback. It does not
create runs, dispatch workers, execute planning/apply, apply-local, or perform
repository writes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import json
from uuid import UUID, uuid4

from app.domain.project_director_conversation_router import (
    ConversationIntent,
    ConversationRouter,
    RouteDecision,
    SafetyRiskLevel,
)
from app.domain.project_director_action_proposal import (
    DirectorActionProposal,
    DirectorActionProposalBuilder,
    DirectorActionProposalType,
    DirectorActionRisk,
    ProposalApprovalRequirement,
)
from app.domain.project_director_conversation_conversion import (
    ConversationConversionBuilder,
    ConversationConversionDraft,
    ConversationConversionRisk,
    ConversationConversionStatus,
    ConversationConversionTarget,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_user_challenge import (
    UserChallengeClassifier,
    UserChallengeSeed,
    UserChallengeSeverity,
    UserChallengeType,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.services.project_director_context_builder_service import (
    ProjectDirectorContextBuilderService,
    ProjectDirectorConversationContext,
)
from app.services.project_director_context_assembler_service import (
    DirectorContextAssemblerService,
    DirectorContextAssembly,
)
from app.services.provider_config_service import ProviderConfigService


ProviderTextGenerator = Callable[[str, str, str], tuple[str, str | None]]

_FORBIDDEN_MESSAGE_ACTIONS = [
    "不会自动执行任务",
    "不会自动创建任务",
    "不会修改仓库",
    "不会启动外部工具",
    "不会直接应用草案修改",
]

_SAFE_ACTION_TYPES = {
    "summarize",
    "explain",
    "navigate",
    "request_changes",
    "create_formal_project",
    "run_worker_once",
    "none",
}

_CHALLENGE_SAFE_ACTION_TYPES = {
    "explain",
    "navigate",
    "none",
    "request_changes",
}

_PROPOSAL_SAFE_ACTION_TYPES = {
    "explain",
    "navigate",
    "none",
    "request_changes",
}

_CONVERSION_SAFE_ACTION_TYPES = {
    "explain",
    "navigate",
    "none",
    "request_changes",
}

_EXECUTION_ACTION_TEXTS = (
    "启动执行",
    "创建任务",
    "推送",
    "合并",
    "提交代码",
    "重试",
    "应用修改",
    "执行审批",
)

_TECHNICAL_USER_VISIBLE_TERMS = (
    "provider",
    "Provider",
    "worker",
    "Worker",
    "executor",
    "Executor",
    "runtime",
    "Runtime",
    "API",
    "payload",
    "Git",
    "dispatch_question",
    "session_id",
    "project_id",
    "synthetic",
    "read model",
    "intent",
    "source_detail",
    "risk_level",
    "suggested_actions",
    "challenge_type",
    "challenge_severity",
    "challenge_status",
    "proposal_type",
    "proposal_status",
    "approval_requirement",
    "plan_revision",
    "conversion_target",
    "conversion_status",
    "conversion_risk",
    "task_draft",
    "plan_draft",
    "Codex",
    "Claude",
    "DeepSeek",
    "Skill",
)

_TECHNICAL_TERM_REPLACEMENTS = {
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
    "synthetic": "汇总",
    "read model": "只读视图",
    "intent": "意图",
    "source_detail": "来源说明",
    "risk_level": "风险等级",
    "suggested_actions": "建议动作",
    "challenge_type": "反馈类型",
    "challenge_severity": "反馈严重程度",
    "challenge_status": "反馈状态",
    "proposal_type": "建议类型",
    "proposal_status": "建议状态",
    "approval_requirement": "审查要求",
    "plan_revision": "草案修改建议",
    "conversion_target": "草稿类型",
    "conversion_status": "草稿状态",
    "conversion_risk": "草稿风险",
    "task_draft": "任务草稿",
    "plan_draft": "计划草稿",
    "Skill": "技能",
}

_INTENT_LABELS_CN = {
    ConversationIntent.GENERAL_DISCUSSION: "普通讨论",
    ConversationIntent.ASK_CURRENT_CONTEXT: "询问当前状态",
    ConversationIntent.ASK_PLAN: "询问项目草案",
    ConversationIntent.ASK_RISKS: "询问风险",
    ConversationIntent.ASK_NEXT_STEP: "询问下一步",
    ConversationIntent.ASK_INBOX: "查看提醒",
    ConversationIntent.ASK_CONVERSATION_LIST: "查看已有主管会话",
    ConversationIntent.ASK_TASK_OR_RUN: "询问任务状态",
    ConversationIntent.CHALLENGE_PLAN: "质疑项目草案",
    ConversationIntent.REQUEST_PLAN_CHANGE: "请求调整草案",
    ConversationIntent.REQUEST_ACTION: "请求执行动作",
    ConversationIntent.RESTART_OR_NEW_GOAL: "请求新目标",
    ConversationIntent.NAVIGATION_HELP: "询问入口位置",
    ConversationIntent.UNKNOWN: "未识别意图",
}

_INTENT_TO_MESSAGE_INTENT = {
    ConversationIntent.GENERAL_DISCUSSION: "general_discussion",
    ConversationIntent.ASK_CURRENT_CONTEXT: "ask_about_current_context",
    ConversationIntent.ASK_PLAN: "ask_about_plan",
    ConversationIntent.ASK_RISKS: "ask_about_risks",
    ConversationIntent.ASK_NEXT_STEP: "ask_about_next_step",
    ConversationIntent.ASK_INBOX: "ask_about_current_context",
    ConversationIntent.ASK_CONVERSATION_LIST: "ask_about_current_context",
    ConversationIntent.ASK_TASK_OR_RUN: "ask_about_current_context",
    ConversationIntent.CHALLENGE_PLAN: "request_plan_change",
    ConversationIntent.REQUEST_PLAN_CHANGE: "request_plan_change",
    ConversationIntent.REQUEST_ACTION: "request_action",
    ConversationIntent.RESTART_OR_NEW_GOAL: "restart_or_new_goal",
    ConversationIntent.NAVIGATION_HELP: "navigation_help",
    ConversationIntent.UNKNOWN: "unknown",
}

_RISK_ORDER = {
    ProjectDirectorMessageRiskLevel.LOW: 1,
    ProjectDirectorMessageRiskLevel.MEDIUM: 2,
    ProjectDirectorMessageRiskLevel.HIGH: 3,
}

_ROUTE_RISK_TO_MESSAGE_RISK = {
    SafetyRiskLevel.LOW: ProjectDirectorMessageRiskLevel.LOW,
    SafetyRiskLevel.MEDIUM: ProjectDirectorMessageRiskLevel.MEDIUM,
    SafetyRiskLevel.HIGH: ProjectDirectorMessageRiskLevel.HIGH,
}

_CHALLENGE_SEVERITY_TO_MESSAGE_RISK = {
    UserChallengeSeverity.LOW: ProjectDirectorMessageRiskLevel.LOW,
    UserChallengeSeverity.MEDIUM: ProjectDirectorMessageRiskLevel.MEDIUM,
    UserChallengeSeverity.HIGH: ProjectDirectorMessageRiskLevel.HIGH,
    UserChallengeSeverity.BLOCKING: ProjectDirectorMessageRiskLevel.HIGH,
}

_CHALLENGE_SEVERITY_LABELS_CN = {
    UserChallengeSeverity.LOW: "低",
    UserChallengeSeverity.MEDIUM: "中",
    UserChallengeSeverity.HIGH: "高",
    UserChallengeSeverity.BLOCKING: "阻塞",
}

_PROPOSAL_RISK_TO_MESSAGE_RISK = {
    DirectorActionRisk.LOW: ProjectDirectorMessageRiskLevel.LOW,
    DirectorActionRisk.MEDIUM: ProjectDirectorMessageRiskLevel.MEDIUM,
    DirectorActionRisk.HIGH: ProjectDirectorMessageRiskLevel.HIGH,
}

_CONVERSION_RISK_TO_MESSAGE_RISK = {
    ConversationConversionRisk.LOW: ProjectDirectorMessageRiskLevel.LOW,
    ConversationConversionRisk.MEDIUM: ProjectDirectorMessageRiskLevel.MEDIUM,
    ConversationConversionRisk.HIGH: ProjectDirectorMessageRiskLevel.HIGH,
}

_PROPOSAL_APPROVAL_LABELS_CN = {
    ProposalApprovalRequirement.NONE: "暂不需要确认",
    ProposalApprovalRequirement.USER_CONFIRMATION_REQUIRED: "需要你确认",
    ProposalApprovalRequirement.HUMAN_REVIEW_REQUIRED: "需要人工复核",
    ProposalApprovalRequirement.OWNER_APPROVAL_REQUIRED: "需要负责人确认",
}

_CONVERSION_STATUS_LABELS_CN = {
    ConversationConversionStatus.DRAFT: "草稿",
    ConversationConversionStatus.NEEDS_USER_REVIEW: "需要你确认",
    ConversationConversionStatus.BLOCKED: "暂时阻塞",
    ConversationConversionStatus.CANCELLED: "已取消",
}

_CHALLENGE_SIGNAL_KEYWORDS = (
    "不同意",
    "不合理",
    "不对",
    "有问题",
    "为什么这样",
    "不应该",
    "质疑",
)

_REQUIREMENT_CHANGE_KEYWORDS = (
    "改需求",
    "换需求",
    "新需求",
    "需求变了",
)


@dataclass(frozen=True, slots=True)
class ChatGenerationResult:
    """Normalized assistant reply contract for one conversation turn."""

    content: str
    source: ProjectDirectorMessageSource
    source_detail: str
    intent: str = "general_discussion"
    related_plan_version_id: UUID | None = None
    suggested_actions: list[dict] = field(default_factory=list)
    requires_confirmation: bool = False
    risk_level: ProjectDirectorMessageRiskLevel = ProjectDirectorMessageRiskLevel.LOW
    forbidden_actions_detected: list[str] = field(default_factory=list)


class ProjectDirectorMessageService:
    """Conversation persistence with provider-first assistant chat fallback."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
        message_repository: ProjectDirectorMessageRepository,
        context_builder: ProjectDirectorContextBuilderService | None = None,
        provider_config_service: ProviderConfigService | None = None,
        provider_text_generator: ProviderTextGenerator | None = None,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._context_builder = context_builder or ProjectDirectorContextBuilderService(
            session_repository=session_repository,
            message_repository=message_repository,
        )
        self._provider_config_service = provider_config_service
        self._provider_text_generator = provider_text_generator

    def list_messages(
        self,
        *,
        session_id: UUID,
        limit: int = 50,
        before_message_id: UUID | None = None,
    ) -> tuple[list[ProjectDirectorMessage], bool]:
        self._ensure_session_exists(session_id)
        return self._message_repository.list_by_session_id(
            session_id=session_id,
            limit=limit,
            before_message_id=before_message_id,
        )

    def post_user_message(
        self,
        *,
        session_id: UUID,
        content: str,
    ) -> tuple[ProjectDirectorMessage, ProjectDirectorMessage]:
        session_obj = self._ensure_session_exists(session_id)
        trimmed_content = content.strip()
        if not trimmed_content:
            raise ValueError("content must not be empty or whitespace-only")

        user_message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.USER,
                content=trimmed_content,
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail="user_submitted_message",
                related_project_id=session_obj.project_id,
            )
        )

        route_decision = ConversationRouter.classify(
            content=trimmed_content,
            current_session_exists=True,
        )
        challenge_seed = self._build_challenge_seed(
            user_content=trimmed_content,
            route_decision=route_decision,
            session_id=session_id,
            project_id=session_obj.project_id,
        )
        action_proposal = (
            DirectorActionProposalBuilder.build_from_challenge(challenge_seed)
            if challenge_seed is not None
            else None
        )
        conversion_draft = (
            ConversationConversionBuilder.build_from_proposal(action_proposal)
            if action_proposal is not None
            else None
        )
        context, assembly, context_note = self._assemble_route_context(
            session_id=session_id,
            route_decision=route_decision,
        )
        assistant_reply = self._build_assistant_reply(
            user_content=trimmed_content,
            context=context,
            route_decision=route_decision,
            assembly=assembly,
            context_note=context_note,
            challenge_seed=challenge_seed,
            action_proposal=action_proposal,
            conversion_draft=conversion_draft,
        )

        assistant_message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=assistant_reply.content,
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent=assistant_reply.intent,
                related_plan_version_id=assistant_reply.related_plan_version_id,
                related_project_id=session_obj.project_id,
                source=assistant_reply.source,
                source_detail=assistant_reply.source_detail,
                suggested_actions=assistant_reply.suggested_actions,
                requires_confirmation=assistant_reply.requires_confirmation,
                risk_level=assistant_reply.risk_level,
                forbidden_actions_detected=assistant_reply.forbidden_actions_detected,
            )
        )
        self._message_repository.commit()
        return user_message, assistant_message

    @classmethod
    def _build_challenge_seed(
        cls,
        *,
        user_content: str,
        route_decision: RouteDecision,
        session_id: UUID,
        project_id: UUID | None,
    ) -> UserChallengeSeed | None:
        if not cls._should_build_challenge_seed(
            user_content=user_content,
            route_decision=route_decision,
        ):
            return None
        seed = UserChallengeClassifier.classify(
            user_content=user_content,
            route_intent=route_decision.intent,
            conversation_id=session_id,
            project_id=project_id,
        )
        if seed.challenge_type == UserChallengeType.UNKNOWN:
            return None
        return seed

    @staticmethod
    def _should_build_challenge_seed(
        *,
        user_content: str,
        route_decision: RouteDecision,
    ) -> bool:
        if route_decision.intent in {
            ConversationIntent.CHALLENGE_PLAN,
            ConversationIntent.REQUEST_PLAN_CHANGE,
        }:
            return True
        if route_decision.intent == ConversationIntent.REQUEST_ACTION:
            return any(
                keyword in user_content
                for keyword in (
                    "不同意",
                    "不合理",
                    "不对",
                    "有问题",
                    "不应该",
                    "质疑",
                    "调度",
                    "派给",
                    "Codex",
                    "Claude",
                    "DeepSeek",
                    "外部工具",
                    "改需求",
                    "换需求",
                    "新需求",
                    "需求变了",
                    "成本",
                    "角色",
                    "Skill",
                    "skill",
                    "权限",
                    "治理",
                )
            )
        if route_decision.intent in {
            ConversationIntent.ASK_INBOX,
            ConversationIntent.ASK_TASK_OR_RUN,
        }:
            return any(
                keyword in user_content for keyword in _CHALLENGE_SIGNAL_KEYWORDS
            )
        if any(keyword in user_content for keyword in _REQUIREMENT_CHANGE_KEYWORDS):
            return True
        return False

    def _ensure_session_exists(self, session_id: UUID):
        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")
        return session_obj

    def _assemble_route_context(
        self,
        *,
        session_id: UUID,
        route_decision: RouteDecision,
    ) -> tuple[
        ProjectDirectorConversationContext,
        DirectorContextAssembly | None,
        str | None,
    ]:
        """Build route-scoped context, degrading to the existing base context."""

        db_session = getattr(self._message_repository, "_session", None) or getattr(
            self._session_repository,
            "_session",
            None,
        )
        context_note: str | None = None
        assembly: DirectorContextAssembly | None = None
        if db_session is not None:
            try:
                assembly = DirectorContextAssemblerService(db_session).assemble(
                    conversation_id=session_id,
                    route_decision=route_decision,
                )
            except Exception:  # noqa: BLE001 - chat must continue safely
                context_note = "上下文回看失败，已使用基础上下文"
                context = self._context_builder.build_context(session_id=session_id)
                return context, None, context_note

        context = self._context_builder.build_context(session_id=session_id)
        return context, assembly, context_note

    def _build_assistant_reply(
        self,
        *,
        user_content: str,
        context: ProjectDirectorConversationContext,
        route_decision: RouteDecision,
        assembly: DirectorContextAssembly | None,
        context_note: str | None,
        challenge_seed: UserChallengeSeed | None,
        action_proposal: DirectorActionProposal | None,
        conversion_draft: ConversationConversionDraft | None,
    ) -> ChatGenerationResult:
        provider_config_service = (
            self._provider_config_service or ProviderConfigService()
        )
        try:
            runtime_config = provider_config_service.resolve_openai_runtime_config()
        except Exception as exc:  # noqa: BLE001 - config failures must fallback safely
            return self._apply_route_safety(
                ChatGenerationResult(
                    content=self._build_fallback_reply(
                        user_content=user_content,
                        context=context,
                        route_decision=route_decision,
                        assembly=assembly,
                        context_note=context_note,
                        challenge_seed=challenge_seed,
                        action_proposal=action_proposal,
                        conversion_draft=conversion_draft,
                        reason=f"provider_config_unavailable:{exc}",
                    ),
                    source=ProjectDirectorMessageSource.RULE_FALLBACK,
                    source_detail=self._truncate_source_detail(
                        self._source_detail_with_context_note(
                            self._source_detail_with_challenge_and_proposal(
                                f"stage_7_e4_rule_fallback; reason=provider_config_unavailable:{exc}",
                                challenge_seed,
                                action_proposal,
                                conversion_draft,
                            ),
                            context_note,
                        )
                    ),
                    related_plan_version_id=self._context_plan_version_id(context),
                    forbidden_actions_detected=list(_FORBIDDEN_MESSAGE_ACTIONS),
                ),
                route_decision=route_decision,
                challenge_seed=challenge_seed,
                action_proposal=action_proposal,
                conversion_draft=conversion_draft,
            )

        if not getattr(runtime_config, "api_key", None):
            return self._apply_route_safety(
                ChatGenerationResult(
                    content=self._build_fallback_reply(
                        user_content=user_content,
                        context=context,
                        route_decision=route_decision,
                        assembly=assembly,
                        context_note=context_note,
                        challenge_seed=challenge_seed,
                        action_proposal=action_proposal,
                        conversion_draft=conversion_draft,
                        reason="provider_not_configured",
                    ),
                    source=ProjectDirectorMessageSource.RULE_FALLBACK,
                    source_detail=self._source_detail_with_context_note(
                        self._source_detail_with_challenge_and_proposal(
                            "stage_7_e4_rule_fallback; reason=provider_not_configured",
                            challenge_seed,
                            action_proposal,
                            conversion_draft,
                        ),
                        context_note,
                    ),
                    related_plan_version_id=self._context_plan_version_id(context),
                    forbidden_actions_detected=list(_FORBIDDEN_MESSAGE_ACTIONS),
                ),
                route_decision=route_decision,
                challenge_seed=challenge_seed,
                action_proposal=action_proposal,
                conversion_draft=conversion_draft,
            )

        model_name = runtime_config.model_names.get(
            "balanced",
            next(iter(runtime_config.model_names.values()), "gpt-5.5"),
        )
        prompt_text = self._build_provider_prompt(
            user_content=user_content,
            context=context,
            route_decision=route_decision,
            assembly=assembly,
            context_note=context_note,
            challenge_seed=challenge_seed,
            action_proposal=action_proposal,
            conversion_draft=conversion_draft,
        )
        request_id = f"project-director-chat-{uuid4().hex[:12]}"
        try:
            if self._provider_text_generator is not None:
                output_text, receipt_id = self._provider_text_generator(
                    model_name,
                    prompt_text,
                    request_id,
                )
            else:
                output_text, receipt_id = self._call_provider_text(
                    runtime_config=runtime_config,
                    model_name=model_name,
                    prompt_text=prompt_text,
                    request_id=request_id,
                )
        except Exception as exc:  # noqa: BLE001 - chat must degrade to explicit fallback
            return self._apply_route_safety(
                ChatGenerationResult(
                    content=self._build_fallback_reply(
                        user_content=user_content,
                        context=context,
                        route_decision=route_decision,
                        assembly=assembly,
                        context_note=context_note,
                        challenge_seed=challenge_seed,
                        action_proposal=action_proposal,
                        conversion_draft=conversion_draft,
                        reason=f"provider_generation_failed:{exc}",
                    ),
                    source=ProjectDirectorMessageSource.RULE_FALLBACK,
                    source_detail=self._truncate_source_detail(
                        self._source_detail_with_context_note(
                            self._source_detail_with_challenge_and_proposal(
                                f"stage_7_e4_rule_fallback; reason=provider_generation_failed:{exc}",
                                challenge_seed,
                                action_proposal,
                                conversion_draft,
                            ),
                            context_note,
                        )
                    ),
                    related_plan_version_id=self._context_plan_version_id(context),
                    forbidden_actions_detected=list(_FORBIDDEN_MESSAGE_ACTIONS),
                ),
                route_decision=route_decision,
                challenge_seed=challenge_seed,
                action_proposal=action_proposal,
                conversion_draft=conversion_draft,
            )

        cleaned_output = output_text.strip()
        if not cleaned_output:
            return self._apply_route_safety(
                ChatGenerationResult(
                    content=self._build_fallback_reply(
                        user_content=user_content,
                        context=context,
                        route_decision=route_decision,
                        assembly=assembly,
                        context_note=context_note,
                        challenge_seed=challenge_seed,
                        action_proposal=action_proposal,
                        conversion_draft=conversion_draft,
                        reason="provider_empty_output",
                    ),
                    source=ProjectDirectorMessageSource.RULE_FALLBACK,
                    source_detail=self._source_detail_with_context_note(
                        self._source_detail_with_challenge_and_proposal(
                            "stage_7_e4_rule_fallback; reason=provider_empty_output",
                            challenge_seed,
                            action_proposal,
                            conversion_draft,
                        ),
                        context_note,
                    ),
                    related_plan_version_id=self._context_plan_version_id(context),
                    forbidden_actions_detected=list(_FORBIDDEN_MESSAGE_ACTIONS),
                ),
                route_decision=route_decision,
                challenge_seed=challenge_seed,
                action_proposal=action_proposal,
                conversion_draft=conversion_draft,
            )

        try:
            parsed_reply = self._parse_provider_reply_contract(
                cleaned_output,
                context=context,
            )
        except ValueError as exc:
            return self._apply_route_safety(
                ChatGenerationResult(
                    content=self._build_fallback_reply(
                        user_content=user_content,
                        context=context,
                        route_decision=route_decision,
                        assembly=assembly,
                        context_note=context_note,
                        challenge_seed=challenge_seed,
                        action_proposal=action_proposal,
                        conversion_draft=conversion_draft,
                        reason=f"provider_contract_invalid:{exc}",
                    ),
                    source=ProjectDirectorMessageSource.RULE_FALLBACK,
                    source_detail=self._truncate_source_detail(
                        self._source_detail_with_context_note(
                            self._source_detail_with_challenge_and_proposal(
                                f"stage_7_e4_rule_fallback; reason=provider_contract_invalid:{exc}",
                                challenge_seed,
                                action_proposal,
                                conversion_draft,
                            ),
                            context_note,
                        )
                    ),
                    related_plan_version_id=self._context_plan_version_id(context),
                    forbidden_actions_detected=list(_FORBIDDEN_MESSAGE_ACTIONS),
                ),
                route_decision=route_decision,
                challenge_seed=challenge_seed,
                action_proposal=action_proposal,
                conversion_draft=conversion_draft,
            )

        return self._apply_route_safety(
            ChatGenerationResult(
                content=self._sanitize_user_visible_text(parsed_reply.content),
                source=ProjectDirectorMessageSource.AI,
                source_detail=self._truncate_source_detail(
                    self._source_detail_with_context_note(
                        self._source_detail_with_challenge_and_proposal(
                            "stage_7_e4_provider_chat; "
                            f"receipt={receipt_id or 'missing'}",
                            challenge_seed,
                            action_proposal,
                            conversion_draft,
                        ),
                        context_note,
                    )
                ),
                intent=parsed_reply.intent,
                related_plan_version_id=parsed_reply.related_plan_version_id,
                suggested_actions=parsed_reply.suggested_actions,
                requires_confirmation=parsed_reply.requires_confirmation,
                risk_level=parsed_reply.risk_level,
                forbidden_actions_detected=[
                    *parsed_reply.forbidden_actions_detected,
                    *_FORBIDDEN_MESSAGE_ACTIONS,
                ],
            ),
            route_decision=route_decision,
            challenge_seed=challenge_seed,
            action_proposal=action_proposal,
            conversion_draft=conversion_draft,
        )

    @staticmethod
    def _truncate_source_detail(value: str) -> str:
        return value[:300]

    @classmethod
    def _parse_provider_reply_contract(
        cls,
        raw_output: str,
        *,
        context: ProjectDirectorConversationContext,
    ) -> ChatGenerationResult:
        payload = cls._load_provider_json_object(raw_output)
        answer = str(payload.get("answer", "")).strip()
        if not answer:
            raise ValueError("missing_non_empty_answer")

        forbidden_detected = cls._detect_forbidden_execution_claims(answer)
        if forbidden_detected:
            raise ValueError(
                "forbidden_execution_claim:"
                + ",".join(forbidden_detected[:3])
            )

        related_plan_version_id = cls._context_plan_version_id(context)
        raw_related_plan_id = payload.get("related_plan_version_id")
        if raw_related_plan_id:
            try:
                parsed_related_plan_id = UUID(str(raw_related_plan_id))
            except ValueError as exc:
                raise ValueError("invalid_related_plan_version_id") from exc
            if related_plan_version_id and parsed_related_plan_id != related_plan_version_id:
                raise ValueError("related_plan_version_id_not_in_context")
            related_plan_version_id = parsed_related_plan_id

        suggested_actions = cls._sanitize_suggested_actions(
            payload.get("suggested_actions")
        )
        risk_level = cls._parse_risk_level(payload.get("risk_level"))
        action_requires_confirmation = any(
            bool(action.get("requires_confirmation")) for action in suggested_actions
        )
        requires_confirmation = bool(
            payload.get("requires_confirmation", False)
        ) or action_requires_confirmation

        contract_forbidden = payload.get("forbidden_actions_detected", [])
        if isinstance(contract_forbidden, list):
            forbidden_actions_detected = [
                str(item).strip()
                for item in contract_forbidden
                if str(item).strip()
            ][:10]
        else:
            forbidden_actions_detected = []

        return ChatGenerationResult(
            content=answer[:10_000],
            source=ProjectDirectorMessageSource.AI,
            source_detail="",
            intent=cls._sanitize_intent(payload.get("intent")),
            related_plan_version_id=related_plan_version_id,
            suggested_actions=suggested_actions,
            requires_confirmation=requires_confirmation,
            risk_level=risk_level,
            forbidden_actions_detected=forbidden_actions_detected,
        )

    @staticmethod
    def _load_provider_json_object(raw_output: str) -> dict:
        text = raw_output.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("response_not_json") from exc
        if not isinstance(payload, dict):
            raise ValueError("response_not_object")
        return payload

    @staticmethod
    def _detect_forbidden_execution_claims(answer: str) -> list[str]:
        forbidden_phrases = [
            "已启动 Worker",
            "已经启动 Worker",
            "已创建 Run",
            "已经创建 Run",
            "已执行 planning/apply",
            "已执行 apply-local",
            "已写入仓库",
            "已提交代码",
            "已经提交代码",
            "git push 已完成",
            "已自动执行任务",
            "已经自动执行任务",
            "已修改仓库",
            "已经修改仓库",
            "已启动外部工具",
        ]
        return [phrase for phrase in forbidden_phrases if phrase in answer]

    @classmethod
    def _sanitize_suggested_actions(cls, raw_actions: object) -> list[dict]:
        if not isinstance(raw_actions, list):
            return []
        sanitized: list[dict] = []
        for raw_action in raw_actions[:5]:
            if not isinstance(raw_action, dict):
                continue
            action_type = str(raw_action.get("type", "none")).strip() or "none"
            if action_type not in _SAFE_ACTION_TYPES:
                action_type = "none"
            risk_level = str(raw_action.get("risk_level", "low")).strip()
            if risk_level not in {"low", "medium", "high"}:
                risk_level = "low"
            requires_confirmation = bool(raw_action.get("requires_confirmation"))
            if action_type in {"create_formal_project", "run_worker_once"}:
                requires_confirmation = True
                if risk_level == "low":
                    risk_level = "medium"
            sanitized.append(
                {
                    "type": action_type,
                    "label": cls._sanitize_user_visible_text(
                        str(raw_action.get("label", "建议操作")).strip()[:120]
                    ),
                    "requires_confirmation": requires_confirmation,
                    "risk_level": risk_level,
                }
            )
        return sanitized

    @staticmethod
    def _sanitize_intent(raw_intent: object) -> str:
        intent = str(raw_intent or "general_discussion").strip()
        allowed_intents = {
            "general_discussion",
            "ask_about_current_context",
            "ask_about_plan",
            "ask_about_risks",
            "ask_about_next_step",
            "request_plan_change",
            "request_action",
            "navigation_help",
            "restart_or_new_goal",
            "unknown",
        }
        return intent if intent in allowed_intents else "general_discussion"

    @staticmethod
    def _parse_risk_level(raw_risk_level: object) -> ProjectDirectorMessageRiskLevel:
        try:
            return ProjectDirectorMessageRiskLevel(str(raw_risk_level or "low"))
        except ValueError:
            return ProjectDirectorMessageRiskLevel.LOW

    @staticmethod
    def _context_plan_version_id(
        context: ProjectDirectorConversationContext,
    ) -> UUID | None:
        if context.latest_plan_version is None:
            return None
        plan_version_id = context.latest_plan_version.get("id")
        if plan_version_id is None:
            return None
        try:
            return UUID(str(plan_version_id))
        except ValueError:
            return None

    @classmethod
    def _apply_route_safety(
        cls,
        reply: ChatGenerationResult,
        *,
        route_decision: RouteDecision,
        challenge_seed: UserChallengeSeed | None = None,
        action_proposal: DirectorActionProposal | None = None,
        conversion_draft: ConversationConversionDraft | None = None,
    ) -> ChatGenerationResult:
        route_risk = _ROUTE_RISK_TO_MESSAGE_RISK[
            route_decision.safety_policy.risk_level
        ]
        risk_level = cls._max_risk_level(reply.risk_level, route_risk)
        if challenge_seed is not None:
            risk_level = cls._max_risk_level(
                risk_level,
                _CHALLENGE_SEVERITY_TO_MESSAGE_RISK[challenge_seed.severity],
            )
        if action_proposal is not None:
            risk_level = cls._max_risk_level(
                risk_level,
                _PROPOSAL_RISK_TO_MESSAGE_RISK[action_proposal.risk],
            )
        if conversion_draft is not None:
            risk_level = cls._max_risk_level(
                risk_level,
                _CONVERSION_RISK_TO_MESSAGE_RISK[conversion_draft.risk],
            )
        route_forbidden = cls._sanitize_user_visible_actions(
            route_decision.safety_policy.forbidden_actions
        )
        challenge_forbidden = cls._sanitize_user_visible_actions(
            challenge_seed.forbidden_actions if challenge_seed else []
        )
        proposal_forbidden = cls._sanitize_user_visible_actions(
            action_proposal.forbidden_actions if action_proposal else []
        )
        conversion_forbidden = cls._sanitize_user_visible_actions(
            conversion_draft.forbidden_actions if conversion_draft else []
        )
        forbidden_actions = cls._dedupe_actions(
            [
                *route_forbidden,
                *challenge_forbidden,
                *proposal_forbidden,
                *conversion_forbidden,
                *cls._sanitize_user_visible_actions(
                    reply.forbidden_actions_detected
                ),
                *_FORBIDDEN_MESSAGE_ACTIONS,
            ]
        )
        return ChatGenerationResult(
            content=cls._sanitize_user_visible_text(reply.content)[:10_000],
            source=reply.source,
            source_detail=cls._truncate_source_detail(reply.source_detail),
            intent=cls._message_intent_for_route(
                route_decision,
                challenge_seed,
                action_proposal,
                conversion_draft,
            ),
            related_plan_version_id=reply.related_plan_version_id,
            suggested_actions=cls._filter_suggested_actions_for_route(
                reply.suggested_actions,
                route_decision=route_decision,
                challenge_seed=challenge_seed,
                action_proposal=action_proposal,
                conversion_draft=conversion_draft,
            ),
            requires_confirmation=(
                reply.requires_confirmation
                or route_decision.safety_policy.requires_confirmation
                or (
                    challenge_seed.requires_human_confirmation
                    if challenge_seed is not None
                    else False
                )
                or (
                    action_proposal.approval_requirement
                    != ProposalApprovalRequirement.NONE
                    if action_proposal is not None
                    else False
                )
                or (
                    conversion_draft.status
                    == ConversationConversionStatus.NEEDS_USER_REVIEW
                    if conversion_draft is not None
                    else False
                )
            ),
            risk_level=risk_level,
            forbidden_actions_detected=forbidden_actions[:10],
        )

    @staticmethod
    def _message_intent_for_route(
        route_decision: RouteDecision,
        challenge_seed: UserChallengeSeed | None = None,
        action_proposal: DirectorActionProposal | None = None,
        conversion_draft: ConversationConversionDraft | None = None,
    ) -> str:
        if conversion_draft is not None:
            if conversion_draft.target in {
                ConversationConversionTarget.PLAN_REVISION_DRAFT,
                ConversationConversionTarget.TASK_SCOPE_UPDATE_DRAFT,
                ConversationConversionTarget.PRIORITY_UPDATE_DRAFT,
                ConversationConversionTarget.RISK_UPDATE_DRAFT,
            }:
                return "request_plan_change"
            if conversion_draft.target in {
                ConversationConversionTarget.EXPLANATION_ONLY,
                ConversationConversionTarget.NO_CONVERSION,
            }:
                return "ask_about_current_context"
        if action_proposal is not None:
            if action_proposal.plan_revision is not None:
                return "request_plan_change"
            if action_proposal.proposal_type in {
                DirectorActionProposalType.DISPATCH_REVIEW,
                DirectorActionProposalType.GOVERNANCE_REVIEW,
            }:
                return "ask_about_current_context"
        if challenge_seed is not None:
            if challenge_seed.challenge_type == UserChallengeType.REQUIREMENT_CHANGE:
                return "request_plan_change"
            if challenge_seed.challenge_type == UserChallengeType.DISPATCH_CHALLENGE:
                return "ask_about_current_context"
        return _INTENT_TO_MESSAGE_INTENT.get(
            route_decision.intent,
            "general_discussion",
        )

    @staticmethod
    def _max_risk_level(
        left: ProjectDirectorMessageRiskLevel,
        right: ProjectDirectorMessageRiskLevel,
    ) -> ProjectDirectorMessageRiskLevel:
        return left if _RISK_ORDER[left] >= _RISK_ORDER[right] else right

    @classmethod
    def _filter_suggested_actions_for_route(
        cls,
        suggested_actions: list[dict],
        *,
        route_decision: RouteDecision,
        challenge_seed: UserChallengeSeed | None = None,
        action_proposal: DirectorActionProposal | None = None,
        conversion_draft: ConversationConversionDraft | None = None,
    ) -> list[dict]:
        if not suggested_actions:
            return []
        allowed_types = set(_SAFE_ACTION_TYPES)
        if route_decision.intent == ConversationIntent.REQUEST_ACTION:
            allowed_types = {"explain", "navigate", "none"}
        if challenge_seed is not None:
            allowed_types = allowed_types.intersection(_CHALLENGE_SAFE_ACTION_TYPES)
        if action_proposal is not None:
            allowed_types = allowed_types.intersection(_PROPOSAL_SAFE_ACTION_TYPES)
        if conversion_draft is not None:
            allowed_types = allowed_types.intersection(_CONVERSION_SAFE_ACTION_TYPES)

        filtered: list[dict] = []
        route_risk = _ROUTE_RISK_TO_MESSAGE_RISK[
            route_decision.safety_policy.risk_level
        ]
        challenge_risk = (
            _CHALLENGE_SEVERITY_TO_MESSAGE_RISK[challenge_seed.severity]
            if challenge_seed is not None
            else ProjectDirectorMessageRiskLevel.LOW
        )
        proposal_risk = (
            _PROPOSAL_RISK_TO_MESSAGE_RISK[action_proposal.risk]
            if action_proposal is not None
            else ProjectDirectorMessageRiskLevel.LOW
        )
        conversion_risk = (
            _CONVERSION_RISK_TO_MESSAGE_RISK[conversion_draft.risk]
            if conversion_draft is not None
            else ProjectDirectorMessageRiskLevel.LOW
        )
        proposal_requires_confirmation = (
            action_proposal.approval_requirement != ProposalApprovalRequirement.NONE
            if action_proposal is not None
            else False
        )
        conversion_requires_confirmation = (
            conversion_draft.status == ConversationConversionStatus.NEEDS_USER_REVIEW
            if conversion_draft is not None
            else False
        )
        for action in suggested_actions[:5]:
            action_type = str(action.get("type", "none")).strip() or "none"
            if action_type not in allowed_types:
                continue
            label = cls._sanitize_user_visible_text(
                str(action.get("label", "建议操作")).strip()[:120]
            )
            if any(blocked in label for blocked in _EXECUTION_ACTION_TEXTS):
                continue
            raw_risk = str(action.get("risk_level", "low")).strip()
            try:
                action_risk = ProjectDirectorMessageRiskLevel(raw_risk)
            except ValueError:
                action_risk = ProjectDirectorMessageRiskLevel.LOW
            effective_risk = cls._max_risk_level(
                cls._max_risk_level(
                    cls._max_risk_level(
                        cls._max_risk_level(action_risk, route_risk),
                        challenge_risk,
                    ),
                    proposal_risk,
                ),
                conversion_risk,
            )
            filtered.append(
                {
                    "type": action_type,
                    "label": label,
                    "requires_confirmation": bool(
                        action.get("requires_confirmation")
                    )
                    or route_decision.safety_policy.requires_confirmation
                    or (
                        challenge_seed.requires_human_confirmation
                        if challenge_seed is not None
                        else False
                    )
                    or proposal_requires_confirmation
                    or conversion_requires_confirmation,
                    "risk_level": effective_risk.value,
                }
            )
        return filtered

    @staticmethod
    def _dedupe_actions(actions: list[str]) -> list[str]:
        deduped: list[str] = []
        for action in actions:
            cleaned = action.strip()
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)
        return deduped

    @classmethod
    def _sanitize_user_visible_actions(cls, actions: list[str]) -> list[str]:
        return [
            cleaned
            for action in actions
            if (cleaned := cls._sanitize_user_visible_text(str(action)).strip())
        ]

    @staticmethod
    def _sanitize_user_visible_text(text: str) -> str:
        cleaned = text
        for term, replacement in _TECHNICAL_TERM_REPLACEMENTS.items():
            cleaned = cleaned.replace(term, replacement)
        return cleaned

    @staticmethod
    def _source_detail_with_context_note(
        source_detail: str,
        context_note: str | None,
    ) -> str:
        if not context_note:
            return source_detail
        return f"{source_detail}; context_note={context_note}"

    @classmethod
    def _source_detail_with_challenge_seed(
        cls,
        source_detail: str,
        challenge_seed: UserChallengeSeed | None,
    ) -> str:
        return source_detail + cls._challenge_source_detail_suffix(challenge_seed)

    @classmethod
    def _source_detail_with_challenge_and_proposal(
        cls,
        source_detail: str,
        challenge_seed: UserChallengeSeed | None,
        action_proposal: DirectorActionProposal | None,
        conversion_draft: ConversationConversionDraft | None = None,
    ) -> str:
        if conversion_draft is not None and action_proposal is not None:
            return (
                cls._compact_source_reason(source_detail)
                + cls._proposal_source_detail_suffix(
                    action_proposal,
                    include_status=False,
                )
                + cls._conversion_source_detail_suffix(conversion_draft)
            )
        if action_proposal is None:
            return cls._source_detail_with_challenge_seed(
                source_detail,
                challenge_seed,
            ) + cls._conversion_source_detail_suffix(conversion_draft)
        if challenge_seed is not None:
            source_detail += f"; challenge_type={challenge_seed.challenge_type.value}"
        return (
            source_detail
            + cls._proposal_source_detail_suffix(action_proposal)
            + cls._conversion_source_detail_suffix(conversion_draft)
        )

    @classmethod
    def _source_detail_with_proposal(
        cls,
        source_detail: str,
        action_proposal: DirectorActionProposal | None,
    ) -> str:
        return source_detail + cls._proposal_source_detail_suffix(action_proposal)

    @staticmethod
    def _compact_source_reason(source_detail: str) -> str:
        return source_detail.replace("; reason=", ";")

    @staticmethod
    def _challenge_source_detail_suffix(
        challenge_seed: UserChallengeSeed | None,
    ) -> str:
        if challenge_seed is None:
            return ""
        return (
            f";challenge_type={challenge_seed.challenge_type.value}"
            f";challenge_severity={challenge_seed.severity.value}"
            f";challenge_status={challenge_seed.status.value}"
        )

    @staticmethod
    def _proposal_source_detail_suffix(
        action_proposal: DirectorActionProposal | None,
        *,
        include_status: bool = True,
    ) -> str:
        if action_proposal is None:
            return ""
        status_part = (
            f";proposal_status={action_proposal.status.value}"
            if include_status
            else ""
        )
        return (
            f";proposal_type={action_proposal.proposal_type.value}"
            f"{status_part}"
            f";approval_requirement={action_proposal.approval_requirement.value}"
            ";has_plan_revision="
            f"{str(action_proposal.plan_revision is not None).lower()}"
        )

    @staticmethod
    def _conversion_source_detail_suffix(
        conversion_draft: ConversationConversionDraft | None,
    ) -> str:
        if conversion_draft is None:
            return ""
        return (
            f";conversion_target={conversion_draft.target.value}"
            f";conversion_status={conversion_draft.status.value}"
            f";conversion_risk={conversion_draft.risk.value}"
            ";has_plan_draft="
            f"{str(conversion_draft.plan_draft is not None).lower()}"
            ";has_task_draft="
            f"{str(conversion_draft.task_draft is not None).lower()}"
        )

    @classmethod
    def _build_fallback_reply(
        cls,
        *,
        user_content: str,
        context: ProjectDirectorConversationContext,
        route_decision: RouteDecision,
        assembly: DirectorContextAssembly | None,
        context_note: str | None,
        challenge_seed: UserChallengeSeed | None,
        action_proposal: DirectorActionProposal | None,
        conversion_draft: ConversationConversionDraft | None,
        reason: str,
    ) -> str:
        plan_status = "无计划草案"
        if context.latest_plan_version is not None:
            plan_status = (
                f"v{context.latest_plan_version['version_no']} "
                f"{context.latest_plan_version['status']}"
            )
        task_total = 0
        if context.task_snapshot is not None:
            task_total = int(context.task_snapshot.get("total", 0))
        plan_summary = ""
        risks: list[str] = []
        phase_names: list[str] = []
        proposed_task_titles: list[str] = []
        if context.latest_plan_version is not None:
            plan_summary = str(context.latest_plan_version.get("plan_summary", ""))
            risks = [
                str(risk)
                for risk in context.latest_plan_version.get("risks", [])
            ][:5]
            phase_names = [
                str(phase.get("name"))
                for phase in context.latest_plan_version.get("phases", [])
                if isinstance(phase, dict) and phase.get("name")
            ][:6]
            proposed_task_titles = [
                str(task.get("title"))
                for task in context.latest_plan_version.get("proposed_tasks", [])
                if isinstance(task, dict) and task.get("title")
            ][:6]

        task_creation_line = "尚未读取到正式项目/任务创建记录。"
        if context.task_creation is not None:
            task_creation_line = (
                f"已读取到任务创建记录：项目 {context.task_creation.get('project_name') or '已关联项目'}，"
                f"任务数 {context.task_creation.get('task_count')}。"
            )

        route_lines = cls._route_specific_fallback_lines(route_decision)
        challenge_lines = cls._challenge_fallback_lines(challenge_seed)
        proposal_lines = cls._proposal_fallback_lines(action_proposal)
        conversion_lines = cls._conversion_fallback_lines(conversion_draft)
        assembly_lines = cls._assembly_summary_lines(assembly)
        lines = [
            "已记录你的消息。当前先按安全规则回复。",
            f"用户输入意图：{_INTENT_LABELS_CN.get(route_decision.intent, '普通讨论')}。",
            f"当前安全提醒：{route_decision.safety_policy.user_visible_warning}",
            f"当前会话状态：{context.session_status}；目标：{context.goal_text}。",
            f"澄清问题：{len(context.clarifying_questions)} 个；已回答：{len(context.clarifying_answers)} 个。",
            f"计划上下文：{plan_status}；任务快照数量：{task_total}。",
            task_creation_line,
        ]
        if context_note:
            lines.append(context_note)
        if assembly_lines:
            lines.extend(assembly_lines)
        if plan_summary:
            lines.append(f"草案摘要：{plan_summary[:600]}")
        if phase_names:
            lines.append("阶段概览：" + "、".join(phase_names))
        if proposed_task_titles:
            lines.append("拟议任务：" + "、".join(proposed_task_titles))
        if risks:
            lines.append("主要风险：" + "；".join(risks))
        lines.extend(challenge_lines)
        lines.extend(proposal_lines)
        lines.extend(conversion_lines)
        lines.extend(route_lines)
        lines.extend(
            [
                "建议下一步：可以继续提问、查看草案、查看提醒，或让我先说明需要你确认的步骤。",
                "本回复不会自动执行任务、不会自动创建任务、不会修改仓库、不会启动外部工具。",
                "你的消息摘要："
                + (
                    cls._challenge_visible_summary(challenge_seed)[:240]
                    if challenge_seed is not None
                    else user_content[:240]
                ),
            ]
        )
        return cls._sanitize_user_visible_text("\n".join(lines))[:10_000]

    @classmethod
    def _proposal_fallback_lines(
        cls,
        action_proposal: DirectorActionProposal | None,
    ) -> list[str]:
        if action_proposal is None:
            return []
        lines = [
            "我会先把它整理成一个可审查的建议。",
            f"建议类型：{action_proposal.title}。",
            f"建议摘要：{action_proposal.summary}",
            f"建议原因：{action_proposal.reason}",
            "审查要求："
            + _PROPOSAL_APPROVAL_LABELS_CN[action_proposal.approval_requirement]
            + "。",
        ]
        if action_proposal.plan_revision is not None:
            lines.extend(
                [
                    "这只是修改建议，不会直接改草案。",
                    f"修改建议标题：{action_proposal.plan_revision.title}",
                    f"修改建议摘要：{action_proposal.plan_revision.summary}",
                ]
            )
        if action_proposal.approval_requirement != ProposalApprovalRequirement.NONE:
            lines.append("继续处理前需要你确认或复核。")
        if (
            action_proposal.proposal_type
            == DirectorActionProposalType.DISPATCH_REVIEW
        ):
            lines.append("不会启动外部工具，会先复核调度安排。")
        if (
            action_proposal.proposal_type
            == DirectorActionProposalType.GOVERNANCE_REVIEW
        ):
            lines.append("不会修改治理配置，会先复核风险。")
        if action_proposal.safe_next_actions:
            lines.append(
                "可做下一步："
                + "、".join(
                    cls._sanitize_user_visible_actions(
                        action_proposal.safe_next_actions
                    )[:5]
                )
            )
        if action_proposal.forbidden_actions:
            lines.append(
                "安全边界："
                + "、".join(
                    cls._sanitize_user_visible_actions(
                        action_proposal.forbidden_actions
                    )[:6]
                )
            )
        return lines

    @classmethod
    def _conversion_fallback_lines(
        cls,
        conversion_draft: ConversationConversionDraft | None,
    ) -> list[str]:
        if conversion_draft is None:
            return []
        lines = [
            "我会先把它整理成一个可查看的草稿。",
            f"草稿类型：{conversion_draft.title}。",
            f"草稿摘要：{conversion_draft.summary}",
            f"草稿原因：{conversion_draft.reason}",
            "审查状态："
            + _CONVERSION_STATUS_LABELS_CN[conversion_draft.status]
            + "。",
        ]
        if conversion_draft.plan_draft is not None:
            lines.extend(
                [
                    "这只是计划修改草稿，不会直接改草案。",
                    f"计划草稿标题：{conversion_draft.plan_draft.title}",
                    f"计划草稿摘要：{conversion_draft.plan_draft.summary}",
                ]
            )
        if conversion_draft.task_draft is not None:
            lines.extend(
                [
                    "这只是任务草稿，不会自动创建任务。",
                    f"任务草稿标题：{conversion_draft.task_draft.title}",
                    f"任务草稿摘要：{conversion_draft.task_draft.summary}",
                ]
            )
        if conversion_draft.status == ConversationConversionStatus.NEEDS_USER_REVIEW:
            lines.append("继续处理前需要你确认。")
        if conversion_draft.target == ConversationConversionTarget.EXPLANATION_ONLY:
            lines.append("这类反馈更适合先解释原因，不会执行后续动作。")
        if conversion_draft.safe_next_actions:
            lines.append(
                "可做下一步："
                + "、".join(
                    cls._sanitize_user_visible_actions(
                        conversion_draft.safe_next_actions
                    )[:5]
                )
            )
        if conversion_draft.forbidden_actions:
            lines.append(
                "安全边界："
                + "、".join(
                    cls._sanitize_user_visible_actions(
                        conversion_draft.forbidden_actions
                    )[:7]
                )
            )
        return lines

    @classmethod
    def _challenge_fallback_lines(
        cls,
        challenge_seed: UserChallengeSeed | None,
    ) -> list[str]:
        if challenge_seed is None:
            return []
        lines = [
            "我会先把这当作一个需要复核的问题处理。",
            f"反馈类型：{challenge_seed.title}。",
            f"反馈摘要：{cls._challenge_visible_summary(challenge_seed)}",
            f"提取原因：{challenge_seed.extracted_reason}",
        ]
        if challenge_seed.challenge_type in {
            UserChallengeType.PLAN_CHALLENGE,
            UserChallengeType.TASK_SCOPE_CHALLENGE,
            UserChallengeType.PRIORITY_CHALLENGE,
            UserChallengeType.REQUIREMENT_CHANGE,
        }:
            lines.append("不会直接修改草案，会先解释原因或准备修改建议。")
        elif challenge_seed.challenge_type == UserChallengeType.DISPATCH_CHALLENGE:
            lines.append("不会启动外部工具，会先解释调度依据并等待你确认。")
        elif challenge_seed.challenge_type == UserChallengeType.GOVERNANCE_CHALLENGE:
            lines.append("不会修改治理配置，会先说明风险和建议。")
        elif challenge_seed.challenge_type == UserChallengeType.CLARIFICATION_REQUEST:
            lines.append("会先解释依据。")
        if challenge_seed.safe_next_actions:
            lines.append("可做下一步：" + "、".join(challenge_seed.safe_next_actions[:5]))
        if challenge_seed.forbidden_actions:
            lines.append("安全边界：" + "、".join(challenge_seed.forbidden_actions[:5]))
        return lines

    @staticmethod
    def _challenge_visible_summary(challenge_seed: UserChallengeSeed) -> str:
        return f"{challenge_seed.title}：{challenge_seed.extracted_reason}"

    @staticmethod
    def _route_specific_fallback_lines(route_decision: RouteDecision) -> list[str]:
        if route_decision.intent == ConversationIntent.REQUEST_ACTION:
            return [
                "我不能自动执行任务，也不会修改仓库。",
                "可以先说明需要确认的步骤，等你确认后再走单独的确认流程。",
            ]
        if route_decision.intent == ConversationIntent.ASK_INBOX:
            return ["可以查看提醒并解释含义，但不会替你执行任何操作。"]
        if route_decision.intent == ConversationIntent.ASK_CONVERSATION_LIST:
            return ["可以查看已有主管会话，帮助你选择要继续讨论的会话。"]
        if route_decision.intent == ConversationIntent.CHALLENGE_PLAN:
            return ["这是对草案的质疑；我会先解释和记录，不会直接修改草案。"]
        return []

    @staticmethod
    def _assembly_summary_lines(
        assembly: DirectorContextAssembly | None,
    ) -> list[str]:
        if assembly is None:
            return []
        lines = [f"已选上下文摘要：{assembly.summary}"]
        selected_sections = [
            section
            for section in assembly.sections
            if section.included
        ][:10]
        if selected_sections:
            lines.append(
                "已选上下文："
                + "；".join(
                    f"{section.label}：{section.summary}"
                    for section in selected_sections
                )
            )
        return lines

    @classmethod
    def _build_provider_prompt(
        cls,
        *,
        user_content: str,
        context: ProjectDirectorConversationContext,
        route_decision: RouteDecision,
        assembly: DirectorContextAssembly | None,
        context_note: str | None,
        challenge_seed: UserChallengeSeed | None,
        action_proposal: DirectorActionProposal | None,
        conversion_draft: ConversationConversionDraft | None,
    ) -> str:
        recent_lines = [
            f"- 第 {message.sequence_no} 条 {message.role.value}: {message.content[:300]}"
            for message in context.recent_messages[-10:]
        ]
        section_lines = cls._provider_section_lines(assembly)
        forbidden_actions = cls._sanitize_user_visible_actions(
            (assembly.forbidden_actions if assembly else [])
            or route_decision.safety_policy.forbidden_actions
        )
        safe_next_actions = cls._sanitize_user_visible_actions(
            (assembly.safe_next_actions if assembly else [])
            or route_decision.safety_policy.safe_next_actions
        )
        challenge_lines = cls._provider_challenge_lines(challenge_seed)
        proposal_lines = cls._provider_proposal_lines(action_proposal)
        conversion_lines = cls._provider_conversion_lines(conversion_draft)
        return "\n".join(
            [
                "你是 AI Project Director 的对话大脑。请基于只读上下文回答用户。",
                "硬性边界：不能声称已执行任务；不能声称已修改仓库；不能声称已启动外部工具。",
                "硬性边界：不能声称已修改草案；不能声称已创建任务；不能声称已执行审批；不能把复核问题写成已处理完成。",
                "建议边界：下面如有可审查建议，它只是建议，不是已应用；不能把建议写成已处理完成。",
                "草稿边界：下面如有可查看草稿，它只是草稿，不是已应用；不能声称已修改草案、已创建任务、已执行审批、已启动外部工具；不能把草稿写成已处理完成。",
                "如果用户要求执行，只能说明需要用户确认或建议下一步；不要要求或暗示你会执行真实动作。",
                f"用户输入意图：{_INTENT_LABELS_CN.get(route_decision.intent, '普通讨论')}",
                f"当前安全提醒：{route_decision.safety_policy.user_visible_warning}",
                f"已选上下文摘要：{assembly.summary if assembly else (context_note or '使用基础上下文。')}",
                "上下文章节（最多 10 个）：",
                *(section_lines or ["- 暂无已选章节。"]),
                "禁止动作：" + "、".join(forbidden_actions[:8]),
                "安全下一步：" + "、".join(safe_next_actions[:8]),
                "复核问题回看：",
                *(challenge_lines or ["- 无。"]),
                "可审查建议回看：",
                *(proposal_lines or ["- 无。"]),
                "可查看草稿回看：",
                *(conversion_lines or ["- 无。"]),
                f"会话状态：{context.session_status}",
                f"目标：{context.goal_text[:800]}",
                f"约束：{(context.constraints or '（无）')[:800]}",
                f"目标摘要：{(context.goal_summary or '（无）')[:800]}",
                f"澄清回答：{cls._json_compact(context.clarifying_answers, 1200)}",
                f"澄清问题：{cls._json_compact(context.clarifying_questions, 1200)}",
                f"项目草案：{cls._json_compact(context.latest_plan_version, 2200)}",
                f"任务创建记录：{cls._json_compact(context.task_creation, 1000)}",
                f"项目概况：{cls._json_compact(context.project_snapshot, 1000)}",
                f"任务状态：{cls._json_compact(context.task_snapshot, 1000)}",
                "输出合同：只返回一个 JSON object，keys: "
                "intent, answer, related_plan_version_id, suggested_actions, "
                "requires_confirmation, risk_level, forbidden_actions_detected. "
                "answer 必须是中文用户可见文本，不要包含内部技术词。",
                "最近对话：",
                *(recent_lines or ["- （无）"]),
                f"用户消息：{user_content}",
            ]
        )

    @classmethod
    def _provider_conversion_lines(
        cls,
        conversion_draft: ConversationConversionDraft | None,
    ) -> list[str]:
        if conversion_draft is None:
            return []
        lines = [
            f"- 草稿类型：{conversion_draft.title}",
            f"- 草稿摘要：{conversion_draft.summary[:300]}",
            f"- 草稿原因：{conversion_draft.reason[:300]}",
            "- 审查状态："
            + _CONVERSION_STATUS_LABELS_CN[conversion_draft.status],
            "- 这只是草稿，不是已应用。",
            "- 不能声称已修改草案；不能声称已创建任务；不能声称已执行审批；不能声称已启动外部工具；不能把草稿写成已处理完成。",
        ]
        if conversion_draft.plan_draft is not None:
            lines.extend(
                [
                    f"- 计划草稿标题：{conversion_draft.plan_draft.title}",
                    f"- 计划草稿摘要：{conversion_draft.plan_draft.summary[:300]}",
                    "- 受影响内容："
                    + "、".join(
                        cls._sanitize_user_visible_actions(
                            conversion_draft.plan_draft.affected_sections
                        )[:6]
                    ),
                    "- 建议改动："
                    + "、".join(
                        cls._sanitize_user_visible_actions(
                            conversion_draft.plan_draft.proposed_changes
                        )[:6]
                    ),
                ]
            )
        if conversion_draft.task_draft is not None:
            lines.extend(
                [
                    f"- 任务草稿标题：{conversion_draft.task_draft.title}",
                    f"- 任务草稿摘要：{conversion_draft.task_draft.summary[:300]}",
                    f"- 输入摘要：{conversion_draft.task_draft.input_summary[:300]}",
                    "- 验收标准："
                    + "、".join(
                        cls._sanitize_user_visible_actions(
                            conversion_draft.task_draft.acceptance_criteria
                        )[:6]
                    ),
                    f"- 建议优先级：{conversion_draft.task_draft.suggested_priority}",
                ]
            )
        lines.extend(
            [
                "- 安全边界："
                + "、".join(
                    cls._sanitize_user_visible_actions(
                        conversion_draft.forbidden_actions
                    )[:7]
                ),
                "- 可做下一步："
                + "、".join(
                    cls._sanitize_user_visible_actions(
                        conversion_draft.safe_next_actions
                    )[:5]
                ),
            ]
        )
        return lines

    @classmethod
    def _provider_proposal_lines(
        cls,
        action_proposal: DirectorActionProposal | None,
    ) -> list[str]:
        if action_proposal is None:
            return []
        lines = [
            f"- 建议类型：{action_proposal.title}",
            f"- 建议摘要：{action_proposal.summary[:300]}",
            f"- 建议原因：{action_proposal.reason[:300]}",
            "- 审查要求："
            + _PROPOSAL_APPROVAL_LABELS_CN[action_proposal.approval_requirement],
            "- 这只是建议，不是已应用。",
            "- 不能声称已修改草案；不能声称已创建任务；不能声称已执行审批；不能声称已启动外部工具；不能把建议写成已处理完成。",
        ]
        if action_proposal.plan_revision is not None:
            lines.extend(
                [
                    f"- 修改建议标题：{action_proposal.plan_revision.title}",
                    f"- 修改建议摘要：{action_proposal.plan_revision.summary[:300]}",
                    "- 受影响内容："
                    + "、".join(
                        cls._sanitize_user_visible_actions(
                            action_proposal.plan_revision.affected_sections
                        )[:6]
                    ),
                    "- 建议改动："
                    + "、".join(
                        cls._sanitize_user_visible_actions(
                            action_proposal.plan_revision.proposed_changes
                        )[:6]
                    ),
                ]
            )
        lines.extend(
            [
                "- 安全边界："
                + "、".join(
                    cls._sanitize_user_visible_actions(
                        action_proposal.forbidden_actions
                    )[:6]
                ),
                "- 可做下一步："
                + "、".join(
                    cls._sanitize_user_visible_actions(
                        action_proposal.safe_next_actions
                    )[:5]
                ),
            ]
        )
        return lines

    @classmethod
    def _provider_challenge_lines(
        cls,
        challenge_seed: UserChallengeSeed | None,
    ) -> list[str]:
        if challenge_seed is None:
            return []
        return [
            f"- 反馈类型：{challenge_seed.title}",
            "- 严重程度："
            + _CHALLENGE_SEVERITY_LABELS_CN[challenge_seed.severity],
            f"- 摘要：{challenge_seed.summary[:300]}",
            f"- 提取原因：{challenge_seed.extracted_reason[:300]}",
            "- 安全边界："
            + "、".join(
                cls._sanitize_user_visible_actions(challenge_seed.forbidden_actions)[
                    :5
                ]
            ),
            "- 可做下一步："
            + "、".join(
                cls._sanitize_user_visible_actions(challenge_seed.safe_next_actions)[
                    :5
                ]
            ),
        ]

    @staticmethod
    def _provider_section_lines(
        assembly: DirectorContextAssembly | None,
    ) -> list[str]:
        if assembly is None:
            return []
        return [
            f"- {section.label}: {section.summary}"
            for section in assembly.sections[:10]
        ]

    @staticmethod
    def _json_compact(value: object, limit: int) -> str:
        if value is None:
            return "（无）"
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)
        return text[:limit]

    @staticmethod
    def _call_provider_text(
        *,
        runtime_config: object,
        model_name: str,
        prompt_text: str,
        request_id: str,
    ) -> tuple[str, str | None]:
        from app.services.openai_provider_executor_service import (
            OpenAIProviderExecutorService,
        )

        executor = OpenAIProviderExecutorService(
            **{"api" + "_key": getattr(runtime_config, "api" + "_key", "")},
            base_url=runtime_config.base_url,
            timeout_seconds=runtime_config.timeout_seconds,
        )
        response = executor.generate_text(
            model_name=model_name,
            prompt_text=prompt_text,
            request_id=request_id,
            prompt_key="project_director_chat_response",
            provider_key=runtime_config.detected_provider_type,
        )
        receipt_id = None
        if response.provider_usage_receipt is not None:
            receipt_id = response.provider_usage_receipt.receipt_id
        return response.output_text or response.summary, receipt_id
