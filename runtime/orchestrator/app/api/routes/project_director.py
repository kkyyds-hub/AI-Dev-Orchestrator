"""AI Project Director session, plan version & confirmation inbox API routes.

BCG-01: goal intake → clarification → confirmation.
BCG-02: provider-first plan draft generation with rule_fallback
        → pending_confirmation → confirmed.
BCG-03: pending confirmation inbox (read-only aggregation).
BCG-04A: confirmed plan version → real task queue creation.
Plan draft generation is review-only: it does not create tasks, dispatch
workers, call planning/apply, or write repositories.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.project_director_plan_version import (
    AgentTeamSuggestion as AgentTeamSuggestionDomain,
    ComplexityAssessment as ComplexityAssessmentDomain,
    DeliverableBoundary as DeliverableBoundaryDomain,
    PlanPhase as PlanPhaseDomain,
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
    ProjectScopeSummary as ProjectScopeSummaryDomain,
    ProposedTask as ProposedTaskDomain,
    RepositoryBindingSuggestion as RepositoryBindingSuggestionDomain,
    SkillBindingSuggestion as SkillBindingSuggestionDomain,
    VerificationMechanismSuggestion as VerificationMechanismSuggestionDomain,
)
from app.domain.project_director_agent_team_config import (
    AgentTeamConfigStatus,
    ProjectDirectorAgentTeamConfig,
    ProjectDirectorAgentTeamMemberConfig,
)
from app.domain.project_director_repository_binding_config import (
    ProjectDirectorRepositoryBindingConfig,
    ProjectDirectorRepositoryBindingConfigItem,
    RepositoryBindingConfigStatus,
)
from app.domain.project_director_skill_binding_config import (
    ProjectDirectorSkillBindingConfig,
    ProjectDirectorSkillBindingConfigItem,
    SkillBindingConfigStatus,
)
from app.domain.project_director_verification_config import (
    ProjectDirectorVerificationConfig,
    ProjectDirectorVerificationConfigItem,
    VerificationConfigStatus,
)
from app.domain.project_director_session import (
    ClarifyingAnswer,
    ClarifyingQuestion,
    ProjectDirectorSessionStatus,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_task_creation_repository import (
    ProjectDirectorTaskCreationRecordRepository,
)
from app.repositories.project_director_agent_team_config_repository import (
    ProjectDirectorAgentTeamConfigRepository,
)
from app.repositories.project_director_repository_binding_config_repository import (
    ProjectDirectorRepositoryBindingConfigRepository,
)
from app.repositories.project_director_skill_binding_config_repository import (
    ProjectDirectorSkillBindingConfigRepository,
)
from app.repositories.project_director_verification_config_repository import (
    ProjectDirectorVerificationConfigRepository,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_confirmation_service import (
    ProjectDirectorConfirmationService,
)
from app.services.project_director_context_builder_service import (
    ProjectDirectorContextBuilderService,
)
from app.services.project_director_plan_service import (
    ProjectDirectorPlanGenerationError,
    ProjectDirectorPlanService,
)
from app.services.project_director_service import ProjectDirectorService
from app.services.project_director_message_service import ProjectDirectorMessageService
from app.services.project_director_conversation_service import (
    ConversationDetail,
    ConversationKind,
    ConversationListItem,
    ConversationStatus,
    ConversationTimelineItem,
    ProjectDirectorConversationService,
)
from app.services.project_director_task_creation_service import (
    ProjectDirectorTaskCreationService,
)
from app.services.project_director_agent_team_config_service import (
    AgentTeamConfigReadResult,
    ProjectDirectorAgentTeamConfigService,
)
from app.services.project_director_repository_binding_config_service import (
    ProjectDirectorRepositoryBindingConfigService,
    RepositoryBindingConfigReadResult,
)
from app.services.project_director_skill_binding_config_service import (
    ProjectDirectorSkillBindingConfigService,
    SkillBindingConfigReadResult,
)
from app.services.project_director_verification_config_service import (
    ProjectDirectorVerificationConfigService,
    VerificationConfigReadResult,
)
from app.services.project_director_setup_readiness_service import (
    ProjectDirectorSetupReadiness,
    ProjectDirectorSetupReadinessService,
)


# ── Dependencies ────────────────────────────────────────────────────


def _get_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorService:
    repo = ProjectDirectorSessionRepository(session)
    return ProjectDirectorService(session_repository=repo)


def _get_message_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorMessageService:
    session_repo = ProjectDirectorSessionRepository(session)
    message_repo = ProjectDirectorMessageRepository(session)
    context_builder = ProjectDirectorContextBuilderService(
        session_repository=session_repo,
        message_repository=message_repo,
        plan_version_repository=ProjectDirectorPlanVersionRepository(session),
        task_creation_repository=ProjectDirectorTaskCreationRecordRepository(session),
        project_repository=ProjectRepository(session),
        task_repository=TaskRepository(session),
    )
    return ProjectDirectorMessageService(
        session_repository=session_repo,
        message_repository=message_repo,
        context_builder=context_builder,
    )


def _get_plan_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorPlanService:
    plan_repo = ProjectDirectorPlanVersionRepository(session)
    session_repo = ProjectDirectorSessionRepository(session)
    return ProjectDirectorPlanService(
        plan_version_repository=plan_repo,
        session_repository=session_repo,
    )


def _get_confirmation_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorConfirmationService:
    session_repo = ProjectDirectorSessionRepository(session)
    plan_repo = ProjectDirectorPlanVersionRepository(session)
    return ProjectDirectorConfirmationService(
        session_repository=session_repo,
        plan_version_repository=plan_repo,
    )


def _get_task_creation_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorTaskCreationService:
    plan_repo = ProjectDirectorPlanVersionRepository(session)
    task_repo = TaskRepository(session)
    creation_repo = ProjectDirectorTaskCreationRecordRepository(session)
    project_repo = ProjectRepository(session)
    agent_team_config_repo = ProjectDirectorAgentTeamConfigRepository(session)
    skill_binding_config_repo = ProjectDirectorSkillBindingConfigRepository(session)
    repository_binding_config_repo = ProjectDirectorRepositoryBindingConfigRepository(
        session
    )
    verification_config_repo = ProjectDirectorVerificationConfigRepository(session)
    return ProjectDirectorTaskCreationService(
        plan_repo=plan_repo,
        task_repo=task_repo,
        creation_repo=creation_repo,
        project_repo=project_repo,
        agent_team_config_repo=agent_team_config_repo,
        skill_binding_config_repo=skill_binding_config_repo,
        repository_binding_config_repo=repository_binding_config_repo,
        verification_config_repo=verification_config_repo,
    )


def _get_agent_team_config_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorAgentTeamConfigService:
    config_repo = ProjectDirectorAgentTeamConfigRepository(session)
    project_repo = ProjectRepository(session)
    return ProjectDirectorAgentTeamConfigService(
        config_repo=config_repo,
        project_repo=project_repo,
    )


def _get_skill_binding_config_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorSkillBindingConfigService:
    config_repo = ProjectDirectorSkillBindingConfigRepository(session)
    project_repo = ProjectRepository(session)
    return ProjectDirectorSkillBindingConfigService(
        config_repo=config_repo,
        project_repo=project_repo,
    )


def _get_repository_binding_config_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorRepositoryBindingConfigService:
    config_repo = ProjectDirectorRepositoryBindingConfigRepository(session)
    project_repo = ProjectRepository(session)
    return ProjectDirectorRepositoryBindingConfigService(
        config_repo=config_repo,
        project_repo=project_repo,
    )


def _get_verification_config_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorVerificationConfigService:
    config_repo = ProjectDirectorVerificationConfigRepository(session)
    project_repo = ProjectRepository(session)
    return ProjectDirectorVerificationConfigService(
        config_repo=config_repo,
        project_repo=project_repo,
    )


def _get_setup_readiness_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorSetupReadinessService:
    project_repo = ProjectRepository(session)
    task_repo = TaskRepository(session)
    agent_team_config_repo = ProjectDirectorAgentTeamConfigRepository(session)
    skill_binding_config_repo = ProjectDirectorSkillBindingConfigRepository(session)
    repository_binding_config_repo = ProjectDirectorRepositoryBindingConfigRepository(
        session
    )
    verification_config_repo = ProjectDirectorVerificationConfigRepository(session)
    return ProjectDirectorSetupReadinessService(
        session=session,
        project_repo=project_repo,
        task_repo=task_repo,
        agent_team_config_repo=agent_team_config_repo,
        skill_binding_config_repo=skill_binding_config_repo,
        repository_binding_config_repo=repository_binding_config_repo,
        verification_config_repo=verification_config_repo,
    )


# ── Request / Response DTOs ─────────────────────────────────────────


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
    def from_domain(cls, s: "ProjectDirectorSession") -> "SessionResponse":  # noqa: F821
        from app.domain.project_director_session import ProjectDirectorSession

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
    def from_domain(cls, message: ProjectDirectorMessage) -> "ProjectDirectorMessageResponse":
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


# ── Contract field computation ──────────────────────────────────────


def _compute_contract_fields(
    s: "ProjectDirectorSession",  # noqa: F821
) -> tuple[str, list[str], bool, list[str], str]:
    """Compute the output contract fields based on session state.

    Returns: (next_action, missing_info, needs_user_confirmation, forbidden_actions, gate_conclusion)
    """

    from app.domain.project_director_session import ProjectDirectorSession

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


# ── Router ──────────────────────────────────────────────────────────


router = APIRouter(
    prefix="/project-director",
    tags=["project-director"],
)


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Project Director session",
)
def create_session(
    request: CreateSessionRequest,
    service: Annotated[ProjectDirectorService, Depends(_get_service)],
) -> SessionResponse:
    """Submit a user goal and receive clarifying questions.

    The session starts in `clarifying` status. Provider-generated
    clarification is preferred when configured; otherwise each returned
    question is explicitly marked as `source=rule_fallback`.
    """

    if not request.goal_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="goal_text must not be empty or whitespace-only",
        )

    try:
        session_obj = service.create_session(
            goal_text=request.goal_text,
            project_id=request.project_id,
            constraints=request.constraints,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return SessionResponse.from_domain(session_obj)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="Get a Project Director session",
)
def get_session(
    session_id: UUID,
    service: Annotated[ProjectDirectorService, Depends(_get_service)],
) -> SessionResponse:
    """Read the full session detail including clarifying questions, answers, and contract fields."""

    session_obj = service.get_session(session_id)
    if session_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project Director session {session_id} not found",
        )

    return SessionResponse.from_domain(session_obj)


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ProjectDirectorMessageListResponse,
    summary="List Project Director session messages",
)
def list_session_messages(
    session_id: UUID,
    message_service: Annotated[
        ProjectDirectorMessageService, Depends(_get_message_service)
    ],
    limit: int = 50,
    before: UUID | None = None,
) -> ProjectDirectorMessageListResponse:
    """Return persisted conversation messages for one Project Director session."""

    safe_limit = max(1, min(limit, 500))
    try:
        messages, has_more = message_service.list_messages(
            session_id=session_id,
            limit=safe_limit,
            before_message_id=before,
        )
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    return ProjectDirectorMessageListResponse(
        session_id=session_id,
        messages=[ProjectDirectorMessageResponse.from_domain(m) for m in messages],
        has_more=has_more,
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=PostProjectDirectorMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Persist a Project Director user message and fallback assistant reply",
)
def post_session_message(
    session_id: UUID,
    request: PostProjectDirectorMessageRequest,
    message_service: Annotated[
        ProjectDirectorMessageService, Depends(_get_message_service)
    ],
) -> PostProjectDirectorMessageResponse:
    """Persist one user message and one provider-first assistant chat reply.

    Stage 7-B2: this endpoint may call the configured Provider for a chat
    response and explicitly falls back to rules when unavailable/failing. It
    does not create runs, dispatch workers, execute planning/apply, execute
    apply-local, execute suggested_actions, or write repositories.
    """

    try:
        user_message, assistant_message = message_service.post_user_message(
            session_id=session_id,
            content=request.content,
        )
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    return PostProjectDirectorMessageResponse(
        session_id=session_id,
        user_message=ProjectDirectorMessageResponse.from_domain(user_message),
        assistant_message=ProjectDirectorMessageResponse.from_domain(assistant_message),
        messages=[
            ProjectDirectorMessageResponse.from_domain(user_message),
            ProjectDirectorMessageResponse.from_domain(assistant_message),
        ],
        source=assistant_message.source,
    )


@router.post(
    "/sessions/{session_id}/answers",
    response_model=SessionResponse,
    summary="Submit answers to clarifying questions",
)
def submit_answers(
    session_id: UUID,
    request: SubmitAnswersRequest,
    service: Annotated[ProjectDirectorService, Depends(_get_service)],
) -> SessionResponse:
    """Submit user answers to the clarifying questions.

    Transitions the session from `clarifying` to `ready_to_confirm`.
    A goal summary is generated from the answers.
    """

    try:
        session_obj = service.submit_answers(
            session_id=session_id,
            answers=request.answers,
        )
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "expected 'clarifying'" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    return SessionResponse.from_domain(session_obj)


@router.post(
    "/sessions/{session_id}/confirm",
    response_model=SessionResponse,
    summary="Confirm the goal summary",
)
def confirm_goal(
    session_id: UUID,
    service: Annotated[ProjectDirectorService, Depends(_get_service)],
) -> SessionResponse:
    """Confirm the goal summary.

    Transitions the session from `ready_to_confirm` to `confirmed`.
    All required clarifying questions must be answered first.
    Confirmed does NOT auto-generate plans or create tasks.
    Re-confirming an already confirmed session is idempotent.
    """

    try:
        session_obj = service.confirm_goal(session_id=session_id)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "cannot confirm" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if "expected 'ready_to_confirm'" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    return SessionResponse.from_domain(session_obj)


# ── Plan Version DTOs ────────────────────────────────────────────────


class PlanPhaseResponse(BaseModel):
    sequence: int
    name: str
    goal: str
    task_count_hint: int

    @classmethod
    def from_domain(cls, p: PlanPhaseDomain) -> "PlanPhaseResponse":
        return cls(
            sequence=p.sequence,
            name=p.name,
            goal=p.goal,
            task_count_hint=p.task_count_hint,
        )


class ProposedTaskResponse(BaseModel):
    title: str
    description: str
    suggested_role_code: str
    priority_hint: str

    @classmethod
    def from_domain(cls, t: ProposedTaskDomain) -> "ProposedTaskResponse":
        return cls(
            title=t.title,
            description=t.description,
            suggested_role_code=t.suggested_role_code,
            priority_hint=t.priority_hint,
        )


class ProjectScopeResponse(BaseModel):
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, scope: ProjectScopeSummaryDomain) -> "ProjectScopeResponse":
        return cls(
            in_scope=scope.in_scope,
            out_of_scope=scope.out_of_scope,
            assumptions=scope.assumptions,
        )


class AgentTeamSuggestionResponse(BaseModel):
    role_code: str
    role_name: str
    responsibility: str
    collaboration_notes: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(
        cls, item: AgentTeamSuggestionDomain
    ) -> "AgentTeamSuggestionResponse":
        return cls(
            role_code=item.role_code,
            role_name=item.role_name,
            responsibility=item.responsibility,
            collaboration_notes=item.collaboration_notes,
        )


class SkillBindingSuggestionResponse(BaseModel):
    skill_code: str
    owner_role_code: str
    usage: str
    activation_stage: str
    binding_mode: str
    reason: str

    @classmethod
    def from_domain(
        cls, item: SkillBindingSuggestionDomain
    ) -> "SkillBindingSuggestionResponse":
        return cls(
            skill_code=item.skill_code,
            owner_role_code=item.owner_role_code,
            usage=item.usage,
            activation_stage=item.activation_stage,
            binding_mode=item.binding_mode,
            reason=item.reason,
        )


class VerificationMechanismResponse(BaseModel):
    name: str
    command_or_method: str
    evidence_required: str
    owner_role_code: str
    purpose: str
    risk_level: str
    requires_user_confirmation: bool

    @classmethod
    def from_domain(
        cls, item: VerificationMechanismSuggestionDomain
    ) -> "VerificationMechanismResponse":
        return cls(
            name=item.name,
            command_or_method=item.command_or_method,
            evidence_required=item.evidence_required,
            owner_role_code=item.owner_role_code,
            purpose=item.purpose,
            risk_level=item.risk_level,
            requires_user_confirmation=item.requires_user_confirmation,
        )


class RepositoryBindingSuggestionResponse(BaseModel):
    binding_type: str
    binding_mode: str
    target: str
    branch: str
    focus_paths: list[str] = Field(default_factory=list)
    usage: str
    safety_note: str

    @classmethod
    def from_domain(
        cls, item: RepositoryBindingSuggestionDomain
    ) -> "RepositoryBindingSuggestionResponse":
        return cls(
            binding_type=item.binding_type,
            binding_mode=item.binding_mode,
            target=item.target,
            branch=item.branch,
            focus_paths=item.focus_paths,
            usage=item.usage,
            safety_note=item.safety_note,
        )


class DeliverableBoundaryResponse(BaseModel):
    name: str
    description: str
    owner_role_code: str
    required_contents: list[str] = Field(default_factory=list)
    done_definition: str
    acceptance_signal: str

    @classmethod
    def from_domain(
        cls, item: DeliverableBoundaryDomain
    ) -> "DeliverableBoundaryResponse":
        return cls(
            name=item.name,
            description=item.description,
            owner_role_code=item.owner_role_code,
            required_contents=item.required_contents,
            done_definition=item.done_definition,
            acceptance_signal=item.acceptance_signal,
        )


class ComplexityAssessmentResponse(BaseModel):
    level: str = "medium"
    label: str = "中等复杂度"
    score: int = 2
    recommended_agent_count: int = 3
    drivers: list[str] = Field(default_factory=list)
    mitigation_suggestions: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(
        cls, item: ComplexityAssessmentDomain
    ) -> "ComplexityAssessmentResponse":
        return cls(
            level=item.level,
            label=item.label,
            score=item.score,
            recommended_agent_count=item.recommended_agent_count,
            drivers=item.drivers,
            mitigation_suggestions=item.mitigation_suggestions,
        )


class PlanVersionResponse(BaseModel):
    id: UUID
    session_id: UUID
    project_id: UUID | None
    version_no: int
    status: PlanVersionStatus
    plan_summary: str
    phases: list[PlanPhaseResponse] = Field(default_factory=list)
    proposed_tasks: list[ProposedTaskResponse] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    project_scope: ProjectScopeResponse = Field(default_factory=ProjectScopeResponse)
    agent_team_suggestions: list[AgentTeamSuggestionResponse] = Field(default_factory=list)
    skill_binding_suggestions: list[SkillBindingSuggestionResponse] = Field(default_factory=list)
    verification_mechanisms: list[VerificationMechanismResponse] = Field(default_factory=list)
    repository_binding_suggestions: list[RepositoryBindingSuggestionResponse] = Field(default_factory=list)
    deliverable_boundaries: list[DeliverableBoundaryResponse] = Field(default_factory=list)
    complexity_assessment: ComplexityAssessmentResponse = Field(
        default_factory=ComplexityAssessmentResponse
    )
    source: str = Field(default="rule_fallback")
    source_detail: str = Field(default="")
    normalization_warnings: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    confirmed_at: str | None
    created_at: str
    updated_at: str
    next_action: str
    missing_info: list[str] = Field(default_factory=list)
    needs_user_confirmation: bool
    gate_conclusion: str

    @classmethod
    def from_domain(cls, pv: ProjectDirectorPlanVersion) -> "PlanVersionResponse":
        next_action, missing_info, needs_confirmation, gate = (
            _compute_plan_contract_fields(pv)
        )

        return cls(
            id=pv.id,
            session_id=pv.session_id,
            project_id=pv.project_id,
            version_no=pv.version_no,
            status=pv.status,
            plan_summary=pv.plan_summary,
            phases=[PlanPhaseResponse.from_domain(p) for p in pv.phases],
            proposed_tasks=[
                ProposedTaskResponse.from_domain(t) for t in pv.proposed_tasks
            ],
            acceptance_criteria=pv.acceptance_criteria,
            risks=pv.risks,
            project_scope=ProjectScopeResponse.from_domain(pv.project_scope),
            agent_team_suggestions=[
                AgentTeamSuggestionResponse.from_domain(item)
                for item in pv.agent_team_suggestions
            ],
            skill_binding_suggestions=[
                SkillBindingSuggestionResponse.from_domain(item)
                for item in pv.skill_binding_suggestions
            ],
            verification_mechanisms=[
                VerificationMechanismResponse.from_domain(item)
                for item in pv.verification_mechanisms
            ],
            repository_binding_suggestions=[
                RepositoryBindingSuggestionResponse.from_domain(item)
                for item in pv.repository_binding_suggestions
            ],
            deliverable_boundaries=[
                DeliverableBoundaryResponse.from_domain(item)
                for item in pv.deliverable_boundaries
            ],
            complexity_assessment=ComplexityAssessmentResponse.from_domain(
                pv.complexity_assessment
            ),
            source=pv.source,
            source_detail=pv.source_detail,
            normalization_warnings=_extract_normalization_warnings(
                pv.source_detail
            ),
            forbidden_actions=pv.forbidden_actions,
            confirmed_at=pv.confirmed_at.isoformat() if pv.confirmed_at else None,
            created_at=pv.created_at.isoformat(),
            updated_at=pv.updated_at.isoformat(),
            next_action=next_action,
            missing_info=missing_info,
            needs_user_confirmation=needs_confirmation,
            gate_conclusion=gate,
        )


def _extract_normalization_warnings(source_detail: str) -> list[str]:
    marker = "normalization_warnings="
    if marker not in source_detail:
        return []
    raw = source_detail.split(marker, 1)[1].split(";", 1)[0]
    return [item.strip() for item in raw.split(",") if item.strip()]


class PlanVersionListResponse(BaseModel):
    session_id: UUID
    plan_versions: list[PlanVersionResponse]


class ReviewPlanVersionRequest(BaseModel):
    action: Literal["approve", "reject", "request_changes"]
    feedback: str = Field(default="", max_length=3000)


class PlanVersionReviewResponse(BaseModel):
    action: Literal["approve", "reject", "request_changes"]
    reviewed_plan_version: PlanVersionResponse
    replacement_plan_version: PlanVersionResponse | None = None
    next_action: str
    gate_conclusion: str


def _compute_plan_contract_fields(
    pv: ProjectDirectorPlanVersion,
) -> tuple[str, list[str], bool, str]:
    """Compute the output contract fields for a plan version."""

    if pv.status == PlanVersionStatus.DRAFT:
        return (
            "计划版本尚未提交确认",
            ["提交确认"],
            False,
            "Partial",
        )

    if pv.status == PlanVersionStatus.PENDING_CONFIRMATION:
        return (
            "计划版本已生成，请审阅后确认。确认后不会自动创建任务",
            ["用户确认"],
            True,
            "Partial",
        )

    if pv.status == PlanVersionStatus.CONFIRMED:
        return (
            "计划版本已确认。后续可进入任务创建阶段，但需单独触发",
            ["任务创建（需单独触发）", "Worker 调度", "运行证据"],
            False,
            "Partial（计划闭环 Pass，总闭环未完成）",
        )

    if pv.status == PlanVersionStatus.SUPERSEDED:
        return (
            "此计划版本已被新版本取代",
            [],
            False,
            "Partial",
        )

    if pv.status == PlanVersionStatus.REJECTED:
        return (
            "此计划版本已被拒绝",
            [],
            False,
            "Partial",
        )

    return ("未知状态", [], False, "Partial")


# ── Plan Version Routes ──────────────────────────────────────────────


@router.post(
    "/sessions/{session_id}/plan-versions",
    response_model=PlanVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a provider-first, review-only plan draft",
)
def create_plan_version(
    session_id: UUID,
    plan_service: Annotated[ProjectDirectorPlanService, Depends(_get_plan_service)],
) -> PlanVersionResponse:
    """Generate a provider-first, review-only plan draft from a confirmed session.

    Only `confirmed` sessions can generate plan versions. The plan service
    prefers configured AI provider output and validates it in the backend.
    Deterministic rule_fallback is used only when no provider can be attempted
    (for example provider not configured). If a configured provider returns
    invalid or unsafe output, the endpoint returns an explicit error instead of
    persisting a template draft. This endpoint does not create tasks, dispatch
    Worker, call planning/apply, or write repositories.
    """

    try:
        plan_version = plan_service.create_plan_version(session_id=session_id)
    except ProjectDirectorPlanGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "only confirmed sessions" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    return PlanVersionResponse.from_domain(plan_version)


@router.get(
    "/sessions/{session_id}/plan-versions",
    response_model=PlanVersionListResponse,
    summary="List plan versions for a session",
)
def list_plan_versions(
    session_id: UUID,
    plan_service: Annotated[ProjectDirectorPlanService, Depends(_get_plan_service)],
) -> PlanVersionListResponse:
    """List all plan versions for a session, newest version_no first."""

    try:
        versions = plan_service.list_plan_versions(session_id=session_id)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    return PlanVersionListResponse(
        session_id=session_id,
        plan_versions=[PlanVersionResponse.from_domain(v) for v in versions],
    )


@router.get(
    "/plan-versions/{plan_version_id}",
    response_model=PlanVersionResponse,
    summary="Get a plan version by ID",
)
def get_plan_version(
    plan_version_id: UUID,
    plan_service: Annotated[ProjectDirectorPlanService, Depends(_get_plan_service)],
) -> PlanVersionResponse:
    """Read a single plan version detail."""

    plan_version = plan_service.get_plan_version(plan_version_id)
    if plan_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan version {plan_version_id} not found",
        )

    return PlanVersionResponse.from_domain(plan_version)


@router.post(
    "/plan-versions/{plan_version_id}/confirm",
    response_model=PlanVersionResponse,
    summary="Confirm a plan version",
)
def confirm_plan_version(
    plan_version_id: UUID,
    plan_service: Annotated[ProjectDirectorPlanService, Depends(_get_plan_service)],
) -> PlanVersionResponse:
    """Confirm a plan version.

    Transitions: pending_confirmation → confirmed.
    Supersedes any previously confirmed plan version for the same session.
    Does NOT create tasks or call planning/apply.
    Re-confirming an already confirmed plan version is idempotent.
    """

    try:
        plan_version = plan_service.confirm_plan_version(
            plan_version_id=plan_version_id
        )
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "only 'pending_confirmation'" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    return PlanVersionResponse.from_domain(plan_version)


@router.post(
    "/plan-versions/{plan_version_id}/review",
    response_model=PlanVersionReviewResponse,
    summary="Review a plan version draft",
)
def review_plan_version(
    plan_version_id: UUID,
    request: ReviewPlanVersionRequest,
    plan_service: Annotated[ProjectDirectorPlanService, Depends(_get_plan_service)],
) -> PlanVersionReviewResponse:
    """Approve, reject, or request changes for a reviewable plan draft."""

    try:
        if request.action == "approve":
            reviewed = plan_service.confirm_plan_version(plan_version_id)
            replacement = None
            next_action = "草案已通过，可单独触发任务创建；不会自动执行。"
        elif request.action == "reject":
            reviewed = plan_service.reject_plan_version(plan_version_id)
            replacement = None
            next_action = "草案已拒绝，可重新生成或调整目标后再提交。"
        else:
            reviewed, replacement = plan_service.request_changes(
                plan_version_id=plan_version_id,
                feedback=request.feedback,
            )
            next_action = (
                f"已生成整改版 v{replacement.version_no}，请重新审阅后再决定。"
            )
    except ProjectDirectorPlanGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "only 'pending_confirmation'" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    return PlanVersionReviewResponse(
        action=request.action,
        reviewed_plan_version=PlanVersionResponse.from_domain(reviewed),
        replacement_plan_version=(
            PlanVersionResponse.from_domain(replacement)
            if replacement is not None
            else None
        ),
        next_action=next_action,
        gate_conclusion="Partial",
    )


# ── Confirmation Inbox DTOs ──────────────────────────────────────────


class ConfirmationItemResponse(BaseModel):
    id: str
    source_type: str
    source_id: UUID
    project_id: UUID | None
    session_id: UUID
    title: str
    summary: str
    status: str
    risk_level: str
    next_action: str
    confirm_api_hint: str
    created_at: str
    updated_at: str


class ConfirmationInboxResponse(BaseModel):
    items: list[ConfirmationItemResponse] = Field(default_factory=list)
    total: int = Field(default=0)


def _inbox_item_to_response(item) -> ConfirmationItemResponse:
    return ConfirmationItemResponse(
        id=item.id,
        source_type=item.source_type,
        source_id=item.source_id,
        project_id=item.project_id,
        session_id=item.session_id,
        title=item.title,
        summary=item.summary,
        status=item.status,
        risk_level=item.risk_level,
        next_action=item.next_action,
        confirm_api_hint=item.confirm_api_hint,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


# ── Confirmation Inbox Routes ────────────────────────────────────────


@router.get(
    "/confirmations",
    response_model=ConfirmationInboxResponse,
    summary="List all pending confirmations",
)
def list_all_confirmations(
    svc: Annotated[
        ProjectDirectorConfirmationService, Depends(_get_confirmation_service)
    ],
) -> ConfirmationInboxResponse:
    """Return all pending confirmation items across all sources.

    Aggregates:
    - Goal confirmations (sessions with status=ready_to_confirm)
    - Plan confirmations (plan versions with status=pending_confirmation)

    Read-only. Does not change any state, create tasks, or call workers.
    """

    items = svc.get_all_confirmations()
    return ConfirmationInboxResponse(
        items=[_inbox_item_to_response(i) for i in items],
        total=len(items),
    )


@router.get(
    "/projects/{project_id}/confirmations",
    response_model=ConfirmationInboxResponse,
    summary="List pending confirmations for a project",
)
def list_project_confirmations(
    project_id: UUID,
    svc: Annotated[
        ProjectDirectorConfirmationService, Depends(_get_confirmation_service)
    ],
) -> ConfirmationInboxResponse:
    """Return pending confirmation items filtered by project_id."""

    items = svc.get_confirmations_by_project(project_id)
    return ConfirmationInboxResponse(
        items=[_inbox_item_to_response(i) for i in items],
        total=len(items),
    )


@router.get(
    "/sessions/{session_id}/confirmations",
    response_model=ConfirmationInboxResponse,
    summary="List pending confirmations for a session",
)
def list_session_confirmations(
    session_id: UUID,
    svc: Annotated[
        ProjectDirectorConfirmationService, Depends(_get_confirmation_service)
    ],
) -> ConfirmationInboxResponse:
    """Return pending confirmation items filtered by session_id."""

    items = svc.get_confirmations_by_session(session_id)
    return ConfirmationInboxResponse(
        items=[_inbox_item_to_response(i) for i in items],
        total=len(items),
    )



# ── Agent Team Config DTOs / Routes ─────────────────────────────────────────


class AgentTeamConfigMemberResponse(BaseModel):
    role_code: str
    role_name: str
    responsibility: str
    collaboration_notes: list[str] = Field(default_factory=list)
    review_status: str = "pending_confirmation"

    @classmethod
    def from_domain(
        cls, item: ProjectDirectorAgentTeamMemberConfig
    ) -> "AgentTeamConfigMemberResponse":
        return cls(
            role_code=item.role_code,
            role_name=item.role_name,
            responsibility=item.responsibility,
            collaboration_notes=item.collaboration_notes,
            review_status=item.review_status,
        )


class AgentTeamConfigResponse(BaseModel):
    id: UUID
    project_id: UUID
    plan_version_id: UUID
    source_draft_id: str
    status: AgentTeamConfigStatus
    agent_team: list[AgentTeamConfigMemberResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    review_note: str = ""
    created_at: str
    updated_at: str
    confirmed_at: str | None = None
    rejected_at: str | None = None

    @classmethod
    def from_domain(
        cls, config: ProjectDirectorAgentTeamConfig
    ) -> "AgentTeamConfigResponse":
        return cls(
            id=config.id,
            project_id=config.project_id,
            plan_version_id=config.plan_version_id,
            source_draft_id=config.source_draft_id,
            status=config.status,
            agent_team=[
                AgentTeamConfigMemberResponse.from_domain(item)
                for item in config.agent_team
            ],
            warnings=config.warnings,
            review_note=config.review_note,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
            confirmed_at=(
                config.confirmed_at.isoformat() if config.confirmed_at else None
            ),
            rejected_at=(
                config.rejected_at.isoformat() if config.rejected_at else None
            ),
        )


class AgentTeamConfigEnvelopeResponse(BaseModel):
    project_id: UUID
    config: AgentTeamConfigResponse | None = None
    next_action: str

    @classmethod
    def from_result(
        cls, result: AgentTeamConfigReadResult
    ) -> "AgentTeamConfigEnvelopeResponse":
        return cls(
            project_id=result.project_id,
            config=(
                AgentTeamConfigResponse.from_domain(result.config)
                if result.config is not None
                else None
            ),
            next_action=result.next_action,
        )


class ReviewAgentTeamConfigRequest(BaseModel):
    action: Literal["confirm", "reject"]
    note: str = Field(default="", max_length=2000)


@router.get(
    "/projects/{project_id}/agent-team-config",
    response_model=AgentTeamConfigEnvelopeResponse,
    summary="Read project-level Project Director agent team config",
)
def get_project_agent_team_config(
    project_id: UUID,
    svc: Annotated[
        ProjectDirectorAgentTeamConfigService,
        Depends(_get_agent_team_config_service),
    ],
) -> AgentTeamConfigEnvelopeResponse:
    """Read the project-level agent team config, if the project has one."""

    try:
        result = svc.get_for_project(project_id)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc
    return AgentTeamConfigEnvelopeResponse.from_result(result)


@router.post(
    "/projects/{project_id}/agent-team-config/review",
    response_model=AgentTeamConfigEnvelopeResponse,
    summary="Confirm or reject a project-level Project Director agent team config",
)
def review_project_agent_team_config(
    project_id: UUID,
    request: ReviewAgentTeamConfigRequest,
    svc: Annotated[
        ProjectDirectorAgentTeamConfigService,
        Depends(_get_agent_team_config_service),
    ],
) -> AgentTeamConfigEnvelopeResponse:
    """Review the config only; never create Agent Session, Worker, Run, or bindings."""

    try:
        result = svc.review_project_config(
            project_id,
            action=request.action,
            note=request.note,
        )
    except ValueError as exc:
        detail = str(exc)
        lower_detail = detail.lower()
        if "project" in lower_detail and "not found" in lower_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "already been reviewed" in lower_detail:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if "agent team config" in lower_detail and "not found" in lower_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc
    return AgentTeamConfigEnvelopeResponse.from_result(result)




# Skill Binding Config DTOs / Routes


class SkillBindingConfigItemResponse(BaseModel):
    skill_code: str
    skill_name: str = ""
    owner_role_code: str
    usage: str
    activation_stage: str
    binding_mode: str
    reason: str = ""
    review_status: str = "pending_confirmation"

    @classmethod
    def from_domain(
        cls, item: ProjectDirectorSkillBindingConfigItem
    ) -> "SkillBindingConfigItemResponse":
        return cls(
            skill_code=item.skill_code,
            skill_name=item.skill_name,
            owner_role_code=item.owner_role_code,
            usage=item.usage,
            activation_stage=item.activation_stage,
            binding_mode=item.binding_mode,
            reason=item.reason,
            review_status=item.review_status,
        )


class SkillBindingConfigResponse(BaseModel):
    id: UUID
    project_id: UUID
    plan_version_id: UUID
    source_draft_id: str
    status: SkillBindingConfigStatus
    skill_bindings: list[SkillBindingConfigItemResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    review_note: str = ""
    created_at: str
    updated_at: str
    confirmed_at: str | None = None
    rejected_at: str | None = None

    @classmethod
    def from_domain(
        cls, config: ProjectDirectorSkillBindingConfig
    ) -> "SkillBindingConfigResponse":
        return cls(
            id=config.id,
            project_id=config.project_id,
            plan_version_id=config.plan_version_id,
            source_draft_id=config.source_draft_id,
            status=config.status,
            skill_bindings=[
                SkillBindingConfigItemResponse.from_domain(item)
                for item in config.skill_bindings
            ],
            warnings=config.warnings,
            review_note=config.review_note,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
            confirmed_at=(
                config.confirmed_at.isoformat() if config.confirmed_at else None
            ),
            rejected_at=(
                config.rejected_at.isoformat() if config.rejected_at else None
            ),
        )


class SkillBindingConfigEnvelopeResponse(BaseModel):
    project_id: UUID
    config: SkillBindingConfigResponse | None = None
    next_action: str

    @classmethod
    def from_result(
        cls, result: SkillBindingConfigReadResult
    ) -> "SkillBindingConfigEnvelopeResponse":
        return cls(
            project_id=result.project_id,
            config=(
                SkillBindingConfigResponse.from_domain(result.config)
                if result.config is not None
                else None
            ),
            next_action=result.next_action,
        )


class ReviewSkillBindingConfigRequest(BaseModel):
    action: Literal["confirm", "reject"]
    note: str = Field(default="", max_length=2000)


@router.get(
    "/projects/{project_id}/skill-binding-config",
    response_model=SkillBindingConfigEnvelopeResponse,
    summary="Read project-level Project Director skill binding config",
)
def get_project_skill_binding_config(
    project_id: UUID,
    svc: Annotated[
        ProjectDirectorSkillBindingConfigService,
        Depends(_get_skill_binding_config_service),
    ],
) -> SkillBindingConfigEnvelopeResponse:
    """Read the project-level Skill binding config, if the project has one."""

    try:
        result = svc.get_for_project(project_id)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc
    return SkillBindingConfigEnvelopeResponse.from_result(result)


@router.post(
    "/projects/{project_id}/skill-binding-config/review",
    response_model=SkillBindingConfigEnvelopeResponse,
    summary="Confirm or reject a project-level Project Director skill binding config",
)
def review_project_skill_binding_config(
    project_id: UUID,
    request: ReviewSkillBindingConfigRequest,
    svc: Annotated[
        ProjectDirectorSkillBindingConfigService,
        Depends(_get_skill_binding_config_service),
    ],
) -> SkillBindingConfigEnvelopeResponse:
    """Review only; never create Skill bindings, Workers, Runs, or Agent Sessions."""

    try:
        result = svc.review_project_config(
            project_id,
            action=request.action,
            note=request.note,
        )
    except ValueError as exc:
        detail = str(exc)
        lower_detail = detail.lower()
        if "project" in lower_detail and "not found" in lower_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "already been reviewed" in lower_detail:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if "skill binding config" in lower_detail and "not found" in lower_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc
    return SkillBindingConfigEnvelopeResponse.from_result(result)


# Repository Binding Config DTOs / Routes


class RepositoryBindingConfigItemResponse(BaseModel):
    binding_type: str
    binding_mode: str
    target: str
    branch: str
    focus_paths: list[str] = Field(default_factory=list)
    usage: str
    safety_note: str
    review_status: str = "pending_confirmation"

    @classmethod
    def from_domain(
        cls, item: ProjectDirectorRepositoryBindingConfigItem
    ) -> "RepositoryBindingConfigItemResponse":
        return cls(
            binding_type=item.binding_type,
            binding_mode=item.binding_mode,
            target=item.target,
            branch=item.branch,
            focus_paths=item.focus_paths,
            usage=item.usage,
            safety_note=item.safety_note,
            review_status=item.review_status,
        )


class RepositoryBindingConfigResponse(BaseModel):
    id: UUID
    project_id: UUID
    plan_version_id: UUID
    source_draft_id: str
    status: RepositoryBindingConfigStatus
    repository_bindings: list[RepositoryBindingConfigItemResponse] = Field(
        default_factory=list
    )
    warnings: list[str] = Field(default_factory=list)
    review_note: str = ""
    created_at: str
    updated_at: str
    confirmed_at: str | None = None
    rejected_at: str | None = None

    @classmethod
    def from_domain(
        cls, config: ProjectDirectorRepositoryBindingConfig
    ) -> "RepositoryBindingConfigResponse":
        return cls(
            id=config.id,
            project_id=config.project_id,
            plan_version_id=config.plan_version_id,
            source_draft_id=config.source_draft_id,
            status=config.status,
            repository_bindings=[
                RepositoryBindingConfigItemResponse.from_domain(item)
                for item in config.repository_bindings
            ],
            warnings=config.warnings,
            review_note=config.review_note,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
            confirmed_at=(
                config.confirmed_at.isoformat() if config.confirmed_at else None
            ),
            rejected_at=(
                config.rejected_at.isoformat() if config.rejected_at else None
            ),
        )


class RepositoryBindingConfigEnvelopeResponse(BaseModel):
    project_id: UUID
    config: RepositoryBindingConfigResponse | None = None
    next_action: str

    @classmethod
    def from_result(
        cls, result: RepositoryBindingConfigReadResult
    ) -> "RepositoryBindingConfigEnvelopeResponse":
        return cls(
            project_id=result.project_id,
            config=(
                RepositoryBindingConfigResponse.from_domain(result.config)
                if result.config is not None
                else None
            ),
            next_action=result.next_action,
        )


class ReviewRepositoryBindingConfigRequest(BaseModel):
    action: Literal["confirm", "reject"]
    note: str = Field(default="", max_length=2000)


@router.get(
    "/projects/{project_id}/repository-binding-config",
    response_model=RepositoryBindingConfigEnvelopeResponse,
    summary="Read project-level Project Director repository binding config",
)
def get_project_repository_binding_config(
    project_id: UUID,
    svc: Annotated[
        ProjectDirectorRepositoryBindingConfigService,
        Depends(_get_repository_binding_config_service),
    ],
) -> RepositoryBindingConfigEnvelopeResponse:
    """Read the project-level repository binding config, if the project has one."""

    try:
        result = svc.get_for_project(project_id)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc
    return RepositoryBindingConfigEnvelopeResponse.from_result(result)


@router.post(
    "/projects/{project_id}/repository-binding-config/review",
    response_model=RepositoryBindingConfigEnvelopeResponse,
    summary="Confirm or reject a project-level Project Director repository binding config",
)
def review_project_repository_binding_config(
    project_id: UUID,
    request: ReviewRepositoryBindingConfigRequest,
    svc: Annotated[
        ProjectDirectorRepositoryBindingConfigService,
        Depends(_get_repository_binding_config_service),
    ],
) -> RepositoryBindingConfigEnvelopeResponse:
    """Review only; never create RepositoryWorkspace, Workers, Runs, or git actions."""

    try:
        result = svc.review_project_config(
            project_id,
            action=request.action,
            note=request.note,
        )
    except ValueError as exc:
        detail = str(exc)
        lower_detail = detail.lower()
        if "project" in lower_detail and "not found" in lower_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "already been reviewed" in lower_detail:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if "repository binding config" in lower_detail and "not found" in lower_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc
    return RepositoryBindingConfigEnvelopeResponse.from_result(result)


# Verification Config DTOs / Routes


class VerificationConfigItemResponse(BaseModel):
    name: str
    command_or_method: str
    purpose: str = ""
    evidence_required: str
    owner_role_code: str
    risk_level: str
    requires_user_confirmation: bool
    review_status: str = "pending_confirmation"

    @classmethod
    def from_domain(
        cls, item: ProjectDirectorVerificationConfigItem
    ) -> "VerificationConfigItemResponse":
        return cls(
            name=item.name,
            command_or_method=item.command_or_method,
            purpose=item.purpose,
            evidence_required=item.evidence_required,
            owner_role_code=item.owner_role_code,
            risk_level=item.risk_level,
            requires_user_confirmation=item.requires_user_confirmation,
            review_status=item.review_status,
        )


class VerificationConfigResponse(BaseModel):
    id: UUID
    project_id: UUID
    plan_version_id: UUID
    source_draft_id: str
    status: VerificationConfigStatus
    verification_mechanisms: list[VerificationConfigItemResponse] = Field(
        default_factory=list
    )
    warnings: list[str] = Field(default_factory=list)
    review_note: str = ""
    created_at: str
    updated_at: str
    confirmed_at: str | None = None
    rejected_at: str | None = None

    @classmethod
    def from_domain(
        cls, config: ProjectDirectorVerificationConfig
    ) -> "VerificationConfigResponse":
        return cls(
            id=config.id,
            project_id=config.project_id,
            plan_version_id=config.plan_version_id,
            source_draft_id=config.source_draft_id,
            status=config.status,
            verification_mechanisms=[
                VerificationConfigItemResponse.from_domain(item)
                for item in config.verification_mechanisms
            ],
            warnings=config.warnings,
            review_note=config.review_note,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
            confirmed_at=(
                config.confirmed_at.isoformat() if config.confirmed_at else None
            ),
            rejected_at=(
                config.rejected_at.isoformat() if config.rejected_at else None
            ),
        )


class VerificationConfigEnvelopeResponse(BaseModel):
    project_id: UUID
    config: VerificationConfigResponse | None = None
    next_action: str

    @classmethod
    def from_result(
        cls, result: VerificationConfigReadResult
    ) -> "VerificationConfigEnvelopeResponse":
        return cls(
            project_id=result.project_id,
            config=(
                VerificationConfigResponse.from_domain(result.config)
                if result.config is not None
                else None
            ),
            next_action=result.next_action,
        )


class ReviewVerificationConfigRequest(BaseModel):
    action: Literal["confirm", "reject"]
    note: str = Field(default="", max_length=2000)


@router.get(
    "/projects/{project_id}/verification-config",
    response_model=VerificationConfigEnvelopeResponse,
    summary="Read project-level Project Director verification config",
)
def get_project_verification_config(
    project_id: UUID,
    svc: Annotated[
        ProjectDirectorVerificationConfigService,
        Depends(_get_verification_config_service),
    ],
) -> VerificationConfigEnvelopeResponse:
    """Read the project-level verification config, if the project has one."""

    try:
        result = svc.get_for_project(project_id)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc
    return VerificationConfigEnvelopeResponse.from_result(result)


@router.post(
    "/projects/{project_id}/verification-config/review",
    response_model=VerificationConfigEnvelopeResponse,
    summary="Confirm or reject a project-level Project Director verification config",
)
def review_project_verification_config(
    project_id: UUID,
    request: ReviewVerificationConfigRequest,
    svc: Annotated[
        ProjectDirectorVerificationConfigService,
        Depends(_get_verification_config_service),
    ],
) -> VerificationConfigEnvelopeResponse:
    """Review only; never execute commands, create Runs, or dispatch Workers."""

    try:
        result = svc.review_project_config(
            project_id,
            action=request.action,
            note=request.note,
        )
    except ValueError as exc:
        detail = str(exc)
        lower_detail = detail.lower()
        if "project" in lower_detail and "not found" in lower_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "already been reviewed" in lower_detail:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if "verification config" in lower_detail and "not found" in lower_detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc
    return VerificationConfigEnvelopeResponse.from_result(result)



# ── Task Creation DTOs ───────────────────────────────────────────────



class ProjectDirectorSetupReadinessResponse(BaseModel):
    project_id: UUID
    source_plan_version_id: UUID | None = None
    source_draft_id: str | None = None
    created_by_director: bool
    formal_project_created: bool
    task_queue_created: bool
    task_count: int
    pending_task_count: int
    agent_team_config_status: Literal[
        "pending_confirmation", "confirmed", "rejected", "missing"
    ]
    skill_binding_config_status: Literal[
        "pending_confirmation", "confirmed", "rejected", "missing"
    ]
    repository_binding_config_status: Literal[
        "pending_confirmation", "confirmed", "rejected", "missing"
    ]
    verification_config_status: Literal[
        "pending_confirmation", "confirmed", "rejected", "missing"
    ]
    pending_confirmation_count: int
    rejected_count: int
    confirmed_count: int
    ready_for_manual_execution: bool
    next_steps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(
        cls,
        readiness: ProjectDirectorSetupReadiness,
    ) -> "ProjectDirectorSetupReadinessResponse":
        return cls(
            project_id=readiness.project_id,
            source_plan_version_id=readiness.source_plan_version_id,
            source_draft_id=readiness.source_draft_id,
            created_by_director=readiness.created_by_director,
            formal_project_created=readiness.formal_project_created,
            task_queue_created=readiness.task_queue_created,
            task_count=readiness.task_count,
            pending_task_count=readiness.pending_task_count,
            agent_team_config_status=readiness.agent_team_config_status,
            skill_binding_config_status=readiness.skill_binding_config_status,
            repository_binding_config_status=(
                readiness.repository_binding_config_status
            ),
            verification_config_status=readiness.verification_config_status,
            pending_confirmation_count=readiness.pending_confirmation_count,
            rejected_count=readiness.rejected_count,
            confirmed_count=readiness.confirmed_count,
            ready_for_manual_execution=readiness.ready_for_manual_execution,
            next_steps=readiness.next_steps,
            warnings=readiness.warnings,
        )


@router.get(
    "/projects/{project_id}/setup-readiness",
    response_model=ProjectDirectorSetupReadinessResponse,
    summary="Read Project Director setup readiness summary",
)
def get_project_setup_readiness(
    project_id: UUID,
    svc: Annotated[
        ProjectDirectorSetupReadinessService,
        Depends(_get_setup_readiness_service),
    ],
) -> ProjectDirectorSetupReadinessResponse:
    """Read a project-level setup summary without execution side effects."""

    try:
        readiness = svc.get_project_setup_readiness(project_id)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    return ProjectDirectorSetupReadinessResponse.from_domain(readiness)


class TaskCreationResponse(BaseModel):
    plan_version_id: UUID
    session_id: UUID
    project_id: UUID
    project_name: str | None = None
    created_task_ids: list[UUID] = Field(default_factory=list)
    task_count: int = Field(default=0)
    status: str
    already_created: bool = False
    next_action: str
    warnings: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    gate_conclusion: str


class ConversationListItemResponse(BaseModel):
    conversation_id: UUID
    project_id: UUID | None = None
    title: str
    kind: ConversationKind
    status: ConversationStatus
    session_status: str
    last_message_preview: str
    last_message_at: str | None = None
    message_count: int
    pending_challenge_count: int
    pending_proposal_count: int
    requires_user_action: bool
    owner_scope: str
    created_at: str
    updated_at: str

    @classmethod
    def from_domain(
        cls, item: ConversationListItem
    ) -> "ConversationListItemResponse":
        return cls(
            conversation_id=item.conversation_id,
            project_id=item.project_id,
            title=item.title,
            kind=item.kind,
            status=item.status,
            session_status=item.session_status,
            last_message_preview=item.last_message_preview,
            last_message_at=(
                item.last_message_at.isoformat()
                if item.last_message_at is not None
                else None
            ),
            message_count=item.message_count,
            pending_challenge_count=item.pending_challenge_count,
            pending_proposal_count=item.pending_proposal_count,
            requires_user_action=item.requires_user_action,
            owner_scope=item.owner_scope,
            created_at=item.created_at.isoformat(),
            updated_at=item.updated_at.isoformat(),
        )


class ConversationListResponse(BaseModel):
    conversations: list[ConversationListItemResponse] = Field(default_factory=list)
    has_more: bool = False
    source: str = Field(default="project_director_sessions_read_model")


class ConversationTaskCreationResponse(BaseModel):
    id: UUID
    plan_version_id: UUID
    session_id: UUID
    project_id: UUID
    version_no: int
    source_type: str
    created_task_ids: list[UUID] = Field(default_factory=list)
    task_count: int
    created_at: str

    @classmethod
    def from_record(cls, record) -> "ConversationTaskCreationResponse":
        return cls(
            id=record.id,
            plan_version_id=record.plan_version_id,
            session_id=record.session_id,
            project_id=record.project_id,
            version_no=record.version_no,
            source_type=record.source_type,
            created_task_ids=record.task_ids,
            task_count=record.task_count,
            created_at=record.created_at.isoformat(),
        )


class ConversationDetailResponse(BaseModel):
    conversation: ConversationListItemResponse
    session: SessionResponse
    recent_messages: list[ProjectDirectorMessageResponse] = Field(default_factory=list)
    latest_plan_version: PlanVersionResponse | None = None
    task_creation: ConversationTaskCreationResponse | None = None
    source: str = Field(default="project_director_conversation_read_model")

    @classmethod
    def from_domain(cls, detail: ConversationDetail) -> "ConversationDetailResponse":
        return cls(
            conversation=ConversationListItemResponse.from_domain(detail.conversation),
            session=SessionResponse.from_domain(detail.session),
            recent_messages=[
                ProjectDirectorMessageResponse.from_domain(message)
                for message in detail.recent_messages
            ],
            latest_plan_version=(
                PlanVersionResponse.from_domain(detail.latest_plan_version)
                if detail.latest_plan_version is not None
                else None
            ),
            task_creation=(
                ConversationTaskCreationResponse.from_record(detail.task_creation)
                if detail.task_creation is not None
                else None
            ),
        )


class ConversationTimelineItemResponse(BaseModel):
    timestamp: str
    kind: str
    summary_cn: str
    related_message_id: UUID | None = None
    related_plan_version_id: UUID | None = None
    related_task_id: UUID | None = None
    related_proposal_id: UUID | None = None

    @classmethod
    def from_domain(
        cls, item: ConversationTimelineItem
    ) -> "ConversationTimelineItemResponse":
        return cls(
            timestamp=item.timestamp.isoformat(),
            kind=item.kind.value,
            summary_cn=item.summary_cn,
            related_message_id=item.related_message_id,
            related_plan_version_id=item.related_plan_version_id,
            related_task_id=item.related_task_id,
            related_proposal_id=item.related_proposal_id,
        )


class ConversationTimelineResponse(BaseModel):
    conversation_id: UUID
    items: list[ConversationTimelineItemResponse] = Field(default_factory=list)
    source: str = Field(default="project_director_conversation_timeline_read_model")


class WorkbenchResumeResponse(BaseModel):
    session: SessionResponse | None = None
    plan_version: PlanVersionResponse | None = None
    task_creation: TaskCreationResponse | None = None
    recent_messages: list[ProjectDirectorMessageResponse] = Field(default_factory=list)
    source: str = Field(default="none")
    next_action: str = Field(default="暂无可恢复的 Project Director 流程。")


class WorkbenchResumableSessionSummary(BaseModel):
    session_id: UUID
    project_id: UUID | None = None
    project_name: str | None = None
    status: ProjectDirectorSessionStatus
    goal_text: str
    goal_summary: str = ""
    updated_at: str
    plan_version_id: UUID | None = None
    plan_version_status: PlanVersionStatus | None = None
    source: str = Field(default="backend_recent_session")
    next_action: str


class WorkbenchResumableSessionsResponse(BaseModel):
    sessions: list[WorkbenchResumableSessionSummary] = Field(default_factory=list)
    source: str = Field(default="project_director_session_repository")


def _task_creation_response_from_result(result) -> TaskCreationResponse:
    return TaskCreationResponse(
        plan_version_id=result.plan_version_id,
        session_id=result.session_id,
        project_id=result.project_id,
        project_name=result.project_name,
        created_task_ids=result.created_task_ids,
        task_count=result.task_count,
        status=result.status,
        already_created=result.already_created,
        next_action=result.next_action,
        warnings=result.warnings,
        forbidden_actions=result.forbidden_actions,
        gate_conclusion=result.gate_conclusion,
    )


def _session_matches_workbench_resume_context(
    session_obj,
    *,
    mode: Literal["new-project", "project"],
    project_id: UUID | None,
) -> bool:
    if mode == "new-project":
        return session_obj.project_id is None
    if project_id is not None:
        return session_obj.project_id == project_id
    return True


def _build_task_creation_readback(
    *,
    db_session: Session,
    plan_repo: ProjectDirectorPlanVersionRepository,
    plan_version_id: UUID,
) -> TaskCreationResponse | None:
    service = ProjectDirectorTaskCreationService(
        plan_repo=plan_repo,
        task_repo=TaskRepository(db_session),
        creation_repo=ProjectDirectorTaskCreationRecordRepository(db_session),
        project_repo=ProjectRepository(db_session),
    )
    result = service.get_created_tasks(plan_version_id)
    if result is None:
        return None
    return _task_creation_response_from_result(result)


def _latest_resumable_plan_for_session(
    *,
    plan_repo: ProjectDirectorPlanVersionRepository,
    session_id: UUID,
) -> ProjectDirectorPlanVersion | None:
    for plan_version in plan_repo.list_by_session_id(session_id):
        if plan_version.status in {
            PlanVersionStatus.PENDING_CONFIRMATION,
            PlanVersionStatus.CONFIRMED,
            PlanVersionStatus.REJECTED,
        }:
            return plan_version
    return None




def _recent_message_responses(
    *,
    db_session: Session,
    session_id: UUID,
    limit: int = 20,
) -> list[ProjectDirectorMessageResponse]:
    messages, _has_more = ProjectDirectorMessageRepository(
        db_session
    ).list_by_session_id(
        session_id=session_id,
        limit=limit,
    )
    return [ProjectDirectorMessageResponse.from_domain(m) for m in messages]

def _build_workbench_resume_for_session(
    *,
    db_session: Session,
    session_obj,
    plan_repo: ProjectDirectorPlanVersionRepository,
) -> WorkbenchResumeResponse:
    latest_plan_version = _latest_resumable_plan_for_session(
        plan_repo=plan_repo,
        session_id=session_obj.id,
    )
    task_creation = (
        _build_task_creation_readback(
            db_session=db_session,
            plan_repo=plan_repo,
            plan_version_id=latest_plan_version.id,
        )
        if latest_plan_version is not None
        else None
    )
    return WorkbenchResumeResponse(
        session=SessionResponse.from_domain(session_obj),
        plan_version=(
            PlanVersionResponse.from_domain(latest_plan_version)
            if latest_plan_version is not None
            else None
        ),
        task_creation=task_creation,
        recent_messages=_recent_message_responses(
            db_session=db_session,
            session_id=session_obj.id,
        ),
        source=(
            "backend_recent_task_creation"
            if task_creation is not None
            else (
                "backend_recent_plan"
                if latest_plan_version is not None
                else "backend_recent_session"
            )
        ),
        next_action=(
            "已恢复正式项目与任务队列，可继续查看执行中心、正式项目或手动启动一次执行。"
            if task_creation is not None
            else "已恢复选中的未完成 Project Director 会话，请继续处理下一步。"
        ),
    )


def _project_name_by_id(
    project_repo: ProjectRepository,
    project_id: UUID | None,
) -> str | None:
    if project_id is None:
        return None
    project = project_repo.get_by_id(project_id)
    return project.name if project is not None else None


@router.get(
    "/workbench/resumable-sessions",
    response_model=WorkbenchResumableSessionsResponse,
    summary="List unfinished Project Director workbench sessions",
)
def list_workbench_resumable_sessions(
    db_session: Annotated[Session, Depends(get_db_session)],
    limit: int = 20,
) -> WorkbenchResumableSessionsResponse:
    """Return unfinished Project Director sessions for explicit workbench restore.

    Read-only recovery list for the workbench UI. It does not create sessions,
    generate plans, create tasks, dispatch Worker, call planning/apply, or write
    repositories.
    """

    session_repo = ProjectDirectorSessionRepository(db_session)
    plan_repo = ProjectDirectorPlanVersionRepository(db_session)
    project_repo = ProjectRepository(db_session)
    safe_limit = max(1, min(limit, 50))
    summaries: list[WorkbenchResumableSessionSummary] = []

    for session_obj in session_repo.list_recent_resumable(limit=safe_limit * 2):
        latest_plan_version = _latest_resumable_plan_for_session(
            plan_repo=plan_repo,
            session_id=session_obj.id,
        )
        task_creation = (
            _build_task_creation_readback(
                db_session=db_session,
                plan_repo=plan_repo,
                plan_version_id=latest_plan_version.id,
            )
            if latest_plan_version is not None
            else None
        )
        if task_creation is not None:
            continue

        summaries.append(
            WorkbenchResumableSessionSummary(
                session_id=session_obj.id,
                project_id=session_obj.project_id,
                project_name=_project_name_by_id(project_repo, session_obj.project_id),
                status=session_obj.status,
                goal_text=session_obj.goal_text,
                goal_summary=session_obj.goal_summary,
                updated_at=session_obj.updated_at.isoformat(),
                plan_version_id=(
                    latest_plan_version.id if latest_plan_version is not None else None
                ),
                plan_version_status=(
                    latest_plan_version.status
                    if latest_plan_version is not None
                    else None
                ),
                source=(
                    "backend_recent_plan"
                    if latest_plan_version is not None
                    else "backend_recent_session"
                ),
                next_action=(
                    "继续审核项目草案"
                    if latest_plan_version is not None
                    and latest_plan_version.status
                    == PlanVersionStatus.PENDING_CONFIRMATION
                    else SessionResponse.from_domain(session_obj).next_action
                ),
            )
        )
        if len(summaries) >= safe_limit:
            break

    return WorkbenchResumableSessionsResponse(sessions=summaries)


@router.get(
    "/workbench/resume",
    response_model=WorkbenchResumeResponse,
    summary="Resume the latest Project Director workbench flow",
)
def get_workbench_resume(
    db_session: Annotated[Session, Depends(get_db_session)],
    mode: Literal["new-project", "project"] = "new-project",
    project_id: UUID | None = None,
    session_id: UUID | None = None,
) -> WorkbenchResumeResponse:
    """Return the latest session / plan/task creation that can still be continued.

    Read-only recovery for the workbench UI. It does not create sessions,
    generate plans, create tasks, dispatch Worker, call planning/apply, or write
    repositories.
    """

    session_repo = ProjectDirectorSessionRepository(db_session)
    plan_repo = ProjectDirectorPlanVersionRepository(db_session)

    if session_id is not None:
        session_obj = session_repo.get_by_id(session_id)
        if session_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project Director session {session_id} not found",
            )
        if not _session_matches_workbench_resume_context(
            session_obj,
            mode=mode,
            project_id=project_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Selected Project Director session does not match the requested workbench context",
            )
        return _build_workbench_resume_for_session(
            db_session=db_session,
            session_obj=session_obj,
            plan_repo=plan_repo,
        )

    recent_plan_versions = plan_repo.list_recent_resumable(
        project_id=project_id if mode == "project" else None,
        unbound_only=False,
        limit=50,
    )
    for plan_version in recent_plan_versions:
        session_obj = session_repo.get_by_id(plan_version.session_id)
        if session_obj is None or not _session_matches_workbench_resume_context(
            session_obj,
            mode=mode,
            project_id=project_id,
        ):
            continue
        task_creation = _build_task_creation_readback(
            db_session=db_session,
            plan_repo=plan_repo,
            plan_version_id=plan_version.id,
        )
        return WorkbenchResumeResponse(
            session=SessionResponse.from_domain(session_obj),
            plan_version=PlanVersionResponse.from_domain(plan_version),
            task_creation=task_creation,
            recent_messages=_recent_message_responses(
                db_session=db_session,
                session_id=session_obj.id,
            ),
            source=(
                "backend_recent_task_creation"
                if task_creation is not None
                else "backend_recent_plan"
            ),
            next_action=(
                "已恢复正式项目与任务队列，可继续查看执行中心、正式项目或手动启动一次执行。"
                if task_creation is not None
                else (
                    "已恢复最近项目草案，请继续审核。"
                    if plan_version.status == PlanVersionStatus.PENDING_CONFIRMATION
                    else "已恢复最近 Project Director 流程，请继续处理下一步。"
                )
            ),
        )

    recent_sessions = session_repo.list_recent_resumable(
        project_id=project_id if mode == "project" else None,
        unbound_only=mode == "new-project",
        limit=50,
    )
    for session_obj in recent_sessions:
        resume = _build_workbench_resume_for_session(
            db_session=db_session,
            session_obj=session_obj,
            plan_repo=plan_repo,
        )
        resume.next_action = (
            "已恢复正式项目与任务队列，可继续查看执行中心、正式项目或手动启动一次执行。"
            if resume.task_creation is not None
            else "已恢复最近 Project Director 会话，请继续处理下一步。"
        )
        return resume

    return WorkbenchResumeResponse()


# ── Project Director Conversation Read-Only Routes ──────────────────


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List Project Director conversations",
)
def list_project_director_conversations(
    db_session: Annotated[Session, Depends(get_db_session)],
    project_id: UUID | None = None,
    status_filter: ConversationStatus | None = Query(default=None, alias="status"),
    kind: ConversationKind | None = None,
    limit: int = 20,
    before: UUID | None = None,
) -> ConversationListResponse:
    """Return the P7 ConversationList read model.

    This endpoint is read-only. It never creates sessions, generates provider
    replies, creates tasks/runs/workers, launches executors, or writes Git state.
    """

    try:
        result = ProjectDirectorConversationService(db_session).list_conversations(
            project_id=project_id,
            status=status_filter,
            kind=kind,
            limit=limit,
            before=before,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return ConversationListResponse(
        conversations=[
            ConversationListItemResponse.from_domain(item)
            for item in result.conversations
        ],
        has_more=result.has_more,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get one Project Director conversation",
)
def get_project_director_conversation(
    conversation_id: UUID,
    db_session: Annotated[Session, Depends(get_db_session)],
    project_id: UUID | None = None,
    recent_message_limit: int = 20,
) -> ConversationDetailResponse:
    """Read one conversation detail without triggering provider or execution."""

    try:
        detail = ProjectDirectorConversationService(db_session).get_conversation(
            conversation_id=conversation_id,
            project_id=project_id,
            recent_message_limit=recent_message_limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project Director conversation {conversation_id} not found",
        )
    return ConversationDetailResponse.from_domain(detail)


@router.get(
    "/conversations/{conversation_id}/timeline",
    response_model=ConversationTimelineResponse,
    summary="Get one Project Director conversation timeline",
)
def get_project_director_conversation_timeline(
    conversation_id: UUID,
    db_session: Annotated[Session, Depends(get_db_session)],
    project_id: UUID | None = None,
) -> ConversationTimelineResponse:
    """Read message/plan/task timeline items for one conversation."""

    try:
        items = ProjectDirectorConversationService(db_session).get_timeline(
            conversation_id=conversation_id,
            project_id=project_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if items is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project Director conversation {conversation_id} not found",
        )
    return ConversationTimelineResponse(
        conversation_id=conversation_id,
        items=[ConversationTimelineItemResponse.from_domain(item) for item in items],
    )


# ── Task Creation Routes ─────────────────────────────────────────────


@router.post(
    "/plan-versions/{plan_version_id}/create-tasks",
    response_model=TaskCreationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create real tasks from a confirmed plan version",
)
def create_tasks_from_plan_version(
    plan_version_id: UUID,
    svc: Annotated[
        ProjectDirectorTaskCreationService,
        Depends(_get_task_creation_service),
    ],
) -> TaskCreationResponse:
    """Create real Task objects from a confirmed Project Director plan version.

    - Only confirmed plan versions can create tasks (409 otherwise).
    - Plan version must have a project_id (409 otherwise).
    - Tasks are created only once per plan version (409 on duplicate).
    - Does NOT call worker, planning/apply, or write repositories.
    - Tasks enter the queue in pending status.
    """

    try:
        result = svc.create_tasks_from_plan_version(plan_version_id)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if (
            "only 'confirmed'" in detail.lower()
            or "must have a project_id" in detail.lower()
            or "already been created" in detail.lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    return TaskCreationResponse(
        plan_version_id=result.plan_version_id,
        session_id=result.session_id,
        project_id=result.project_id,
        project_name=result.project_name,
        created_task_ids=result.created_task_ids,
        task_count=result.task_count,
        status=result.status,
        already_created=result.already_created,
        next_action=result.next_action,
        warnings=result.warnings,
        forbidden_actions=result.forbidden_actions,
        gate_conclusion=result.gate_conclusion,
    )


@router.post(
    "/plan-versions/{plan_version_id}/create-formal-project",
    response_model=TaskCreationResponse,
    summary="Explicitly create a formal Project and Task queue from a confirmed draft",
)
def create_formal_project_from_plan_version(
    plan_version_id: UUID,
    svc: Annotated[
        ProjectDirectorTaskCreationService,
        Depends(_get_task_creation_service),
    ],
) -> TaskCreationResponse:
    """Create/read formal Project + pending Tasks from a confirmed draft.

    This is an explicit user-triggered action. Approving/reviewing a draft
    never calls this automatically. The operation is idempotent and will
    return the existing creation record on repeated calls without duplicating
    Project or Task rows.
    """

    try:
        result = svc.create_formal_project_from_plan_version(plan_version_id)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "only 'confirmed'" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    return TaskCreationResponse(
        plan_version_id=result.plan_version_id,
        session_id=result.session_id,
        project_id=result.project_id,
        project_name=result.project_name,
        created_task_ids=result.created_task_ids,
        task_count=result.task_count,
        status=result.status,
        already_created=result.already_created,
        next_action=result.next_action,
        warnings=result.warnings,
        forbidden_actions=result.forbidden_actions,
        gate_conclusion=result.gate_conclusion,
    )


@router.get(
    "/plan-versions/{plan_version_id}/created-tasks",
    response_model=TaskCreationResponse,
    summary="Get created tasks for a plan version",
)
def get_created_tasks(
    plan_version_id: UUID,
    svc: Annotated[
        ProjectDirectorTaskCreationService,
        Depends(_get_task_creation_service),
    ],
) -> TaskCreationResponse:
    """Return the task creation record for a plan version, if tasks have been created."""

    result = svc.get_created_tasks(plan_version_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No tasks have been created for plan version {plan_version_id}. "
                f"Use POST /project-director/plan-versions/{plan_version_id}/create-tasks "
                f"to create tasks from a confirmed plan version."
            ),
        )

    return TaskCreationResponse(
        plan_version_id=result.plan_version_id,
        session_id=result.session_id,
        project_id=result.project_id,
        project_name=result.project_name,
        created_task_ids=result.created_task_ids,
        task_count=result.task_count,
        status=result.status,
        already_created=result.already_created,
        next_action=result.next_action,
        warnings=result.warnings,
        forbidden_actions=result.forbidden_actions,
        gate_conclusion=result.gate_conclusion,
    )
