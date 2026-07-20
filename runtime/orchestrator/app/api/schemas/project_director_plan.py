"""Project Director plan-version request and response schemas."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

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
from app.domain.project_director_conversation_intelligence import FormalizationTarget


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
    formalization_target: FormalizationTarget | None = None
    formalization_workspace_version: int | None = None
    formalization_source_message_ids: list[UUID] = Field(default_factory=list)
    formalization_source_event_ids: list[UUID] = Field(default_factory=list)
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
            formalization_target=pv.formalization_target,
            formalization_workspace_version=pv.formalization_workspace_version,
            formalization_source_message_ids=pv.formalization_source_message_ids,
            formalization_source_event_ids=pv.formalization_source_event_ids,
            confirmed_at=pv.confirmed_at.isoformat() if pv.confirmed_at else None,
            created_at=pv.created_at.isoformat(),
            updated_at=pv.updated_at.isoformat(),
            next_action=next_action,
            missing_info=missing_info,
            needs_user_confirmation=needs_confirmation,
            gate_conclusion=gate,
        )


class FormalizeDiscussionRequest(BaseModel):
    workspace_version: int = Field(ge=1)
    target: Literal["plan_revision"]
    user_confirmed: bool = False


class FormalizeDiscussionResponse(BaseModel):
    session_id: UUID
    workspace_version: int
    target: Literal["plan_revision"]
    source_message_ids: list[UUID]
    source_event_ids: list[UUID]
    idempotent_replay: bool
    plan_version: PlanVersionResponse
    task_created: bool = False
    run_created: bool = False
    worker_started: bool = False
    executor_started: bool = False
    repository_write_performed: bool = False
    gate_conclusion: str = "Partial"


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


def _extract_normalization_warnings(source_detail: str) -> list[str]:
    marker = "normalization_warnings="
    if marker not in source_detail:
        return []
    raw = source_detail.split(marker, 1)[1].split(";", 1)[0]
    return [item.strip() for item in raw.split(",") if item.strip()]


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
