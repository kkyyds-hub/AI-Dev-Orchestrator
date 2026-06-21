"""Project Director session and message request/response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_session import (
    ClarifyingAnswer,
    ClarifyingQuestion,
    ProjectDirectorSession,
    ProjectDirectorSessionStatus,
)


class CreateSessionRequest(BaseModel):
    goal_text: str = Field(min_length=1, max_length=5000)
    project_id: UUID | None = Field(default=None)
    constraints: str = Field(default="", max_length=3000)


class ClarifyingQuestionResponse(BaseModel):
    id: str
    question: str
    hint: str
    required: bool
    source: str = Field(default="rule_fallback")
    source_detail: str = Field(default="")

    @classmethod
    def from_domain(cls, q: ClarifyingQuestion) -> "ClarifyingQuestionResponse":
        return cls(
            id=q.id,
            question=q.question,
            hint=q.hint,
            required=q.required,
            source=q.source,
            source_detail=q.source_detail,
        )


class ClarifyingAnswerResponse(BaseModel):
    question_id: str
    answer: str

    @classmethod
    def from_domain(cls, a: ClarifyingAnswer) -> "ClarifyingAnswerResponse":
        return cls(question_id=a.question_id, answer=a.answer)


class SessionResponse(BaseModel):
    id: UUID
    project_id: UUID | None
    goal_text: str
    constraints: str
    status: ProjectDirectorSessionStatus
    clarifying_questions: list[ClarifyingQuestionResponse] = Field(default_factory=list)
    clarifying_answers: list[ClarifyingAnswerResponse] = Field(default_factory=list)
    goal_summary: str
    confirmed_at: str | None
    created_at: str
    updated_at: str
    next_action: str
    missing_info: list[str] = Field(default_factory=list)
    needs_user_confirmation: bool
    forbidden_actions: list[str] = Field(default_factory=list)
    gate_conclusion: str

    @classmethod
    def from_domain(cls, s: ProjectDirectorSession) -> "SessionResponse":
        next_action, missing_info, needs_confirmation, forbidden, gate = (
            _compute_contract_fields(s)
        )

        return cls(
            id=s.id,
            project_id=s.project_id,
            goal_text=s.goal_text,
            constraints=s.constraints,
            status=s.status,
            clarifying_questions=[
                ClarifyingQuestionResponse.from_domain(q)
                for q in s.clarifying_questions
            ],
            clarifying_answers=[
                ClarifyingAnswerResponse.from_domain(a)
                for a in s.clarifying_answers
            ],
            goal_summary=s.goal_summary,
            confirmed_at=s.confirmed_at.isoformat() if s.confirmed_at else None,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
            next_action=next_action,
            missing_info=missing_info,
            needs_user_confirmation=needs_confirmation,
            forbidden_actions=forbidden,
            gate_conclusion=gate,
        )


class SubmitAnswersRequest(BaseModel):
    answers: list[ClarifyingAnswer] = Field(min_length=1)


class ProjectDirectorMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: ProjectDirectorMessageRole
    content: str
    sequence_no: int
    intent: str | None = None
    related_plan_version_id: UUID | None = None
    related_project_id: UUID | None = None
    related_task_id: UUID | None = None
    source: ProjectDirectorMessageSource
    source_detail: str = ""
    suggested_actions: list[dict] = Field(default_factory=list)
    requires_confirmation: bool = False
    risk_level: ProjectDirectorMessageRiskLevel | None = None
    forbidden_actions_detected: list[str] = Field(default_factory=list)
    token_count: int | None = None
    estimated_cost: float | None = None
    created_at: str

    @classmethod
    def from_domain(
        cls, message: ProjectDirectorMessage
    ) -> "ProjectDirectorMessageResponse":
        return cls(
            id=message.id,
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            sequence_no=message.sequence_no,
            intent=message.intent,
            related_plan_version_id=message.related_plan_version_id,
            related_project_id=message.related_project_id,
            related_task_id=message.related_task_id,
            source=message.source,
            source_detail=message.source_detail,
            suggested_actions=message.suggested_actions,
            requires_confirmation=message.requires_confirmation,
            risk_level=message.risk_level,
            forbidden_actions_detected=message.forbidden_actions_detected,
            token_count=message.token_count,
            estimated_cost=message.estimated_cost,
            created_at=message.created_at.isoformat(),
        )


class ProjectDirectorMessageListResponse(BaseModel):
    session_id: UUID
    messages: list[ProjectDirectorMessageResponse] = Field(default_factory=list)
    has_more: bool = False


class PostProjectDirectorMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)


class PostProjectDirectorMessageResponse(BaseModel):
    session_id: UUID
    user_message: ProjectDirectorMessageResponse
    assistant_message: ProjectDirectorMessageResponse
    messages: list[ProjectDirectorMessageResponse]
    source: ProjectDirectorMessageSource = ProjectDirectorMessageSource.RULE_FALLBACK
    gate_conclusion: str = "Partial"
    forbidden_actions: list[str] = Field(
        default_factory=lambda: [
            "不启动 Worker",
            "不创建 Run",
            "不执行 planning/apply",
            "不执行 apply-local",
            "不写仓库",
            "不执行 suggested_actions",
        ]
    )


def _compute_contract_fields(
    s: ProjectDirectorSession,
) -> tuple[str, list[str], bool, list[str], str]:
    """Compute the output contract fields based on session state."""

    if s.status == ProjectDirectorSessionStatus.DRAFT:
        return (
            "系统正在生成澄清问题，请稍候",
            [],
            False,
            ["不生成计划", "不创建任务", "不调度 Worker", "不写仓库"],
            "Partial",
        )

    if s.status == ProjectDirectorSessionStatus.CLARIFYING:
        answered_count = len(s.clarifying_answers)
        total_required = sum(1 for q in s.clarifying_questions if q.required)
        missing: list[str] = []
        if s.clarifying_questions:
            answered_ids = {a.question_id for a in s.clarifying_answers}
            missing = [
                f"[必答] {q.question}"
                for q in s.clarifying_questions
                if q.required and q.id not in answered_ids
            ]
        if missing:
            return (
                f"请继续回答 {len(missing)} 个必答问题后提交答案",
                missing,
                True,
                ["不生成计划", "不创建任务", "不调度 Worker", "不写仓库"],
                "Partial",
            )
        return (
            f"已回答全部 {total_required} 个必答问题，请提交答案进入确认",
            [],
            True,
            ["不生成计划", "不创建任务", "不调度 Worker", "不写仓库"],
            "Partial",
        )

    if s.status == ProjectDirectorSessionStatus.READY_TO_CONFIRM:
        return (
            "请确认目标摘要，确认后将进入已确认状态（不会自动生成计划或创建任务）",
            ["用户确认"],
            True,
            [
                "不自动生成计划",
                "不自动创建任务",
                "不调度 Worker",
                "不写仓库",
                "不把确认等同于执行",
            ],
            "Partial",
        )

    if s.status == ProjectDirectorSessionStatus.CONFIRMED:
        return (
            "目标已确认。后续可进入 Plan Draft 阶段，但需单独触发",
            ["计划草案", "角色与 Skill 方案", "任务队列"],
            False,
            [
                "不自动生成计划（需单独触发）",
                "不自动创建任务",
                "不调度 Worker",
                "不写仓库",
            ],
            "Partial（目标闭环 Pass，总闭环未完成）",
        )

    return ("未知状态", [], False, [], "Partial")
