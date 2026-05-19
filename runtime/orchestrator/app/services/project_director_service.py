"""AI Project Director service — goal intake, clarification, confirmation.

Phase 1: deterministic rule-based clarification (no AI, no Provider).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.project_director_session import (
    ClarifyingAnswer,
    ClarifyingQuestion,
    ProjectDirectorSession,
    ProjectDirectorSessionStatus,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)


# ── Deterministic clarification rule sets ──────────────────────────

def _generate_clarifying_questions(
    goal_text: str, constraints: str
) -> list[ClarifyingQuestion]:
    """Generate clarifying questions using deterministic keyword rules.

    No AI, no Provider — purely rule-based analysis of the input text.
    """

    questions: list[ClarifyingQuestion] = []
    text_lower = goal_text.lower()
    char_count = len(goal_text.strip())

    # 1. Very short goal → ask for more detail
    # Use character count as a language-agnostic measure (Chinese text
    # would be misjudged as "short" by word-count alone).
    if char_count < 20:
        questions.append(
            ClarifyingQuestion(
                question=(
                    "你的目标描述比较简短。能否补充更多细节？"
                    "例如：你希望实现什么功能、解决什么问题、"
                    "预期的最终效果是什么？"
                ),
                hint="请用 2-5 句话描述目标",
            )
        )

    # 2. No scope keywords → ask about boundaries
    scope_keywords = ["范围", "scope", "只做", "不做", "包括", "边界", "限制"]
    if not any(kw in text_lower for kw in scope_keywords):
        questions.append(
            ClarifyingQuestion(
                question=(
                    "请明确本次目标的范围和边界：哪些内容是必须完成的？"
                    "哪些内容明确不在本次范围内？"
                ),
                hint="明确范围和「不做」的边界",
            )
        )

    # 3. No acceptance criteria → ask about success measurement
    acceptance_keywords = [
        "验收", "标准", "完成", "通过", "测试", "验证",
        "acceptance", "criteria", "done", "test", "verify",
    ]
    if not any(kw in text_lower for kw in acceptance_keywords):
        questions.append(
            ClarifyingQuestion(
                question=(
                    "你如何判断目标已经完成？请描述 2-3 条关键的验收标准。"
                ),
                hint="具体可衡量的完成标准",
            )
        )

    # 4. Technical keywords → ask about constraints
    tech_keywords = [
        "build", "构建", "开发", "实现", "implement", "代码", "code",
        "api", "接口", "前端", "frontend", "后端", "backend",
        "数据库", "database", "部署", "deploy",
    ]
    if any(kw in text_lower for kw in tech_keywords):
        questions.append(
            ClarifyingQuestion(
                question=(
                    "是否有技术栈、框架或工具的约束？"
                    "例如：必须使用某个语言、数据库、或部署环境？"
                ),
                hint="技术栈约束，无约束可答「无特殊要求」",
            )
        )

    # 5. No priority/time mention → ask about timeline
    time_keywords = [
        "时间", "优先级", "priority", "截止", "deadline",
        "紧急", "urgent", "阶段", "phase", "迭代",
    ]
    if not any(kw in text_lower for kw in time_keywords):
        questions.append(
            ClarifyingQuestion(
                question=(
                    "你对时间或优先级有什么要求？"
                    "是否有关键截止日期或必须优先完成的部分？"
                ),
                hint="时间线/优先级，无要求可答「无特殊时间要求」",
            )
        )

    # 6. No risk mention → ask about risks
    risk_keywords = ["风险", "risk", "依赖", "阻塞", "block", "问题"]
    if not any(kw in text_lower for kw in risk_keywords):
        questions.append(
            ClarifyingQuestion(
                question=(
                    "你预见到哪些潜在风险或依赖？"
                    "例如：是否依赖其他团队、外部服务、或特定数据？"
                ),
                hint="已知风险或依赖，无可答「暂未发现」",
            )
        )

    # Ensure we have at least 3 questions even for well-described goals
    if len(questions) < 3:
        questions.append(
            ClarifyingQuestion(
                question=(
                    "请描述目标完成后的理想状态："
                    "用户/系统/业务会有什么不同？"
                ),
                hint="描述成功后的最终效果",
            )
        )

    return questions


def _generate_goal_summary(
    goal_text: str,
    constraints: str,
    questions: list[ClarifyingQuestion],
    answers: list[ClarifyingAnswer],
) -> str:
    """Build a structured goal summary from the goal, questions, and answers."""

    answer_map = {a.question_id: a.answer for a in answers}

    parts: list[str] = []
    parts.append("## 目标摘要\n")
    parts.append(goal_text.strip())

    if constraints.strip():
        parts.append("\n## 约束条件\n")
        parts.append(constraints.strip())

    parts.append("\n## 澄清结果\n")
    for q in questions:
        answer = answer_map.get(q.id, "（未回答）")
        parts.append(f"- **{q.question}**\n  答：{answer}")

    parts.append("\n## 确认状态\n")
    parts.append("以上摘要由 AI 项目主管根据用户回答整理，待用户确认。")

    return "\n".join(parts)


# ── Service ────────────────────────────────────────────────────────


class ProjectDirectorService:
    """Business logic for AI Project Director sessions."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository,
    ) -> None:
        self._session_repo = session_repository

    def create_session(
        self,
        *,
        goal_text: str,
        project_id: UUID | None = None,
        constraints: str = "",
    ) -> ProjectDirectorSession:
        """Create a new Project Director session and generate clarifying questions."""

        if not goal_text.strip():
            raise ValueError("goal_text must not be empty or whitespace-only")

        questions = _generate_clarifying_questions(goal_text, constraints)

        now = datetime.now(timezone.utc)
        session_obj = ProjectDirectorSession(
            id=uuid4(),
            project_id=project_id,
            goal_text=goal_text.strip(),
            constraints=constraints.strip(),
            status=ProjectDirectorSessionStatus.CLARIFYING,
            clarifying_questions=questions,
            clarifying_answers=[],
            goal_summary="",
            confirmed_at=None,
            created_at=now,
            updated_at=now,
        )

        return self._session_repo.create(session_obj)

    def get_session(self, session_id: UUID) -> ProjectDirectorSession | None:
        """Return the session or None."""
        return self._session_repo.get_by_id(session_id)

    def submit_answers(
        self,
        session_id: UUID,
        answers: list[ClarifyingAnswer],
    ) -> ProjectDirectorSession:
        """Submit user answers to clarifying questions.

        If all required questions are answered → ready_to_confirm.
        If any required question is still unanswered → stays clarifying.
        """

        session_obj = self._session_repo.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Session {session_id} not found")

        if session_obj.status != ProjectDirectorSessionStatus.CLARIFYING:
            raise ValueError(
                f"Session is in '{session_obj.status}' status, "
                f"expected 'clarifying' to submit answers"
            )

        # Validate that all answer question_ids match existing questions
        valid_q_ids = {q.id for q in session_obj.clarifying_questions}
        for answer in answers:
            if answer.question_id not in valid_q_ids:
                raise ValueError(
                    f"Answer references unknown question_id: {answer.question_id}"
                )

        # Merge answers: replace existing answers for the same question_id
        existing_map = {a.question_id: a for a in session_obj.clarifying_answers}
        for answer in answers:
            existing_map[answer.question_id] = answer

        merged_answers = list(existing_map.values())

        # Determine status: only ready_to_confirm if ALL required are answered
        answered_ids = {a.question_id for a in merged_answers}
        all_required_answered = all(
            q.id in answered_ids
            for q in session_obj.clarifying_questions
            if q.required
        )

        new_status = (
            ProjectDirectorSessionStatus.READY_TO_CONFIRM
            if all_required_answered
            else ProjectDirectorSessionStatus.CLARIFYING
        )

        # Generate goal summary
        goal_summary = _generate_goal_summary(
            goal_text=session_obj.goal_text,
            constraints=session_obj.constraints,
            questions=session_obj.clarifying_questions,
            answers=merged_answers,
        )

        updated = ProjectDirectorSession(
            id=session_obj.id,
            project_id=session_obj.project_id,
            goal_text=session_obj.goal_text,
            constraints=session_obj.constraints,
            status=new_status,
            clarifying_questions=session_obj.clarifying_questions,
            clarifying_answers=merged_answers,
            goal_summary=goal_summary,
            confirmed_at=None,
            created_at=session_obj.created_at,
            updated_at=datetime.now(timezone.utc),
        )

        return self._session_repo.update(updated)

    def confirm_goal(self, session_id: UUID) -> ProjectDirectorSession:
        """Confirm the goal summary.

        Transitions status: ready_to_confirm → confirmed.
        Requires all required clarifying questions to be answered.
        """

        session_obj = self._session_repo.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Session {session_id} not found")

        if session_obj.status == ProjectDirectorSessionStatus.CONFIRMED:
            # Already confirmed — idempotent, return as-is
            return session_obj

        # Validate all required questions are answered
        answered_ids = {a.question_id for a in session_obj.clarifying_answers}
        unanswered_required = [
            q for q in session_obj.clarifying_questions
            if q.required and q.id not in answered_ids
        ]
        if unanswered_required:
            raise ValueError(
                "Cannot confirm: the following required questions have not been answered: "
                + "; ".join(q.question[:80] for q in unanswered_required)
            )

        if session_obj.status != ProjectDirectorSessionStatus.READY_TO_CONFIRM:
            raise ValueError(
                f"Session is in '{session_obj.status}' status, "
                f"expected 'ready_to_confirm' to confirm goal"
            )

        updated = ProjectDirectorSession(
            id=session_obj.id,
            project_id=session_obj.project_id,
            goal_text=session_obj.goal_text,
            constraints=session_obj.constraints,
            status=ProjectDirectorSessionStatus.CONFIRMED,
            clarifying_questions=session_obj.clarifying_questions,
            clarifying_answers=session_obj.clarifying_answers,
            goal_summary=session_obj.goal_summary,
            confirmed_at=datetime.now(timezone.utc),
            created_at=session_obj.created_at,
            updated_at=datetime.now(timezone.utc),
        )

        return self._session_repo.update(updated)
