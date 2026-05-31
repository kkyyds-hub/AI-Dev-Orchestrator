"""AI Project Director session, plan version & confirmation inbox API routes.

BCG-01: goal intake → clarification → confirmation.
BCG-02: plan version generation → pending_confirmation → confirmed.
BCG-03: pending confirmation inbox (read-only aggregation).
BCG-04A: confirmed plan version → real task queue creation.
No AI, no Provider, no planning/apply, no worker dispatch.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
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
from app.domain.project_director_session import (
    ClarifyingAnswer,
    ClarifyingQuestion,
    ProjectDirectorSessionStatus,
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
from app.services.project_director_confirmation_service import (
    ProjectDirectorConfirmationService,
)
from app.services.project_director_plan_service import ProjectDirectorPlanService
from app.services.project_director_service import ProjectDirectorService
from app.services.project_director_task_creation_service import (
    ProjectDirectorTaskCreationService,
)


# ── Dependencies ────────────────────────────────────────────────────


def _get_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorService:
    repo = ProjectDirectorSessionRepository(session)
    return ProjectDirectorService(session_repository=repo)


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
    return ProjectDirectorTaskCreationService(
        plan_repo=plan_repo,
        task_repo=task_repo,
        creation_repo=creation_repo,
        project_repo=project_repo,
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

    @classmethod
    def from_domain(cls, q: ClarifyingQuestion) -> "ClarifyingQuestionResponse":
        return cls(id=q.id, question=q.question, hint=q.hint, required=q.required)


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

    The session starts in `clarifying` status with deterministic questions.
    No AI or Provider is called.
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
            forbidden_actions=pv.forbidden_actions,
            confirmed_at=pv.confirmed_at.isoformat() if pv.confirmed_at else None,
            created_at=pv.created_at.isoformat(),
            updated_at=pv.updated_at.isoformat(),
            next_action=next_action,
            missing_info=missing_info,
            needs_user_confirmation=needs_confirmation,
            gate_conclusion=gate,
        )


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
    summary="Create a plan version from a confirmed session",
)
def create_plan_version(
    session_id: UUID,
    plan_service: Annotated[ProjectDirectorPlanService, Depends(_get_plan_service)],
) -> PlanVersionResponse:
    """Generate a deterministic plan version from a confirmed session.

    Only `confirmed` sessions can generate plan versions.
    No AI, no Provider, no task creation, no worker dispatch.
    """

    try:
        plan_version = plan_service.create_plan_version(session_id=session_id)
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


# ── Task Creation DTOs ───────────────────────────────────────────────


class TaskCreationResponse(BaseModel):
    plan_version_id: UUID
    session_id: UUID
    project_id: UUID
    created_task_ids: list[UUID] = Field(default_factory=list)
    task_count: int = Field(default=0)
    status: str
    next_action: str
    forbidden_actions: list[str] = Field(default_factory=list)
    gate_conclusion: str


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
        created_task_ids=result.created_task_ids,
        task_count=result.task_count,
        status=result.status,
        next_action=result.next_action,
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
        created_task_ids=result.created_task_ids,
        task_count=result.task_count,
        status=result.status,
        next_action=result.next_action,
        forbidden_actions=result.forbidden_actions,
        gate_conclusion=result.gate_conclusion,
    )
