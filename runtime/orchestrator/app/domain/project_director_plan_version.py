"""AI Project Director Plan Version domain model.

Plan drafts are review-only records. Generation is provider-first with explicit
rule fallback provenance, but confirmation still does not create tasks or run
workers.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from app.domain._base import DomainModel
from app.domain.project_role import ProjectRoleCode


class PlanVersionStatus(StrEnum):
    """Plan version lifecycle."""

    DRAFT = "draft"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class PlanPhase(DomainModel):
    """A single phase within a plan version."""

    sequence: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=1, max_length=1000)
    task_count_hint: int = Field(default=1, ge=1)


class ProposedTask(DomainModel):
    """A proposed task within a plan version — NOT a real task in the queue."""

    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2000)
    suggested_role_code: ProjectRoleCode = Field(default=ProjectRoleCode.ENGINEER)
    priority_hint: str = Field(default="normal", max_length=40)


class ProjectScopeSummary(DomainModel):
    """Review-only project scope boundaries for a generated plan draft."""

    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class AgentTeamSuggestion(DomainModel):
    """Suggested agent/role lineup for a reviewable plan draft."""

    role_code: ProjectRoleCode = Field(default=ProjectRoleCode.ENGINEER)
    role_name: str = Field(default="", max_length=100)
    responsibility: str = Field(min_length=1, max_length=1000)
    collaboration_notes: list[str] = Field(default_factory=list)


class SkillBindingSuggestion(DomainModel):
    """Suggested skill binding for a role without creating real bindings."""

    skill_code: str = Field(min_length=1, max_length=120)
    owner_role_code: ProjectRoleCode = Field(default=ProjectRoleCode.ENGINEER)
    usage: str = Field(min_length=1, max_length=1000)
    activation_stage: str = Field(default="planning", max_length=120)
    binding_mode: str = Field(default="not_bound", max_length=120)
    reason: str = Field(default="", max_length=1000)


class VerificationMechanismSuggestion(DomainModel):
    """Suggested verification mechanism for a plan draft."""

    name: str = Field(min_length=1, max_length=200)
    command_or_method: str = Field(min_length=1, max_length=1000)
    evidence_required: str = Field(min_length=1, max_length=1000)
    owner_role_code: ProjectRoleCode = Field(default=ProjectRoleCode.REVIEWER)
    purpose: str = Field(default="", max_length=1000)
    risk_level: str = Field(default="normal", max_length=40)
    requires_user_confirmation: bool = Field(default=False)


class RepositoryBindingSuggestion(DomainModel):
    """Suggested repository binding without creating any real repository link."""

    binding_type: str = Field(default="review_only", max_length=120)
    binding_mode: str = Field(default="not_bound", max_length=120)
    target: str = Field(min_length=1, max_length=500)
    branch: str = Field(default="未指定", max_length=200)
    focus_paths: list[str] = Field(default_factory=list)
    usage: str = Field(min_length=1, max_length=1000)
    safety_note: str = Field(min_length=1, max_length=1000)


class DeliverableBoundary(DomainModel):
    """Expected deliverable boundary for a plan draft."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    owner_role_code: ProjectRoleCode = Field(default=ProjectRoleCode.ENGINEER)
    required_contents: list[str] = Field(default_factory=list)
    done_definition: str = Field(min_length=1, max_length=1000)
    acceptance_signal: str = Field(default="", max_length=1000)


class ComplexityAssessment(DomainModel):
    """Deterministic complexity assessment for a review-only draft."""

    level: str = Field(default="medium", max_length=40)
    label: str = Field(default="中等复杂度", max_length=100)
    score: int = Field(default=2, ge=1, le=5)
    recommended_agent_count: int = Field(default=3, ge=1, le=8)
    drivers: list[str] = Field(default_factory=list)
    mitigation_suggestions: list[str] = Field(default_factory=list)


class ProjectDirectorPlanVersion(DomainModel):
    """A plan version generated from a confirmed Project Director session.

    Not a real planning/apply output — purely a reviewable draft.
    Does NOT create tasks, dispatch workers, or write repositories.
    """

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    project_id: UUID | None = None
    version_no: int = Field(ge=1)
    status: PlanVersionStatus = Field(default=PlanVersionStatus.DRAFT)
    plan_summary: str = Field(default="", max_length=5000)
    phases: list[PlanPhase] = Field(default_factory=list)
    proposed_tasks: list[ProposedTask] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    project_scope: ProjectScopeSummary = Field(default_factory=ProjectScopeSummary)
    agent_team_suggestions: list[AgentTeamSuggestion] = Field(default_factory=list)
    skill_binding_suggestions: list[SkillBindingSuggestion] = Field(default_factory=list)
    verification_mechanisms: list[VerificationMechanismSuggestion] = Field(default_factory=list)
    repository_binding_suggestions: list[RepositoryBindingSuggestion] = Field(default_factory=list)
    deliverable_boundaries: list[DeliverableBoundary] = Field(default_factory=list)
    complexity_assessment: ComplexityAssessment = Field(default_factory=ComplexityAssessment)
    source: str = Field(default="rule_fallback", max_length=40)
    source_detail: str = Field(default="deterministic_plan_generation", max_length=500)
    forbidden_actions: list[str] = Field(default_factory=list)
    confirmed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
