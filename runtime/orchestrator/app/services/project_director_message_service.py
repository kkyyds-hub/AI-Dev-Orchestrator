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

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
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
from app.services.provider_config_service import ProviderConfigService


ProviderTextGenerator = Callable[[str, str, str], tuple[str, str | None]]

_FORBIDDEN_MESSAGE_ACTIONS = [
    "不启动 Worker",
    "不创建 Run",
    "不执行 planning/apply",
    "不执行 apply-local",
    "不写仓库",
    "不执行 suggested_actions",
]


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

        context = self._context_builder.build_context(session_id=session_id)
        assistant_reply = self._build_assistant_reply(
            user_content=trimmed_content,
            context=context,
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

    def _ensure_session_exists(self, session_id: UUID):
        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")
        return session_obj

    def _build_assistant_reply(
        self,
        *,
        user_content: str,
        context: ProjectDirectorConversationContext,
    ) -> ChatGenerationResult:
        provider_config_service = (
            self._provider_config_service or ProviderConfigService()
        )
        try:
            runtime_config = provider_config_service.resolve_openai_runtime_config()
        except Exception as exc:  # noqa: BLE001 - config failures must fallback safely
            return ChatGenerationResult(
                content=self._build_fallback_reply(
                    user_content=user_content,
                    context=context,
                    reason=f"provider_config_unavailable:{exc}",
                ),
                source=ProjectDirectorMessageSource.RULE_FALLBACK,
                source_detail=self._truncate_source_detail(
                    f"stage_7_b2_rule_fallback; reason=provider_config_unavailable:{exc}"
                ),
                related_plan_version_id=self._context_plan_version_id(context),
                forbidden_actions_detected=list(_FORBIDDEN_MESSAGE_ACTIONS),
            )

        if not getattr(runtime_config, "api_key", None):
            return ChatGenerationResult(
                content=self._build_fallback_reply(
                    user_content=user_content,
                    context=context,
                    reason="provider_not_configured",
                ),
                source=ProjectDirectorMessageSource.RULE_FALLBACK,
                source_detail="stage_7_b2_rule_fallback; reason=provider_not_configured",
                related_plan_version_id=self._context_plan_version_id(context),
                forbidden_actions_detected=list(_FORBIDDEN_MESSAGE_ACTIONS),
            )

        model_name = runtime_config.model_names.get(
            "balanced",
            next(iter(runtime_config.model_names.values()), "gpt-5.5"),
        )
        prompt_text = self._build_provider_prompt(
            user_content=user_content,
            context=context,
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
            return ChatGenerationResult(
                content=self._build_fallback_reply(
                    user_content=user_content,
                    context=context,
                    reason=f"provider_generation_failed:{exc}",
                ),
                source=ProjectDirectorMessageSource.RULE_FALLBACK,
                source_detail=self._truncate_source_detail(
                    f"stage_7_b2_rule_fallback; reason=provider_generation_failed:{exc}"
                ),
                related_plan_version_id=self._context_plan_version_id(context),
                forbidden_actions_detected=list(_FORBIDDEN_MESSAGE_ACTIONS),
            )

        cleaned_output = output_text.strip()
        if not cleaned_output:
            return ChatGenerationResult(
                content=self._build_fallback_reply(
                    user_content=user_content,
                    context=context,
                    reason="provider_empty_output",
                ),
                source=ProjectDirectorMessageSource.RULE_FALLBACK,
                source_detail="stage_7_b2_rule_fallback; reason=provider_empty_output",
                related_plan_version_id=self._context_plan_version_id(context),
                forbidden_actions_detected=list(_FORBIDDEN_MESSAGE_ACTIONS),
            )

        try:
            parsed_reply = self._parse_provider_reply_contract(
                cleaned_output,
                context=context,
            )
        except ValueError as exc:
            return ChatGenerationResult(
                content=self._build_fallback_reply(
                    user_content=user_content,
                    context=context,
                    reason=f"provider_contract_invalid:{exc}",
                ),
                source=ProjectDirectorMessageSource.RULE_FALLBACK,
                source_detail=self._truncate_source_detail(
                    f"stage_7_b2_rule_fallback; reason=provider_contract_invalid:{exc}"
                ),
                related_plan_version_id=self._context_plan_version_id(context),
                forbidden_actions_detected=list(_FORBIDDEN_MESSAGE_ACTIONS),
            )

        return ChatGenerationResult(
            content=parsed_reply.content,
            source=ProjectDirectorMessageSource.AI,
            source_detail=self._truncate_source_detail(
                "stage_7_b2_provider_chat; "
                f"provider={runtime_config.detected_provider_type}; "
                f"model={model_name}; receipt={receipt_id or 'missing'}"
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
        ]
        return [phrase for phrase in forbidden_phrases if phrase in answer]

    @staticmethod
    def _sanitize_suggested_actions(raw_actions: object) -> list[dict]:
        if not isinstance(raw_actions, list):
            return []
        sanitized: list[dict] = []
        allowed_types = {
            "summarize",
            "explain",
            "navigate",
            "request_changes",
            "create_formal_project",
            "run_worker_once",
            "none",
        }
        for raw_action in raw_actions[:5]:
            if not isinstance(raw_action, dict):
                continue
            action_type = str(raw_action.get("type", "none")).strip() or "none"
            if action_type not in allowed_types:
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
                    "label": str(raw_action.get("label", "建议操作")).strip()[:120],
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

    @staticmethod
    def _build_fallback_reply(
        *,
        user_content: str,
        context: ProjectDirectorConversationContext,
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
                f"已读取到任务创建记录：项目 {context.task_creation.get('project_name') or context.task_creation.get('project_id')}，"
                f"任务数 {context.task_creation.get('task_count')}。"
            )

        lines = [
            "已记录你的消息。当前 Provider 不可用或输出不符合安全合同，因此使用规则 fallback 回复。",
            f"fallback 原因：{reason}。",
            f"当前会话状态：{context.session_status}；目标：{context.goal_text}。",
            f"澄清问题：{len(context.clarifying_questions)} 个；已回答：{len(context.clarifying_answers)} 个。",
            f"计划上下文：{plan_status}；任务快照数量：{task_total}。",
            task_creation_line,
        ]
        if plan_summary:
            lines.append(f"草案摘要：{plan_summary[:600]}")
        if phase_names:
            lines.append("阶段概览：" + "、".join(phase_names))
        if proposed_task_titles:
            lines.append("拟议任务：" + "、".join(proposed_task_titles))
        if risks:
            lines.append("主要风险：" + "；".join(risks))
        lines.extend(
            [
                "建议下一步：如果你在总结草案，可先审核阶段、拟议任务、风险与验收标准；如要创建正式项目或启动执行，仍需通过单独按钮/确认链路触发。",
                "本回复不会启动 Worker、创建 Run、执行 planning/apply、执行 apply-local、写仓库或执行 suggested_actions。",
                f"你的消息摘要：{user_content[:240]}",
            ]
        )
        return "\n".join(lines)[:10_000]

    @staticmethod
    def _build_provider_prompt(
        *,
        user_content: str,
        context: ProjectDirectorConversationContext,
    ) -> str:
        recent_lines = [
            f"- #{message.sequence_no} {message.role.value}: {message.content[:500]}"
            for message in context.recent_messages
        ]
        return "\n".join(
            [
                "你是 AI Project Director 的对话大脑。请基于只读上下文回答用户。",
                "硬性边界：不得声称已经启动 Worker、创建 Run、执行 planning/apply、执行 apply-local、写仓库或执行 suggested_actions。",
                "如建议后续动作，只能描述为需要用户显式确认/单独触发的建议。",
                f"Session ID: {context.session_id}",
                f"Project ID: {context.project_id}",
                f"Session Status: {context.session_status}",
                f"Goal: {context.goal_text}",
                f"Constraints: {context.constraints or '（无）'}",
                f"Goal Summary: {context.goal_summary or '（无）'}",
                f"Clarifying Answers: {context.clarifying_answers}",
                f"Clarifying Questions: {context.clarifying_questions}",
                f"Latest Plan Version: {context.latest_plan_version}",
                f"Task Creation: {context.task_creation}",
                f"Project Snapshot: {context.project_snapshot}",
                f"Task Snapshot: {context.task_snapshot}",
                "Provider Output Contract: return one JSON object only with keys: "
                "intent, answer, related_plan_version_id, suggested_actions, "
                "requires_confirmation, risk_level, forbidden_actions_detected. "
                "The answer must be Chinese user-facing text grounded in the context.",
                "Recent Messages:",
                *(recent_lines or ["- （无）"]),
                f"User Message: {user_content}",
            ]
        )

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
