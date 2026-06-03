"""Session-scoped Project Director conversational message service.

Stage 7-B1 foundation only: persists user messages and returns a deterministic
assistant fallback. It does not call AI providers, create runs, dispatch workers,
execute planning/apply, or perform repository writes.
"""

from __future__ import annotations

from uuid import UUID

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


class ProjectDirectorMessageService:
    """Conversation persistence and deterministic assistant fallback."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
        message_repository: ProjectDirectorMessageRepository,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository

    def list_messages(
        self,
        *,
        session_id: UUID,
        limit: int = 200,
    ) -> list[ProjectDirectorMessage]:
        self._ensure_session_exists(session_id)
        return self._message_repository.list_by_session_id(
            session_id=session_id,
            limit=limit,
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

        assistant_message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=self._build_fallback_reply(
                    user_content=trimmed_content,
                    session_status=session_obj.status.value,
                    goal_text=session_obj.goal_text,
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="general_discussion",
                related_project_id=session_obj.project_id,
                source=ProjectDirectorMessageSource.RULE_FALLBACK,
                source_detail="stage_7_b1_deterministic_conversation_foundation",
                suggested_actions=[],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.LOW,
                forbidden_actions_detected=[
                    "不启动 Worker",
                    "不创建 Run",
                    "不调用 Provider",
                    "不执行 planning/apply",
                    "不执行 apply-local",
                    "不写仓库",
                ],
            )
        )
        self._message_repository.commit()
        return user_message, assistant_message

    def _ensure_session_exists(self, session_id: UUID):
        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")
        return session_obj

    @staticmethod
    def _build_fallback_reply(
        *,
        user_content: str,
        session_status: str,
        goal_text: str,
    ) -> str:
        return (
            "已记录你的消息，并基于当前 Project Director 会话状态给出基础回复。"
            f"当前会话状态为 {session_status}，目标为：{goal_text}。"
            "Stage 7-B1 仅启用消息持久化与规则 fallback 回复；"
            "不会启动 Worker、创建 Run、调用 Provider、执行 planning/apply 或写仓库。"
            f"你的消息摘要：{user_content[:240]}"
        )
