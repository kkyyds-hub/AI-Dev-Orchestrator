"""Session-scoped Project Director conversational message service.

Stage 7-B2: persists user messages, builds read-only context, and returns a
provider-first assistant chat response with explicit rule fallback. It does not
create runs, dispatch workers, execute planning/apply, apply-local, or perform
repository writes.
"""

from __future__ import annotations

from collections.abc import Callable
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
        assistant_content, source, source_detail = self._build_assistant_reply(
            user_content=trimmed_content,
            context=context,
        )

        assistant_message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=assistant_content,
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="general_discussion",
                related_project_id=session_obj.project_id,
                source=source,
                source_detail=source_detail,
                suggested_actions=[],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.LOW,
                forbidden_actions_detected=list(_FORBIDDEN_MESSAGE_ACTIONS),
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
    ) -> tuple[str, ProjectDirectorMessageSource, str]:
        provider_config_service = (
            self._provider_config_service or ProviderConfigService()
        )
        try:
            runtime_config = provider_config_service.resolve_openai_runtime_config()
        except Exception as exc:  # noqa: BLE001 - config failures must fallback safely
            return (
                self._build_fallback_reply(
                    user_content=user_content,
                    context=context,
                    reason=f"provider_config_unavailable:{exc}",
                ),
                ProjectDirectorMessageSource.RULE_FALLBACK,
                self._truncate_source_detail(
                    f"stage_7_b2_rule_fallback; reason=provider_config_unavailable:{exc}"
                ),
            )

        if not getattr(runtime_config, "api_key", None):
            return (
                self._build_fallback_reply(
                    user_content=user_content,
                    context=context,
                    reason="provider_not_configured",
                ),
                ProjectDirectorMessageSource.RULE_FALLBACK,
                "stage_7_b2_rule_fallback; reason=provider_not_configured",
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
            return (
                self._build_fallback_reply(
                    user_content=user_content,
                    context=context,
                    reason=f"provider_generation_failed:{exc}",
                ),
                ProjectDirectorMessageSource.RULE_FALLBACK,
                self._truncate_source_detail(
                    f"stage_7_b2_rule_fallback; reason=provider_generation_failed:{exc}"
                ),
            )

        cleaned_output = output_text.strip()
        if not cleaned_output:
            return (
                self._build_fallback_reply(
                    user_content=user_content,
                    context=context,
                    reason="provider_empty_output",
                ),
                ProjectDirectorMessageSource.RULE_FALLBACK,
                "stage_7_b2_rule_fallback; reason=provider_empty_output",
            )

        return (
            cleaned_output[:10_000],
            ProjectDirectorMessageSource.AI,
            self._truncate_source_detail(
                f"stage_7_b2_provider_chat; provider={runtime_config.detected_provider_type}; "
                f"model={model_name}; receipt={receipt_id or 'missing'}"
            ),
        )

    @staticmethod
    def _truncate_source_detail(value: str) -> str:
        return value[:300]

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
        return (
            "已记录你的消息，并基于当前 Project Director 会话上下文给出规则 fallback 回复。"
            f"当前会话状态为 {context.session_status}，目标为：{context.goal_text}。"
            f"计划上下文：{plan_status}；任务数量：{task_total}。"
            f"fallback 原因：{reason}。"
            "本回复不会启动 Worker、创建 Run、执行 planning/apply、执行 apply-local 或写仓库。"
            f"你的消息摘要：{user_content[:240]}"
        )

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
                f"Latest Plan Version: {context.latest_plan_version}",
                f"Project Snapshot: {context.project_snapshot}",
                f"Task Snapshot: {context.task_snapshot}",
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
