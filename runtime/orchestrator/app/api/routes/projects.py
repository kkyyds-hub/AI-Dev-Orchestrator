"""Project endpoints."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain._base import utc_now
from app.domain.approval import ApprovalDecisionAction
from app.domain.project import (
    Project,
    ProjectMilestone,
    ProjectMilestoneCode,
    ProjectStage,
    ProjectStageBlockingTask,
    ProjectStageGuard,
    ProjectStageHistoryEntry,
    ProjectStageHistoryOutcome,
    ProjectStatus,
    ProjectTaskStats,
)
from app.domain.project_role import ProjectRoleCode
from app.api.routes.repositories import (
    ChangeSessionResponse,
    RepositoryDay15FlowStatus,
    RepositorySnapshotResponse,
    RepositoryWorkspaceResponse,
    build_repository_day15_flow_snapshot,
)
from app.domain.change_session import ChangeSession
from app.domain.task import TaskHumanStatus, TaskPriority, TaskRiskLevel, TaskStatus
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.change_plan_repository import ChangePlanRepository
from app.repositories.change_session_repository import ChangeSessionRepository
from app.repositories.commit_candidate_repository import CommitCandidateRepository
from app.repositories.deliverable_repository import DeliverableRepository
from app.repositories.agent_session_repository import AgentSessionRepository
from app.repositories.failure_review_repository import FailureReviewRepository
from app.repositories.project_role_repository import ProjectRoleRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_snapshot_repository import (
    RepositorySnapshotRepository,
)
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.verification_run_repository import VerificationRunRepository
from app.services.approval_service import (
    ApprovalService,
    ApprovalTimelineEntry,
)
from app.services.budget_guard_service import BudgetGuardService
from app.services.context_budget_service import ContextBudgetService
from app.services.context_builder_service import ContextBuilderService
from app.services.decision_replay_service import (
    DecisionReplayService,
    ProjectDecisionTimelineEntry,
)
from app.services.diff_summary_service import DiffSummaryService
from app.services.deliverable_service import (
    DeliverableService,
    DeliverableTimelineEntry,
)
from app.services.failure_review_service import FailureReviewService
from app.services.change_risk_guard_service import (
    ChangeBatchPreflightTimelineEntry,
    ChangeRiskGuardService,
)
from app.services.project_memory_service import (
    MemoryCompactionRecord,
    MemoryGovernanceState,
    MemoryRehydrateResult,
    ProjectMemoryCount,
    ProjectMemoryItem,
    ProjectMemoryKind,
    ProjectMemorySearchHit,
    ProjectMemorySearchResult,
    ProjectMemoryService,
)
from app.services.project_service import (
    ProjectDetail,
    ProjectService,
    ProjectTaskTreeItem,
)
from app.services.project_stage_service import (
    ProjectStageAdvanceResult,
    ProjectStageService,
    ProjectStageTransitionError,
)
from app.services.role_catalog_service import RoleCatalogService
from app.services.repository_release_gate_service import (
    RepositoryReleaseGateChangeBatchNotFoundError,
    RepositoryReleaseGateProjectNotFoundError,
    RepositoryReleaseGateService,
)
from app.services.sop_engine_service import (
    ProjectSopSelectionResult,
    ProjectSopSnapshot,
    ProjectSopStageTask,
    ProjectSopOwnerRole,
    SopEngineService,
    SopTemplateSummary,
    SopTemplateStagePreview,
)
from app.services.task_service import TaskService
from app.services.task_readiness_service import TaskReadinessService
from app.services.task_state_machine_service import TaskStateMachineService
from app.services.memory_compaction_service import MemoryCompactionService
from app.services.run_logging_service import RunLoggingService


class ProjectCreateRequest(BaseModel):
    """DTO for project creation requests."""

    name: str = Field(
        min_length=1,
        max_length=200,
        description="Project name shown in the boss/project overview.",
    )
    summary: str = Field(
        min_length=1,
        max_length=2_000,
        description="Minimal project summary describing scope and expected outcome.",
    )
    status: ProjectStatus = Field(
        default=ProjectStatus.ACTIVE,
        description="Overall project status. Defaults to `active`.",
    )
    stage: ProjectStage = Field(
        default=ProjectStage.INTAKE,
        description="Current lifecycle stage. Defaults to `intake`.",
    )


class ProjectTaskStatsResponse(BaseModel):
    """Task aggregation attached to one project response."""

    total_tasks: int
    pending_tasks: int
    running_tasks: int
    paused_tasks: int
    waiting_human_tasks: int
    completed_tasks: int
    failed_tasks: int
    blocked_tasks: int
    last_task_updated_at: datetime | None = None

    @classmethod
    def from_task_stats(
        cls,
        task_stats: ProjectTaskStats,
    ) -> "ProjectTaskStatsResponse":
        """Convert the domain task stats into an API DTO."""

        return cls(
            total_tasks=task_stats.total_tasks,
            pending_tasks=task_stats.pending_tasks,
            running_tasks=task_stats.running_tasks,
            paused_tasks=task_stats.paused_tasks,
            waiting_human_tasks=task_stats.waiting_human_tasks,
            completed_tasks=task_stats.completed_tasks,
            failed_tasks=task_stats.failed_tasks,
            blocked_tasks=task_stats.blocked_tasks,
            last_task_updated_at=task_stats.last_task_updated_at,
        )


class ProjectResponse(BaseModel):
    """Basic project response DTO."""

    id: UUID
    name: str
    summary: str
    status: ProjectStatus
    stage: ProjectStage
    task_stats: ProjectTaskStatsResponse
    repository_workspace: RepositoryWorkspaceResponse | None = None
    latest_repository_snapshot: RepositorySnapshotResponse | None = None
    current_change_session: ChangeSessionResponse | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_project(
        cls,
        project: Project,
        *,
        current_change_session: ChangeSession | None = None,
    ) -> "ProjectResponse":
        """Convert the domain project into an API DTO."""

        return cls(
            id=project.id,
            name=project.name,
            summary=project.summary,
            status=project.status,
            stage=project.stage,
            task_stats=ProjectTaskStatsResponse.from_task_stats(project.task_stats),
            repository_workspace=(
                RepositoryWorkspaceResponse.from_workspace(project.repository_workspace)
                if project.repository_workspace is not None
                else None
            ),
            latest_repository_snapshot=(
                RepositorySnapshotResponse.from_snapshot(
                    project.latest_repository_snapshot
                )
                if project.latest_repository_snapshot is not None
                else None
            ),
            current_change_session=(
                ChangeSessionResponse.from_change_session(current_change_session)
                if current_change_session is not None
                else None
            ),
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class ProjectDay15FlowOverviewResponse(BaseModel):
    """Boss-level Day15 minimum closed-loop overview attached to one project."""

    project_id: UUID
    project_name: str
    generated_at: datetime
    overall_status: RepositoryDay15FlowStatus
    summary: str
    completed_step_count: int
    total_step_count: int
    blocked_step_count: int
    selected_change_batch_id: UUID | None = None
    selected_change_batch_title: str | None = None
    release_status: str | None = None
    release_qualification_established: bool
    git_write_actions_triggered: bool


class ProjectSopTemplateStagePreviewResponse(BaseModel):
    """One stage preview returned by the SOP template catalog."""

    stage: ProjectStage
    title: str
    owner_role_codes: list[ProjectRoleCode]

    @classmethod
    def from_summary(
        cls,
        preview: SopTemplateStagePreview,
    ) -> "ProjectSopTemplateStagePreviewResponse":
        """Convert one stage preview into an API DTO."""

        return cls(
            stage=preview.stage,
            title=preview.title,
            owner_role_codes=list(preview.owner_role_codes),
        )


class ProjectSopTemplateSummaryResponse(BaseModel):
    """One selectable Day06 SOP template returned by the API."""

    code: str
    name: str
    summary: str
    description: str
    is_default: bool
    stages: list[ProjectSopTemplateStagePreviewResponse]

    @classmethod
    def from_summary(
        cls,
        template: SopTemplateSummary,
    ) -> "ProjectSopTemplateSummaryResponse":
        """Convert one SOP template summary into an API DTO."""

        return cls(
            code=template.code,
            name=template.name,
            summary=template.summary,
            description=template.description,
            is_default=template.is_default,
            stages=[
                ProjectSopTemplateStagePreviewResponse.from_summary(stage)
                for stage in template.stages
            ],
        )


class ProjectSopOwnerRoleResponse(BaseModel):
    """One resolved owner role shown inside the project SOP snapshot."""

    role_code: ProjectRoleCode
    name: str
    summary: str
    enabled: bool

    @classmethod
    def from_item(
        cls,
        role: ProjectSopOwnerRole,
    ) -> "ProjectSopOwnerRoleResponse":
        """Convert one owner-role item into an API DTO."""

        return cls(
            role_code=role.role_code,
            name=role.name,
            summary=role.summary,
            enabled=role.enabled,
        )


class ProjectSopStageTaskResponse(BaseModel):
    """One current-stage SOP task shown on the project detail page."""

    task_id: UUID
    task_code: str
    title: str
    status: TaskStatus
    owner_role_codes: list[ProjectRoleCode]
    owner_role_names: list[str]

    @classmethod
    def from_item(
        cls,
        item: ProjectSopStageTask,
    ) -> "ProjectSopStageTaskResponse":
        """Convert one SOP stage task into an API DTO."""

        return cls(
            task_id=item.task_id,
            task_code=item.task_code,
            title=item.title,
            status=item.status,
            owner_role_codes=list(item.owner_role_codes),
            owner_role_names=list(item.owner_role_names),
        )


class ProjectSopSnapshotResponse(BaseModel):
    """Current Day06 SOP snapshot attached to project detail."""

    project_id: UUID
    has_template: bool
    available_template_count: int
    selected_template_code: str | None = None
    selected_template_name: str | None = None
    selected_template_summary: str | None = None
    current_stage: ProjectStage
    current_stage_title: str | None = None
    current_stage_summary: str | None = None
    next_stage: ProjectStage | None = None
    can_advance: bool | None = None
    blocking_reasons: list[str]
    required_inputs: list[str]
    expected_outputs: list[str]
    guard_conditions: list[str]
    owner_roles: list[ProjectSopOwnerRoleResponse]
    stage_tasks: list[ProjectSopStageTaskResponse]
    current_stage_task_count: int
    current_stage_completed_task_count: int
    all_current_stage_tasks_completed: bool
    context_summary: str

    @classmethod
    def from_snapshot(
        cls,
        snapshot: ProjectSopSnapshot,
    ) -> "ProjectSopSnapshotResponse":
        """Convert one SOP snapshot into an API DTO."""

        return cls(
            project_id=snapshot.project_id,
            has_template=snapshot.has_template,
            available_template_count=snapshot.available_template_count,
            selected_template_code=snapshot.selected_template_code,
            selected_template_name=snapshot.selected_template_name,
            selected_template_summary=snapshot.selected_template_summary,
            current_stage=snapshot.current_stage,
            current_stage_title=snapshot.current_stage_title,
            current_stage_summary=snapshot.current_stage_summary,
            next_stage=snapshot.next_stage,
            can_advance=snapshot.can_advance,
            blocking_reasons=snapshot.blocking_reasons,
            required_inputs=snapshot.required_inputs,
            expected_outputs=snapshot.expected_outputs,
            guard_conditions=snapshot.guard_conditions,
            owner_roles=[
                ProjectSopOwnerRoleResponse.from_item(role)
                for role in snapshot.owner_roles
            ],
            stage_tasks=[
                ProjectSopStageTaskResponse.from_item(task)
                for task in snapshot.stage_tasks
            ],
            current_stage_task_count=snapshot.current_stage_task_count,
            current_stage_completed_task_count=snapshot.current_stage_completed_task_count,
            all_current_stage_tasks_completed=snapshot.all_current_stage_tasks_completed,
            context_summary=snapshot.context_summary,
        )


class ProjectTaskTreeItemResponse(BaseModel):
    """One task node returned by the Day03 project detail endpoint."""

    id: UUID
    project_id: UUID | None = None
    title: str
    status: TaskStatus
    priority: TaskPriority
    input_summary: str
    acceptance_criteria: list[str]
    depends_on_task_ids: list[UUID]
    child_task_ids: list[UUID]
    depth: int
    risk_level: TaskRiskLevel
    owner_role_code: ProjectRoleCode | None = None
    upstream_role_code: ProjectRoleCode | None = None
    downstream_role_code: ProjectRoleCode | None = None
    human_status: TaskHumanStatus
    paused_reason: str | None = None
    source_draft_id: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_service_item(
        cls,
        item: ProjectTaskTreeItem,
    ) -> "ProjectTaskTreeItemResponse":
        """Convert one project task-tree item into an API DTO."""

        return cls(
            id=item.task.id,
            project_id=item.task.project_id,
            title=item.task.title,
            status=item.task.status,
            priority=item.task.priority,
            input_summary=item.task.input_summary,
            acceptance_criteria=item.task.acceptance_criteria,
            depends_on_task_ids=item.task.depends_on_task_ids,
            child_task_ids=item.child_task_ids,
            depth=item.depth,
            risk_level=item.task.risk_level,
            owner_role_code=item.task.owner_role_code,
            upstream_role_code=item.task.upstream_role_code,
            downstream_role_code=item.task.downstream_role_code,
            human_status=item.task.human_status,
            paused_reason=item.task.paused_reason,
            source_draft_id=item.task.source_draft_id,
            created_at=item.task.created_at,
            updated_at=item.task.updated_at,
        )


class ProjectDetailResponse(ProjectResponse):
    """Detailed project payload enriched with task-tree data."""

    tasks: list[ProjectTaskTreeItemResponse]
    stage_guard: "ProjectStageGuardResponse | None" = None
    stage_timeline: list["ProjectStageTimelineEntryResponse"] = Field(default_factory=list)
    sop_snapshot: ProjectSopSnapshotResponse | None = None

    @classmethod
    def from_detail(cls, detail: ProjectDetail) -> "ProjectDetailResponse":
        """Convert the Day04 project aggregate into an API DTO."""

        return cls(
            id=detail.project.id,
            name=detail.project.name,
            summary=detail.project.summary,
            status=detail.project.status,
            stage=detail.project.stage,
            task_stats=ProjectTaskStatsResponse.from_task_stats(detail.project.task_stats),
            repository_workspace=(
                RepositoryWorkspaceResponse.from_workspace(
                    detail.project.repository_workspace
                )
                if detail.project.repository_workspace is not None
                else None
            ),
            latest_repository_snapshot=(
                RepositorySnapshotResponse.from_snapshot(
                    detail.project.latest_repository_snapshot
                )
                if detail.project.latest_repository_snapshot is not None
                else None
            ),
            current_change_session=None,
            created_at=detail.project.created_at,
            updated_at=detail.project.updated_at,
            tasks=[
                ProjectTaskTreeItemResponse.from_service_item(item)
                for item in detail.task_tree
            ],
            stage_guard=(
                ProjectStageGuardResponse.from_guard(detail.stage_guard)
                if detail.stage_guard is not None
                else None
            ),
            stage_timeline=[
                ProjectStageTimelineEntryResponse.from_entry(entry)
                for entry in (detail.stage_timeline or [])
            ],
            sop_snapshot=(
                ProjectSopSnapshotResponse.from_snapshot(detail.sop_snapshot)
                if detail.sop_snapshot is not None
                else None
            ),
        )


class ProjectMemoryCountResponse(BaseModel):
    """One memory-category counter shown in the Day14 panel header."""

    memory_type: ProjectMemoryKind
    count: int

    @classmethod
    def from_count(cls, item: ProjectMemoryCount) -> "ProjectMemoryCountResponse":
        return cls(
            memory_type=item.memory_type,
            count=item.count,
        )


class ProjectMemoryItemResponse(BaseModel):
    """One project-memory record exposed to the Day14 UI."""

    memory_id: str
    memory_type: ProjectMemoryKind
    title: str
    summary: str
    detail: str | None = None
    stage: ProjectStage | None = None
    role_code: ProjectRoleCode | None = None
    actor_name: str | None = None
    source_kind: str
    source_label: str
    task_id: UUID | None = None
    run_id: UUID | None = None
    approval_id: UUID | None = None
    deliverable_id: UUID | None = None
    deliverable_version_id: UUID | None = None
    tags: list[str]
    created_at: datetime

    @classmethod
    def from_item(cls, item: ProjectMemoryItem) -> "ProjectMemoryItemResponse":
        return cls(
            memory_id=item.memory_id,
            memory_type=item.memory_type,
            title=item.title,
            summary=item.summary,
            detail=item.detail,
            stage=item.stage,
            role_code=item.role_code,
            actor_name=item.actor_name,
            source_kind=item.source_kind.value,
            source_label=item.source_label,
            task_id=item.task_id,
            run_id=item.run_id,
            approval_id=item.approval_id,
            deliverable_id=item.deliverable_id,
            deliverable_version_id=item.deliverable_version_id,
            tags=item.tags,
            created_at=item.created_at,
        )


class ProjectMemorySnapshotResponse(BaseModel):
    """Latest persisted Day14 project-memory snapshot."""

    project_id: UUID
    project_name: str
    generated_at: datetime
    total_memories: int
    counts: list[ProjectMemoryCountResponse]
    latest_items: list[ProjectMemoryItemResponse]


class ProjectCostDashboardModeBreakdownResponse(BaseModel):
    """Run aggregation grouped by token-accounting mode."""

    mode: str
    run_count: int
    total_estimated_cost_usd: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ProjectCostDashboardRoleBreakdownResponse(BaseModel):
    """Run aggregation grouped by owner role."""

    role_code: str
    run_count: int
    total_estimated_cost_usd: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ProjectCostDashboardThreadBreakdownResponse(BaseModel):
    """Run aggregation grouped by Day11 agent-thread sessions."""

    session_id: UUID
    task_id: UUID
    run_id: UUID
    status: str
    review_status: str
    current_phase: str
    owner_role_code: str
    total_estimated_cost_usd: float
    total_tokens: int
    updated_at: datetime


class ProjectCostDashboardCacheSummaryResponse(BaseModel):
    """Minimal cache-side summary for Day14 dashboard observations."""

    total_memories: int
    memory_type_counts: list[ProjectMemoryCountResponse] = Field(default_factory=list)
    cache_signal_note: str


class ProjectCostDashboardFallbackContractResponse(BaseModel):
    """Explicit fallback contract when token accounting is not fully provider-reported."""

    provider_reported_run_count: int
    heuristic_run_count: int
    missing_mode_run_count: int
    fallback_active: bool
    fallback_reason: str


class ProjectCostDashboardSnapshotResponse(BaseModel):
    """Day14 minimal cost/cache aggregation snapshot."""

    project_id: UUID
    project_name: str
    generated_at: datetime
    task_count: int
    task_count_with_runs: int
    run_count: int
    thread_count: int
    total_estimated_cost_usd: float
    avg_estimated_cost_per_run_usd: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    mode_breakdown: list[ProjectCostDashboardModeBreakdownResponse]
    role_breakdown: list[ProjectCostDashboardRoleBreakdownResponse]
    thread_breakdown: list[ProjectCostDashboardThreadBreakdownResponse]
    cache_summary: ProjectCostDashboardCacheSummaryResponse
    fallback_contract: ProjectCostDashboardFallbackContractResponse
    day15_smoke_routes: list[str] = Field(default_factory=list)


class ProjectMemorySearchHitResponse(BaseModel):
    """One lexical project-memory search hit."""

    score: float
    matched_terms: list[str]
    item: ProjectMemoryItemResponse

    @classmethod
    def from_hit(cls, hit: ProjectMemorySearchHit) -> "ProjectMemorySearchHitResponse":
        return cls(
            score=hit.score,
            matched_terms=hit.matched_terms,
            item=ProjectMemoryItemResponse.from_item(hit.item),
        )


class ProjectMemorySearchResponse(BaseModel):
    """Day14 memory-search payload returned to the frontend."""

    project_id: UUID
    query: str
    total_matches: int
    hits: list[ProjectMemorySearchHitResponse]

    @classmethod
    def from_result(
        cls,
        result: ProjectMemorySearchResult,
    ) -> "ProjectMemorySearchResponse":
        return cls(
            project_id=result.project_id,
            query=result.query,
            total_matches=result.total_matches,
            hits=[ProjectMemorySearchHitResponse.from_hit(hit) for hit in result.hits],
        )


class ProjectMemoryContextResponse(BaseModel):
    """Preview of task-scoped memory recall built via the context builder."""

    project_id: UUID
    task_id: UUID
    task_title: str
    query_text: str
    memory_count: int
    context_summary: str
    items: list[ProjectMemoryItemResponse]


class ProjectMemoryGovernanceStateResponse(BaseModel):
    """Day09 governance state consumed by Day10 control-surface actions."""

    project_id: UUID
    generated_at: datetime
    checkpoint_count: int
    latest_checkpoint_id: str | None = None
    latest_task_id: UUID | None = None
    latest_run_id: UUID | None = None
    latest_pressure_level: str | None = None
    latest_usage_ratio: float | None = None
    latest_bad_context_detected: bool
    latest_bad_context_reasons: list[str]
    latest_rolling_summary: str | None = None
    latest_compaction_applied: bool
    latest_compaction_reduction_ratio: float | None = None
    latest_compaction_reason_codes: list[str]
    latest_rehydrate_at: datetime | None = None
    latest_rehydrate_used_checkpoint_id: str | None = None
    latest_compacted_at: datetime | None = None
    latest_reset_at: datetime | None = None
    storage_path: str | None = None

    @classmethod
    def from_state(
        cls,
        state: MemoryGovernanceState,
    ) -> "ProjectMemoryGovernanceStateResponse":
        return cls(
            project_id=state.project_id,
            generated_at=state.generated_at,
            checkpoint_count=state.checkpoint_count,
            latest_checkpoint_id=state.latest_checkpoint_id,
            latest_task_id=state.latest_task_id,
            latest_run_id=state.latest_run_id,
            latest_pressure_level=state.latest_pressure_level,
            latest_usage_ratio=state.latest_usage_ratio,
            latest_bad_context_detected=state.latest_bad_context_detected,
            latest_bad_context_reasons=state.latest_bad_context_reasons,
            latest_rolling_summary=state.latest_rolling_summary,
            latest_compaction_applied=state.latest_compaction_applied,
            latest_compaction_reduction_ratio=state.latest_compaction_reduction_ratio,
            latest_compaction_reason_codes=state.latest_compaction_reason_codes,
            latest_rehydrate_at=state.latest_rehydrate_at,
            latest_rehydrate_used_checkpoint_id=state.latest_rehydrate_used_checkpoint_id,
            latest_compacted_at=state.latest_compacted_at,
            latest_reset_at=state.latest_reset_at,
            storage_path=state.storage_path,
        )


class ProjectMemoryGovernanceRehydrateResponse(BaseModel):
    """Manual rehydrate action response used by Day10 preview timeline."""

    project_id: UUID
    task_id: UUID | None = None
    used_checkpoint_id: str | None = None
    rehydrated_context_summary: str
    rehydrated: bool
    generated_at: datetime

    @classmethod
    def from_result(
        cls,
        result: MemoryRehydrateResult,
    ) -> "ProjectMemoryGovernanceRehydrateResponse":
        return cls(
            project_id=result.project_id,
            task_id=result.task_id,
            used_checkpoint_id=result.used_checkpoint_id,
            rehydrated_context_summary=result.rehydrated_context_summary,
            rehydrated=result.rehydrated,
            generated_at=result.generated_at,
        )


class ProjectMemoryGovernanceCompactRequest(BaseModel):
    """Optional compact action payload for Day10 manual controls."""

    target_chars: int = Field(default=900, ge=300, le=2_000)


class ProjectMemoryGovernanceCompactResponse(BaseModel):
    """Manual compact action response for Day10 control surface."""

    project_id: UUID
    checkpoint_id: str | None = None
    compacted_summary: str
    compacted_char_count: int
    reduction_ratio: float
    reason_codes: list[str]
    created_at: datetime

    @classmethod
    def from_record(
        cls,
        record: MemoryCompactionRecord,
    ) -> "ProjectMemoryGovernanceCompactResponse":
        return cls(
            project_id=record.project_id,
            checkpoint_id=record.checkpoint_id,
            compacted_summary=record.compacted_summary,
            compacted_char_count=record.compacted_char_count,
            reduction_ratio=record.reduction_ratio,
            reason_codes=record.reason_codes,
            created_at=record.created_at,
        )


class ProjectMemoryGovernanceResetResponse(BaseModel):
    """Reset-action response so Day10 can refresh control state."""

    project_id: UUID
    reset_performed: bool
    generated_at: datetime


class ProjectStageBlockingTaskResponse(BaseModel):
    """One task currently blocking project stage advancement."""

    task_id: UUID
    title: str
    status: TaskStatus
    blocking_reasons: list[str]

    @classmethod
    def from_item(
        cls,
        item: ProjectStageBlockingTask,
    ) -> "ProjectStageBlockingTaskResponse":
        """Convert one blocking-task domain object into an API DTO."""

        return cls(
            task_id=item.task_id,
            title=item.title,
            status=item.status,
            blocking_reasons=item.blocking_reasons,
        )


class ProjectMilestoneResponse(BaseModel):
    """One milestone shown by the Day04 project detail panel."""

    code: ProjectMilestoneCode
    title: str
    satisfied: bool
    summary: str
    blocking_reasons: list[str]
    related_task_ids: list[UUID]

    @classmethod
    def from_milestone(cls, milestone: ProjectMilestone) -> "ProjectMilestoneResponse":
        """Convert one milestone domain object into an API DTO."""

        return cls(
            code=milestone.code,
            title=milestone.title,
            satisfied=milestone.satisfied,
            summary=milestone.summary,
            blocking_reasons=milestone.blocking_reasons,
            related_task_ids=milestone.related_task_ids,
        )


class ProjectStageGuardResponse(BaseModel):
    """Current stage-guard evaluation attached to project detail."""

    current_stage: ProjectStage
    target_stage: ProjectStage | None = None
    can_advance: bool
    milestones: list[ProjectMilestoneResponse]
    blocking_reasons: list[str]
    blocking_tasks: list[ProjectStageBlockingTaskResponse]
    total_tasks: int
    ready_task_count: int
    completed_task_count: int
    current_stage_task_count: int
    current_stage_completed_task_count: int

    @classmethod
    def from_guard(cls, guard: ProjectStageGuard) -> "ProjectStageGuardResponse":
        """Convert one stage-guard domain object into an API DTO."""

        return cls(
            current_stage=guard.current_stage,
            target_stage=guard.target_stage,
            can_advance=guard.can_advance,
            milestones=[
                ProjectMilestoneResponse.from_milestone(item)
                for item in guard.milestones
            ],
            blocking_reasons=guard.blocking_reasons,
            blocking_tasks=[
                ProjectStageBlockingTaskResponse.from_item(item)
                for item in guard.blocking_tasks
            ],
            total_tasks=guard.total_tasks,
            ready_task_count=guard.ready_task_count,
            completed_task_count=guard.completed_task_count,
            current_stage_task_count=guard.current_stage_task_count,
            current_stage_completed_task_count=guard.current_stage_completed_task_count,
        )


class ProjectStageTimelineEntryResponse(BaseModel):
    """One auditable project stage action displayed in the Day04 timeline."""

    id: UUID
    from_stage: ProjectStage | None = None
    to_stage: ProjectStage
    outcome: ProjectStageHistoryOutcome
    note: str | None = None
    reasons: list[str]
    created_at: datetime

    @classmethod
    def from_entry(
        cls,
        entry: ProjectStageHistoryEntry,
    ) -> "ProjectStageTimelineEntryResponse":
        """Convert one stage-history entry into an API DTO."""

        return cls(
            id=entry.id,
            from_stage=entry.from_stage,
            to_stage=entry.to_stage,
            outcome=entry.outcome,
            note=entry.note,
            reasons=entry.reasons,
            created_at=entry.created_at,
        )


class ProjectStageAdvanceRequest(BaseModel):
    """Body accepted by the Day04 stage-advance endpoint."""

    note: str | None = Field(
        default=None,
        max_length=500,
        description="Optional operator note appended to the stage audit trail.",
    )


class ProjectStageAdvanceResponse(BaseModel):
    """Result returned after one explicit stage-advance attempt."""

    project_id: UUID
    previous_stage: ProjectStage
    attempted_stage: ProjectStage
    current_stage: ProjectStage
    advanced: bool
    message: str
    stage_guard: ProjectStageGuardResponse
    timeline_entry: ProjectStageTimelineEntryResponse

    @classmethod
    def from_result(
        cls,
        result: ProjectStageAdvanceResult,
    ) -> "ProjectStageAdvanceResponse":
        """Convert one stage-advance result into an API DTO."""

        return cls(
            project_id=result.project.id,
            previous_stage=result.previous_stage,
            attempted_stage=result.attempted_stage,
            current_stage=result.project.stage,
            advanced=result.advanced,
            message=result.message,
            stage_guard=ProjectStageGuardResponse.from_guard(result.stage_guard),
            timeline_entry=ProjectStageTimelineEntryResponse.from_entry(
                result.timeline_entry
            ),
        )


class ProjectSopTemplateSelectRequest(BaseModel):
    """Body accepted by the Day06 SOP template selection endpoint."""

    template_code: str = Field(
        min_length=1,
        max_length=100,
        description="Stable built-in SOP template code to bind to the project.",
    )


class ProjectSopGeneratedTaskResponse(BaseModel):
    """One SOP-generated task returned after template selection."""

    id: UUID
    title: str
    status: TaskStatus
    source_draft_id: str | None = None

    @classmethod
    def from_task(
        cls,
        task,
    ) -> "ProjectSopGeneratedTaskResponse":
        """Convert one created task into an API DTO."""

        return cls(
            id=task.id,
            title=task.title,
            status=task.status,
            source_draft_id=task.source_draft_id,
        )


class ProjectSopTemplateSelectResponse(BaseModel):
    """Result returned after binding a project to one SOP template."""

    project_id: UUID
    template_code: str
    template_name: str
    created_task_count: int
    message: str
    created_tasks: list[ProjectSopGeneratedTaskResponse]
    sop_snapshot: ProjectSopSnapshotResponse

    @classmethod
    def from_result(
        cls,
        result: ProjectSopSelectionResult,
    ) -> "ProjectSopTemplateSelectResponse":
        """Convert one SOP selection result into an API DTO."""

        return cls(
            project_id=result.project.id,
            template_code=result.template.code,
            template_name=result.template.name,
            created_task_count=len(result.created_tasks),
            message=result.message,
            created_tasks=[
                ProjectSopGeneratedTaskResponse.from_task(task)
                for task in result.created_tasks
            ],
            sop_snapshot=ProjectSopSnapshotResponse.from_snapshot(result.snapshot),
        )


PROJECT_TIMELINE_EVENT_TYPE_ORDER = [
    "stage",
    "deliverable",
    "preflight",
    "approval",
    "role_handoff",
    "decision",
]

PROJECT_TIMELINE_EVENT_TYPE_LABELS = {
    "stage": "阶段推进",
    "deliverable": "交付件提交",
    "preflight": "执行前预检",
    "approval": "审批动作",
    "role_handoff": "角色交接",
    "decision": "运行决策",
}


class ProjectTimelineEventTypeCountResponse(BaseModel):
    """One filter bucket shown on top of the Day11 project timeline."""

    event_type: str
    label: str
    count: int


class ProjectTimelineEventResponse(BaseModel):
    """One normalized event node returned by the Day11 project timeline API."""

    id: str
    event_type: str
    label: str
    tone: str
    title: str
    summary: str
    occurred_at: datetime
    stage: ProjectStage | None = None
    task_id: UUID | None = None
    task_title: str | None = None
    run_id: UUID | None = None
    deliverable_id: UUID | None = None
    deliverable_title: str | None = None
    deliverable_version_id: UUID | None = None
    deliverable_version_number: int | None = None
    approval_id: UUID | None = None
    approval_status: str | None = None
    source_event: str | None = None
    actor: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectTimelineResponse(BaseModel):
    """Project-level cross-domain timeline returned by the Day11 endpoint."""

    project_id: UUID
    generated_at: datetime
    total_events: int
    event_type_counts: list[ProjectTimelineEventTypeCountResponse]
    events: list[ProjectTimelineEventResponse]


def _build_project_stack(session: Session) -> tuple[ProjectService, ProjectStageService, SopEngineService]:
    """Create the shared Day06 service stack used by project endpoints."""

    project_repository = ProjectRepository(session)
    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    project_role_repository = ProjectRoleRepository(session)
    project_memory_service = ProjectMemoryService(
        project_repository=project_repository,
        task_repository=task_repository,
        run_repository=run_repository,
        deliverable_repository=DeliverableRepository(session),
        approval_repository=ApprovalRepository(session),
        failure_review_service=FailureReviewService(
            failure_review_repository=FailureReviewRepository(),
            run_logging_service=RunLoggingService(),
        ),
    )
    task_state_machine_service = TaskStateMachineService()
    task_readiness_service = TaskReadinessService(
        task_repository=task_repository,
        run_repository=run_repository,
    )
    context_builder_service = ContextBuilderService(
        run_repository=run_repository,
        task_readiness_service=task_readiness_service,
        project_memory_service=project_memory_service,
    )
    role_catalog_service = RoleCatalogService(
        project_repository=project_repository,
        project_role_repository=project_role_repository,
    )
    approval_service = ApprovalService(
        approval_repository=ApprovalRepository(session),
        deliverable_repository=DeliverableRepository(session),
        project_repository=project_repository,
    )
    task_service = TaskService(
        task_repository=task_repository,
        project_repository=project_repository,
        budget_guard_service=BudgetGuardService(run_repository=run_repository),
        task_state_machine_service=task_state_machine_service,
        role_catalog_service=role_catalog_service,
    )
    sop_engine_service = SopEngineService(
        project_repository=project_repository,
        task_repository=task_repository,
        task_service=task_service,
        role_catalog_service=role_catalog_service,
        context_builder_service=context_builder_service,
        task_state_machine_service=task_state_machine_service,
    )
    project_stage_service = ProjectStageService(
        project_repository=project_repository,
        task_repository=task_repository,
        task_readiness_service=task_readiness_service,
        task_state_machine_service=task_state_machine_service,
        sop_engine_service=sop_engine_service,
        approval_service=approval_service,
    )
    project_service = ProjectService(
        project_repository=project_repository,
        task_repository=task_repository,
        project_stage_service=project_stage_service,
        sop_engine_service=sop_engine_service,
    )
    return project_service, project_stage_service, sop_engine_service


def _build_project_memory_stack(
    session: Session,
) -> tuple[TaskRepository, ContextBuilderService, ProjectMemoryService]:
    """Create the Day14 project-memory dependencies."""

    project_repository = ProjectRepository(session)
    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    project_memory_service = ProjectMemoryService(
        project_repository=project_repository,
        task_repository=task_repository,
        run_repository=run_repository,
        deliverable_repository=DeliverableRepository(session),
        approval_repository=ApprovalRepository(session),
        failure_review_service=FailureReviewService(
            failure_review_repository=FailureReviewRepository(),
            run_logging_service=RunLoggingService(),
        ),
    )
    context_builder_service = ContextBuilderService(
        run_repository=run_repository,
        task_readiness_service=TaskReadinessService(
            task_repository=task_repository,
            run_repository=run_repository,
        ),
        project_memory_service=project_memory_service,
        context_budget_service=ContextBudgetService(),
        memory_compaction_service=MemoryCompactionService(),
    )
    return task_repository, context_builder_service, project_memory_service


def _build_project_timeline_stack(
    session: Session,
) -> tuple[
    ProjectRepository,
    TaskRepository,
    RunRepository,
    DeliverableService,
    ApprovalService,
    ChangeRiskGuardService,
    DecisionReplayService,
]:
    """Create the Day11 project-timeline stack."""

    project_repository = ProjectRepository(session)
    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    deliverable_repository = DeliverableRepository(session)
    approval_repository = ApprovalRepository(session)

    deliverable_service = DeliverableService(
        deliverable_repository=deliverable_repository,
        project_repository=project_repository,
        task_repository=task_repository,
        run_repository=run_repository,
    )
    approval_service = ApprovalService(
        approval_repository=approval_repository,
        deliverable_repository=deliverable_repository,
        project_repository=project_repository,
    )
    change_risk_guard_service = ChangeRiskGuardService(
        change_batch_repository=ChangeBatchRepository(session),
        project_repository=project_repository,
    )
    run_logging_service = RunLoggingService()
    decision_replay_service = DecisionReplayService(
        run_logging_service=run_logging_service,
        failure_review_service=FailureReviewService(
            failure_review_repository=FailureReviewRepository(),
            run_logging_service=run_logging_service,
        ),
    )

    return (
        project_repository,
        task_repository,
        run_repository,
        deliverable_service,
        approval_service,
        change_risk_guard_service,
        decision_replay_service,
    )


def _build_project_timeline_type_counts(
    events: list[ProjectTimelineEventResponse],
) -> list[ProjectTimelineEventTypeCountResponse]:
    """Build stable filter buckets for the Day11 timeline UI."""

    counter = Counter(event.event_type for event in events)
    return [
        ProjectTimelineEventTypeCountResponse(
            event_type=event_type,
            label=PROJECT_TIMELINE_EVENT_TYPE_LABELS[event_type],
            count=counter.get(event_type, 0),
        )
        for event_type in PROJECT_TIMELINE_EVENT_TYPE_ORDER
    ]


def _build_stage_timeline_events(
    project,
) -> list[ProjectTimelineEventResponse]:
    """Convert project stage-history entries into timeline events."""

    events: list[ProjectTimelineEventResponse] = []
    for entry in project.stage_history:
        if entry.outcome == ProjectStageHistoryOutcome.APPLIED:
            title = (
                f"项目进入 {entry.to_stage.value} 阶段"
                if entry.from_stage is not None
                else f"项目以 {entry.to_stage.value} 阶段创建"
            )
            summary = entry.note or "记录了一次阶段推进。"
            tone = "success"
        else:
            title = f"阶段推进受阻：{entry.to_stage.value}"
            summary = entry.note or "当前阶段仍存在阻塞项，暂时无法推进。"
            tone = "warning"

        events.append(
            ProjectTimelineEventResponse(
                id=f"stage:{entry.id}",
                event_type="stage",
                label=PROJECT_TIMELINE_EVENT_TYPE_LABELS["stage"],
                tone=tone,
                title=title,
                summary=summary,
                occurred_at=entry.created_at,
                stage=entry.to_stage,
                metadata={
                    "from_stage": entry.from_stage.value if entry.from_stage is not None else None,
                    "to_stage": entry.to_stage.value,
                    "outcome": entry.outcome.value,
                    "reasons": list(entry.reasons),
                },
            )
        )

    return events


def _build_deliverable_timeline_events(
    entries: list[DeliverableTimelineEntry],
    *,
    task_title_map: dict[UUID, str],
) -> list[ProjectTimelineEventResponse]:
    """Convert deliverable-version submissions into timeline events."""

    return [
        ProjectTimelineEventResponse(
            id=f"deliverable:{entry.version.id}",
            event_type="deliverable",
            label=PROJECT_TIMELINE_EVENT_TYPE_LABELS["deliverable"],
            tone="info",
            title=(
                f"提交交付件《{entry.deliverable.title}》"
                f" v{entry.version.version_number}"
            ),
            summary=entry.version.summary,
            occurred_at=entry.version.created_at,
            stage=entry.deliverable.stage,
            task_id=entry.version.source_task_id,
            task_title=(
                task_title_map.get(entry.version.source_task_id)
                if entry.version.source_task_id is not None
                else None
            ),
            run_id=entry.version.source_run_id,
            deliverable_id=entry.deliverable.id,
            deliverable_title=entry.deliverable.title,
            deliverable_version_id=entry.version.id,
            deliverable_version_number=entry.version.version_number,
            actor=entry.version.author_role_code.value,
            metadata={
                "deliverable_type": entry.deliverable.type.value,
                "content_format": entry.version.content_format.value,
                "author_role_code": entry.version.author_role_code.value,
            },
        )
        for entry in entries
    ]


def _build_approval_timeline_events(
    entries: list[ApprovalTimelineEntry],
) -> list[ProjectTimelineEventResponse]:
    """Convert approval requests / decisions into timeline events."""

    events: list[ProjectTimelineEventResponse] = []
    for entry in entries:
        if entry.event_kind == "request":
            title = (
                f"发起审批《{entry.approval.deliverable_title}》"
                f" v{entry.approval.deliverable_version_number}"
            )
            summary = entry.approval.request_note or "等待老板审批结论。"
            tone = "danger" if entry.overdue else "warning"
            metadata: dict[str, Any] = {
                "event_kind": entry.event_kind,
                "requester_role_code": entry.approval.requester_role_code.value,
                "due_at": entry.approval.due_at.isoformat(),
                "overdue": entry.overdue,
            }
            actor = entry.approval.requester_role_code.value
            source_event = "approval_request"
        else:
            assert entry.decision is not None
            title = (
                f"审批结论：{entry.approval.deliverable_title}"
                f" v{entry.approval.deliverable_version_number}"
            )
            summary = entry.decision.summary
            if entry.decision.action == ApprovalDecisionAction.APPROVE:
                tone = "success"
            elif entry.decision.action == ApprovalDecisionAction.REJECT:
                tone = "danger"
            else:
                tone = "warning"
            metadata = {
                "event_kind": entry.event_kind,
                "action": entry.decision.action.value,
                "comment": entry.decision.comment,
                "highlighted_risks": list(entry.decision.highlighted_risks),
                "requested_changes": list(entry.decision.requested_changes),
            }
            actor = entry.decision.actor_name
            source_event = "approval_decision"

        events.append(
            ProjectTimelineEventResponse(
                id=(
                    f"approval-request:{entry.approval.id}"
                    if entry.event_kind == "request"
                    else f"approval-decision:{entry.decision.id}"
                ),
                event_type="approval",
                label=PROJECT_TIMELINE_EVENT_TYPE_LABELS["approval"],
                tone=tone,
                title=title,
                summary=summary,
                occurred_at=entry.occurred_at,
                stage=entry.approval.deliverable_stage,
                deliverable_id=entry.approval.deliverable_id,
                deliverable_title=entry.approval.deliverable_title,
                deliverable_version_id=entry.approval.deliverable_version_id,
                deliverable_version_number=entry.approval.deliverable_version_number,
                approval_id=entry.approval.id,
                approval_status=entry.approval.status.value,
                source_event=source_event,
                actor=actor,
                metadata=metadata,
            )
        )

    return events


def _build_preflight_timeline_events(
    entries: list[ChangeBatchPreflightTimelineEntry],
) -> list[ProjectTimelineEventResponse]:
    """Convert Day08 preflight and manual-confirmation events into timeline events."""

    events: list[ProjectTimelineEventResponse] = []
    for entry in entries:
        if entry.event_kind == "manual_confirmation_approved":
            title = f"人工放行变更批次《{entry.change_batch_title}》"
            tone = "success"
        elif entry.event_kind == "manual_confirmation_rejected":
            title = f"人工驳回变更批次《{entry.change_batch_title}》"
            tone = "danger"
        elif entry.event_kind == "manual_confirmation_requested":
            title = f"等待人工确认《{entry.change_batch_title}》"
            tone = "warning"
        else:
            title = f"执行前预检《{entry.change_batch_title}》"
            tone = (
                "success"
                if entry.preflight_status == "ready_for_execution"
                else "warning"
            )

        severity_value = (
            entry.overall_severity.value
            if entry.overall_severity is not None
            else None
        )
        events.append(
            ProjectTimelineEventResponse(
                id=f"preflight:{entry.change_batch_id}:{entry.event_kind}:{entry.occurred_at.isoformat()}",
                event_type="preflight",
                label=PROJECT_TIMELINE_EVENT_TYPE_LABELS["preflight"],
                tone=tone,
                title=title,
                summary=entry.summary,
                occurred_at=entry.occurred_at,
                actor=(
                    "老板"
                    if entry.event_kind.startswith("manual_confirmation_")
                    else "执行前守卫"
                ),
                metadata={
                    "change_batch_id": str(entry.change_batch_id),
                    "change_batch_title": entry.change_batch_title,
                    "event_kind": entry.event_kind,
                    "preflight_status": entry.preflight_status.value,
                    "manual_confirmation_status": entry.manual_confirmation_status.value,
                    "overall_severity": severity_value,
                },
            )
        )

    return events


def _build_decision_timeline_events(
    entries: list[ProjectDecisionTimelineEntry],
) -> list[ProjectTimelineEventResponse]:
    """Convert run-log replay events into Day11 timeline events."""

    events: list[ProjectTimelineEventResponse] = []
    for entry in entries:
        if entry.timeline_type == "role_handoff":
            title = "角色交接"
            tone = "info"
        else:
            title = entry.trace_item.title
            tone = _map_timeline_level_to_tone(entry.trace_item.level)

        metadata = dict(entry.trace_item.data)
        metadata["run_status"] = entry.run_status.value
        events.append(
            ProjectTimelineEventResponse(
                id=(
                    f"run:{entry.run_id}:{entry.trace_item.event}:"
                    f"{entry.occurred_at.isoformat()}"
                ),
                event_type=entry.timeline_type,
                label=PROJECT_TIMELINE_EVENT_TYPE_LABELS[entry.timeline_type],
                tone=tone,
                title=title,
                summary=entry.trace_item.summary,
                occurred_at=entry.occurred_at,
                task_id=entry.task_id,
                task_title=entry.task_title,
                run_id=entry.run_id,
                source_event=entry.trace_item.event,
                actor=None,
                metadata=metadata,
            )
        )

    return events


def _map_timeline_level_to_tone(level: str) -> str:
    """Map structured log levels into UI badge tones."""

    normalized_level = level.lower().strip()
    if normalized_level in {"error", "critical"}:
        return "danger"
    if normalized_level in {"warning", "warn"}:
        return "warning"
    if normalized_level == "success":
        return "success"
    return "info"


def get_project_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectService:
    """Create the project service dependency."""

    return _build_project_stack(session)[0]


def get_project_stage_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectStageService:
    """Create the Day04/Day06 project-stage guard dependency."""

    return _build_project_stack(session)[1]


def get_sop_engine_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> SopEngineService:
    """Create the Day06 SOP engine dependency."""

    return _build_project_stack(session)[2]


def get_project_memory_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectMemoryService:
    """Create the Day14 project-memory dependency."""

    return _build_project_memory_stack(session)[2]


def get_repository_release_gate_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> RepositoryReleaseGateService:
    """Create the Day14 release-gate dependency used by the Day15 overview."""

    project_repository = ProjectRepository(session)
    repository_workspace_repository = RepositoryWorkspaceRepository(session)
    change_batch_repository = ChangeBatchRepository(session)
    commit_candidate_repository = CommitCandidateRepository(session)
    verification_run_repository = VerificationRunRepository(session)
    return RepositoryReleaseGateService(
        project_repository=project_repository,
        repository_workspace_repository=repository_workspace_repository,
        repository_snapshot_repository=RepositorySnapshotRepository(session),
        change_batch_repository=change_batch_repository,
        commit_candidate_repository=commit_candidate_repository,
        verification_run_repository=verification_run_repository,
        diff_summary_service=DiffSummaryService(
            project_repository=project_repository,
            repository_workspace_repository=repository_workspace_repository,
            change_batch_repository=change_batch_repository,
            deliverable_repository=DeliverableRepository(session),
            approval_repository=ApprovalRepository(session),
            verification_run_repository=verification_run_repository,
        ),
    )


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
)
def create_project(
    request: ProjectCreateRequest,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectResponse:
    """Create one project."""

    try:
        project = project_service.create_project(
            name=request.name,
            summary=request.summary,
            status=request.status,
            stage=request.stage,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    current_change_session: ChangeSession | None = None
    try:
        # Keep project creation resilient even if Day03 change-session storage is unavailable.
        current_change_session = ChangeSessionRepository(session).get_by_project_id(project.id)
    except SQLAlchemyError:
        session.rollback()

    return ProjectResponse.from_project(
        project,
        current_change_session=current_change_session,
    )


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List projects",
)
def list_projects(
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[ProjectResponse]:
    """Return all projects."""

    projects = project_service.list_projects()
    change_session_repository = ChangeSessionRepository(session)
    return [
        ProjectResponse.from_project(
            project,
            current_change_session=change_session_repository.get_by_project_id(project.id),
        )
        for project in projects
    ]


@router.get(
    "/sop-templates",
    response_model=list[ProjectSopTemplateSummaryResponse],
    summary="List available SOP templates",
)
def list_sop_templates(
    sop_engine_service: Annotated[SopEngineService, Depends(get_sop_engine_service)],
) -> list[ProjectSopTemplateSummaryResponse]:
    """Return the Day06 built-in SOP template catalog."""

    return [
        ProjectSopTemplateSummaryResponse.from_summary(template)
        for template in sop_engine_service.list_template_summaries()
    ]


@router.put(
    "/{project_id}/sop-template",
    response_model=ProjectSopTemplateSelectResponse,
    summary="Bind one project to a SOP template",
)
def select_project_sop_template(
    project_id: UUID,
    request: ProjectSopTemplateSelectRequest,
    sop_engine_service: Annotated[SopEngineService, Depends(get_sop_engine_service)],
) -> ProjectSopTemplateSelectResponse:
    """Bind one project to a Day06 SOP template and sync current-stage tasks."""

    try:
        result = sop_engine_service.select_project_template(
            project_id=project_id,
            template_code=request.template_code,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return ProjectSopTemplateSelectResponse.from_result(result)


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Get project detail",
)
def get_project(
    project_id: UUID,
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDetailResponse:
    """Return one project by ID."""

    detail = project_service.get_project_detail(project_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    response = ProjectDetailResponse.from_detail(detail)
    change_session = ChangeSessionRepository(session).get_by_project_id(project_id)
    return response.model_copy(
        update={
            "current_change_session": (
                ChangeSessionResponse.from_change_session(change_session)
                if change_session is not None
                else None
            )
        }
    )


@router.get(
    "/{project_id}/day15-repository-flow",
    response_model=ProjectDay15FlowOverviewResponse,
    summary="Get the Day15 minimum closed-loop overview for one project",
)
def get_project_day15_repository_flow(
    project_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    repository_release_gate_service: Annotated[
        RepositoryReleaseGateService,
        Depends(get_repository_release_gate_service),
    ],
) -> ProjectDay15FlowOverviewResponse:
    """Return a boss-facing Day15 read-only closed-loop overview."""

    try:
        flow = build_repository_day15_flow_snapshot(
            project_id=project_id,
            project_repository=ProjectRepository(session),
            change_plan_repository=ChangePlanRepository(session),
            change_batch_repository=ChangeBatchRepository(session),
            repository_release_gate_service=repository_release_gate_service,
        )
    except (
        RepositoryReleaseGateProjectNotFoundError,
        RepositoryReleaseGateChangeBatchNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if flow.overall_status == RepositoryDay15FlowStatus.BLOCKED:
        summary = "闭环存在缺口，当前可审阅并可拒绝，但不满足放行条件。"
    elif flow.overall_status == RepositoryDay15FlowStatus.READY_FOR_REVIEW:
        summary = "闭环链路已齐备，可审阅、可解释、可拒绝。"
    else:
        summary = "闭环链路进行中，仍有步骤待补齐。"

    return ProjectDay15FlowOverviewResponse(
        project_id=flow.project_id,
        project_name=flow.project_name,
        generated_at=flow.generated_at,
        overall_status=flow.overall_status,
        summary=summary,
        completed_step_count=flow.completed_step_count,
        total_step_count=flow.total_step_count,
        blocked_step_count=flow.blocked_step_count,
        selected_change_batch_id=flow.selected_change_batch_id,
        selected_change_batch_title=flow.selected_change_batch_title,
        release_status=flow.release_status.value if flow.release_status else None,
        release_qualification_established=flow.release_qualification_established,
        git_write_actions_triggered=flow.git_write_actions_triggered,
    )


@router.get(
    "/{project_id}/cost-dashboard",
    response_model=ProjectCostDashboardSnapshotResponse,
    summary="Get the Day14 minimal cost/cache dashboard snapshot",
)
def get_project_cost_dashboard_snapshot(
    project_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    project_memory_service: Annotated[
        ProjectMemoryService, Depends(get_project_memory_service)
    ],
) -> ProjectCostDashboardSnapshotResponse:
    """Return project-scoped Day14 cost aggregation with explicit fallback semantics."""

    project_repository = ProjectRepository(session)
    task_repository = TaskRepository(session)
    run_repository = RunRepository(session)
    agent_session_repository = AgentSessionRepository(session)

    project = project_repository.get_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    tasks = task_repository.list_by_project_id(project_id)
    task_ids = [task.id for task in tasks]
    runs = run_repository.list_by_task_ids(task_ids)

    total_prompt_tokens = sum(run.prompt_tokens for run in runs)
    total_completion_tokens = sum(run.completion_tokens for run in runs)
    total_estimated_cost = round(sum(run.estimated_cost for run in runs), 6)
    task_count_with_runs = len({run.task_id for run in runs})

    mode_accumulator: dict[str, dict[str, float]] = {}
    role_accumulator: dict[str, dict[str, float]] = {}
    mode_counter = Counter((run.token_accounting_mode or "missing") for run in runs)

    for run in runs:
        mode_key = run.token_accounting_mode or "missing"
        role_key = (
            run.owner_role_code.value if run.owner_role_code is not None else "unassigned"
        )

        mode_bucket = mode_accumulator.setdefault(
            mode_key,
            {
                "run_count": 0.0,
                "cost": 0.0,
                "prompt_tokens": 0.0,
                "completion_tokens": 0.0,
                "total_tokens": 0.0,
            },
        )
        mode_bucket["run_count"] += 1
        mode_bucket["cost"] += run.estimated_cost
        mode_bucket["prompt_tokens"] += run.prompt_tokens
        mode_bucket["completion_tokens"] += run.completion_tokens
        mode_bucket["total_tokens"] += run.total_tokens

        role_bucket = role_accumulator.setdefault(
            role_key,
            {
                "run_count": 0.0,
                "cost": 0.0,
                "prompt_tokens": 0.0,
                "completion_tokens": 0.0,
                "total_tokens": 0.0,
            },
        )
        role_bucket["run_count"] += 1
        role_bucket["cost"] += run.estimated_cost
        role_bucket["prompt_tokens"] += run.prompt_tokens
        role_bucket["completion_tokens"] += run.completion_tokens
        role_bucket["total_tokens"] += run.total_tokens

    mode_breakdown = [
        ProjectCostDashboardModeBreakdownResponse(
            mode=mode,
            run_count=int(values["run_count"]),
            total_estimated_cost_usd=round(float(values["cost"]), 6),
            prompt_tokens=int(values["prompt_tokens"]),
            completion_tokens=int(values["completion_tokens"]),
            total_tokens=int(values["total_tokens"]),
        )
        for mode, values in sorted(
            mode_accumulator.items(),
            key=lambda item: (-item[1]["run_count"], item[0]),
        )
    ]
    role_breakdown = [
        ProjectCostDashboardRoleBreakdownResponse(
            role_code=role_code,
            run_count=int(values["run_count"]),
            total_estimated_cost_usd=round(float(values["cost"]), 6),
            prompt_tokens=int(values["prompt_tokens"]),
            completion_tokens=int(values["completion_tokens"]),
            total_tokens=int(values["total_tokens"]),
        )
        for role_code, values in sorted(
            role_accumulator.items(),
            key=lambda item: (-item[1]["run_count"], item[0]),
        )
    ]
    run_by_id = {run.id: run for run in runs}
    thread_breakdown: list[ProjectCostDashboardThreadBreakdownResponse] = []
    for session_item in agent_session_repository.list_by_project_id(
        project_id=project_id,
        limit=max(len(runs), 20),
    ):
        bound_run = run_by_id.get(session_item.run_id)
        if bound_run is None:
            continue
        thread_breakdown.append(
            ProjectCostDashboardThreadBreakdownResponse(
                session_id=session_item.id,
                task_id=session_item.task_id,
                run_id=session_item.run_id,
                status=session_item.status.value,
                review_status=session_item.review_status.value,
                current_phase=session_item.current_phase.value,
                owner_role_code=(
                    session_item.owner_role_code.value
                    if session_item.owner_role_code is not None
                    else "unassigned"
                ),
                total_estimated_cost_usd=round(bound_run.estimated_cost, 6),
                total_tokens=bound_run.total_tokens,
                updated_at=session_item.updated_at,
            )
        )

    memory_snapshot = project_memory_service.get_project_memory_snapshot(project_id=project_id)
    if memory_snapshot is None:
        memory_type_counts: list[ProjectMemoryCountResponse] = []
        total_memories = 0
        cache_signal_note = (
            "Day14 memory snapshot is unavailable. Cache-side observation is currently missing."
        )
    else:
        memory_type_counts = [
            ProjectMemoryCountResponse.from_count(item) for item in memory_snapshot.counts
        ]
        total_memories = memory_snapshot.total_memories
        cache_signal_note = (
            "Cache signal currently uses Day14 project-memory counts, "
            "not provider-level cache hit/miss telemetry."
        )

    provider_reported_run_count = mode_counter.get("provider_reported", 0)
    heuristic_run_count = mode_counter.get("heuristic", 0)
    missing_mode_run_count = mode_counter.get("missing", 0)
    fallback_active = heuristic_run_count > 0 or missing_mode_run_count > 0
    fallback_reason = (
        "At least one run still uses heuristic/missing token accounting mode; "
        "Day14 cost totals must be treated as fallback estimates."
        if fallback_active
        else "All runs in the current slice are provider_reported."
    )

    return ProjectCostDashboardSnapshotResponse(
        project_id=project.id,
        project_name=project.name,
        generated_at=utc_now(),
        task_count=len(tasks),
        task_count_with_runs=task_count_with_runs,
        run_count=len(runs),
        thread_count=len(thread_breakdown),
        total_estimated_cost_usd=total_estimated_cost,
        avg_estimated_cost_per_run_usd=(
            round(total_estimated_cost / len(runs), 6) if runs else 0.0
        ),
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_prompt_tokens + total_completion_tokens,
        mode_breakdown=mode_breakdown,
        role_breakdown=role_breakdown,
        thread_breakdown=thread_breakdown,
        cache_summary=ProjectCostDashboardCacheSummaryResponse(
            total_memories=total_memories,
            memory_type_counts=memory_type_counts,
            cache_signal_note=cache_signal_note,
        ),
        fallback_contract=ProjectCostDashboardFallbackContractResponse(
            provider_reported_run_count=provider_reported_run_count,
            heuristic_run_count=heuristic_run_count,
            missing_mode_run_count=missing_mode_run_count,
            fallback_active=fallback_active,
            fallback_reason=fallback_reason,
        ),
        day15_smoke_routes=[
            "GET /projects/{project_id}/team-control-center",
            "GET /projects/{project_id}/cost-dashboard",
            "POST /workers/run-once?project_id={project_id}",
            "GET /projects/{project_id}/memory",
        ],
    )


@router.get(
    "/{project_id}/memory",
    response_model=ProjectMemorySnapshotResponse,
    summary="Get the Day14 project-memory snapshot",
)
def get_project_memory_snapshot(
    project_id: UUID,
    project_memory_service: Annotated[
        ProjectMemoryService, Depends(get_project_memory_service)
    ],
    limit: int = 8,
) -> ProjectMemorySnapshotResponse:
    """Return the latest Day14 project-memory snapshot for one project."""

    snapshot = project_memory_service.get_project_memory_snapshot(project_id=project_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return ProjectMemorySnapshotResponse(
        project_id=snapshot.project_id,
        project_name=snapshot.project_name,
        generated_at=snapshot.generated_at,
        total_memories=snapshot.total_memories,
        counts=[ProjectMemoryCountResponse.from_count(item) for item in snapshot.counts],
        latest_items=[
            ProjectMemoryItemResponse.from_item(item)
            for item in snapshot.items[: max(limit, 0)]
        ],
    )


@router.get(
    "/{project_id}/memory/search",
    response_model=ProjectMemorySearchResponse,
    summary="Search Day14 project memories",
)
def search_project_memory(
    project_id: UUID,
    project_memory_service: Annotated[
        ProjectMemoryService, Depends(get_project_memory_service)
    ],
    q: str = "",
    limit: int = 10,
    memory_type: ProjectMemoryKind | None = None,
) -> ProjectMemorySearchResponse:
    """Run a minimal lexical search across one project's Day14 memories."""

    result = project_memory_service.search_project_memories(
        project_id=project_id,
        query=q,
        limit=limit,
        memory_type=memory_type,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return ProjectMemorySearchResponse.from_result(result)


@router.get(
    "/{project_id}/memory/context",
    response_model=ProjectMemoryContextResponse,
    summary="Preview task-scoped memory recall for one project task",
)
def get_project_memory_context(
    project_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
    task_id: UUID,
    limit: int = 3,
) -> ProjectMemoryContextResponse:
    """Return the task-scoped Day14 memory recall used by context building."""

    task_repository, context_builder_service, _ = _build_project_memory_stack(session)
    task = task_repository.get_by_id(task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found in project: {task_id}",
        )

    memory_context = context_builder_service.build_task_memory_context(
        task=task,
        limit=limit,
    )
    if memory_context is None:
        return ProjectMemoryContextResponse(
            project_id=project_id,
            task_id=task.id,
            task_title=task.title,
            query_text="",
            memory_count=0,
            context_summary="Project memory recall is unavailable for the current task.",
            items=[],
        )

    return ProjectMemoryContextResponse(
        project_id=memory_context.project_id,
        task_id=memory_context.task_id,
        task_title=memory_context.task_title,
        query_text=memory_context.query_text,
        memory_count=len(memory_context.items),
        context_summary=memory_context.context_summary,
        items=[ProjectMemoryItemResponse.from_item(item) for item in memory_context.items],
    )


@router.get(
    "/{project_id}/memory/governance",
    response_model=ProjectMemoryGovernanceStateResponse,
    summary="Get Day09 memory-governance state",
)
def get_project_memory_governance_state(
    project_id: UUID,
    project_memory_service: Annotated[
        ProjectMemoryService, Depends(get_project_memory_service)
    ],
) -> ProjectMemoryGovernanceStateResponse:
    """Return Day09 checkpoint/bad-context/rehydrate governance state."""

    state = project_memory_service.get_memory_governance_state(project_id=project_id)
    return ProjectMemoryGovernanceStateResponse.from_state(state)


@router.post(
    "/{project_id}/memory/governance/rehydrate",
    response_model=ProjectMemoryGovernanceRehydrateResponse,
    summary="Trigger Day09 manual rehydrate preview",
)
def rehydrate_project_memory_governance(
    project_id: UUID,
    project_memory_service: Annotated[
        ProjectMemoryService, Depends(get_project_memory_service)
    ],
    task_id: UUID | None = None,
) -> ProjectMemoryGovernanceRehydrateResponse:
    """Trigger one manual rehydrate preview from latest checkpoints."""

    result = project_memory_service.rehydrate_context(
        project_id=project_id,
        task_id=task_id,
    )
    return ProjectMemoryGovernanceRehydrateResponse.from_result(result)


@router.post(
    "/{project_id}/memory/governance/compact",
    response_model=ProjectMemoryGovernanceCompactResponse,
    summary="Trigger Day09 manual compaction",
)
def compact_project_memory_governance(
    project_id: UUID,
    request: ProjectMemoryGovernanceCompactRequest,
    project_memory_service: Annotated[
        ProjectMemoryService, Depends(get_project_memory_service)
    ],
) -> ProjectMemoryGovernanceCompactResponse:
    """Compact latest checkpoint context for Day10 manual action entry."""

    record = project_memory_service.compact_latest_checkpoint(
        project_id=project_id,
        target_chars=request.target_chars,
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No governance checkpoint found for project: {project_id}",
        )

    return ProjectMemoryGovernanceCompactResponse.from_record(record)


@router.post(
    "/{project_id}/memory/governance/reset",
    response_model=ProjectMemoryGovernanceResetResponse,
    summary="Reset Day09 memory-governance artifacts",
)
def reset_project_memory_governance(
    project_id: UUID,
    project_memory_service: Annotated[
        ProjectMemoryService, Depends(get_project_memory_service)
    ],
) -> ProjectMemoryGovernanceResetResponse:
    """Reset governance checkpoint/compaction state for one project."""

    reset_performed = project_memory_service.reset_memory_governance(
        project_id=project_id,
    )
    return ProjectMemoryGovernanceResetResponse(
        project_id=project_id,
        reset_performed=reset_performed,
        generated_at=utc_now(),
    )


@router.get(
    "/{project_id}/timeline",
    response_model=ProjectTimelineResponse,
    summary="Get project timeline",
)
def get_project_timeline(
    project_id: UUID,
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectTimelineResponse:
    """Return the Day11 project-level timeline across stages, deliverables and runs."""

    (
        project_repository,
        task_repository,
        run_repository,
        deliverable_service,
        approval_service,
        change_risk_guard_service,
        decision_replay_service,
    ) = _build_project_timeline_stack(session)

    project = project_repository.get_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    tasks = task_repository.list_by_project_id(project_id)
    task_title_map = {task.id: task.title for task in tasks}
    runs = run_repository.list_by_task_ids(list(task_title_map))

    events: list[ProjectTimelineEventResponse] = []
    events.extend(_build_stage_timeline_events(project))

    deliverable_entries = deliverable_service.list_project_timeline_entries(project_id) or []
    events.extend(
        _build_deliverable_timeline_events(
            deliverable_entries,
            task_title_map=task_title_map,
        )
    )

    approval_entries = approval_service.list_project_timeline_entries(project_id) or []
    events.extend(_build_approval_timeline_events(approval_entries))

    preflight_entries = change_risk_guard_service.list_project_timeline_entries(project_id)
    events.extend(_build_preflight_timeline_events(preflight_entries))

    decision_entries = decision_replay_service.build_project_timeline_entries(
        runs=runs,
        task_titles=task_title_map,
    )
    events.extend(_build_decision_timeline_events(decision_entries))

    events.sort(key=lambda item: (item.occurred_at, item.id), reverse=True)
    return ProjectTimelineResponse(
        project_id=project_id,
        generated_at=utc_now(),
        total_events=len(events),
        event_type_counts=_build_project_timeline_type_counts(events),
        events=events,
    )


@router.post(
    "/{project_id}/advance-stage",
    response_model=ProjectStageAdvanceResponse,
    summary="Attempt to advance one project into the next stage",
)
def advance_project_stage(
    project_id: UUID,
    request: ProjectStageAdvanceRequest,
    project_stage_service: Annotated[
        ProjectStageService, Depends(get_project_stage_service)
    ],
) -> ProjectStageAdvanceResponse:
    """Attempt one Day04 project stage promotion and record the audit entry."""

    try:
        result = project_stage_service.advance_project_stage(
            project_id=project_id,
            note=request.note,
        )
    except ProjectStageTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )

    return ProjectStageAdvanceResponse.from_result(result)


ProjectDetailResponse.model_rebuild()
