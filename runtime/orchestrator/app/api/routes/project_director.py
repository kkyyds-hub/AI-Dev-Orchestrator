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

from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.api.schemas.project_director_plan import (
    PlanVersionListResponse,
    PlanVersionResponse,
    PlanVersionReviewResponse,
    ReviewPlanVersionRequest,
)
from app.api.schemas.project_director_session import (
    CreateSessionRequest,
    PostProjectDirectorMessageRequest,
    PostProjectDirectorMessageResponse,
    ProjectDirectorMessageListResponse,
    ProjectDirectorMessageResponse,
    SessionResponse,
    SubmitAnswersRequest,
)
from app.api.schemas.project_director_workbench import (
    ConversationListItemResponse,
    ConversationListResponse,
    ConversationTaskCreationResponse,
    ConversationTimelineItemResponse,
    ConversationTimelineResponse,
    DirectorInboxItemResponse,
    DirectorInboxResponse,
    TaskCreationResponse,
    WorkbenchResumableSessionSummary,
    WorkbenchResumableSessionsResponse,
)
from app.domain.project_director_plan_version import (
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
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
    ConversationStatus,
    ProjectDirectorConversationService,
)
from app.services.project_director_inbox_service import (
    InboxItemKind,
    InboxItemPriority,
    InboxItemStatus,
    ProjectDirectorInboxService,
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
from app.services.project_director_evidence_to_agent_dry_run_service import (
    ProjectDirectorEvidenceToAgentDryRunService,
)
from app.services.project_director_dry_run_task_dispatch_service import (
    ProjectDirectorDryRunTaskDispatchService,
)
from app.services.project_director_controlled_executor_dispatch_service import (
    ProjectDirectorControlledExecutorDispatchService,
)
from app.services.project_director_readonly_review_service import (
    ProjectDirectorReadonlyReviewService,
)
from app.services.project_director_programmer_no_write_plan_service import (
    ProjectDirectorProgrammerNoWritePlanService,
)
from app.services.project_director_programmer_no_write_execution_service import (
    ProjectDirectorProgrammerNoWriteExecutionService,
)
from app.services.project_director_sandbox_write_preflight_service import (
    ProjectDirectorSandboxWritePreflightService,
)
from app.services.project_director_sandbox_write_execution_service import (
    ProjectDirectorSandboxWriteExecutionService,
)
from app.services.project_director_sandbox_write_design_lock_service import (
    ProjectDirectorSandboxWriteDesignLockService,
)
from app.services.project_director_sandbox_workspace_guard_service import (
    ProjectDirectorSandboxWorkspaceGuardService,
)
from app.services.project_director_sandbox_operation_manifest_guard_service import (
    ProjectDirectorSandboxOperationManifestGuardService,
)
from app.services.project_director_sandbox_workspace_creation_service import (
    ProjectDirectorSandboxWorkspaceCreationService,
)
from app.services.project_director_sandbox_workspace_manifest_write_service import (
    ProjectDirectorSandboxWorkspaceManifestWriteService,
)
from app.services.project_director_sandbox_candidate_file_write_service import (
    ProjectDirectorSandboxCandidateFileWriteService,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    ProjectDirectorSandboxCandidateDiffService,
)
from app.domain.project_director_sandbox_candidate_file_write import (
    CandidateSandboxFileWrite,
)
from app.domain.project_director_dry_run_task_dispatch import (
    ProjectDirectorDryRunTaskWorkerResult,
)
from app.domain.project_director_sandbox_write_preflight import (
    ProjectDirectorFileOperationPlan,
)


# ── Dependencies ────────────────────────────────────────────────────


REPO_ROOT = Path(__file__).resolve().parents[5]


class EvidenceToAgentDryRunRequest(BaseModel):
    user_goal: str = Field(min_length=1, max_length=5000)


class EvidenceToAgentDryRunSessionResponse(BaseModel):
    dry_run_summary: dict
    message: ProjectDirectorMessageResponse | None = None
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    ai_project_director_total_loop: str = "Partial"


class ConfirmDryRunTaskDispatchRequest(BaseModel):
    source_message_id: UUID
    user_confirmed: bool = False


class ConfirmDryRunTaskDispatchResponse(BaseModel):
    dispatch_status: Literal["dispatched", "blocked"]
    session_id: UUID
    source_message_id: UUID
    created_task_id: UUID | None = None
    evidence_pack_id: str | None = None
    safe_dry_run_task: bool = True
    worker_simulate_required: bool = True
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    ai_project_director_total_loop: str = "Partial"
    message_bound: bool = False
    message: ProjectDirectorMessageResponse | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class RecordDryRunTaskWorkerResultRequest(BaseModel):
    task_id: UUID
    run_id: UUID | None = None
    worker_run_once_ok: bool
    worker_simulate_mode: bool = True
    run_created: bool
    run_readback_ok: bool
    blocked_reasons: list[str] = Field(default_factory=list)


class RecordDryRunTaskWorkerResultResponse(BaseModel):
    session_id: UUID
    task_id: UUID
    run_id: UUID | None = None
    worker_run_once_ok: bool
    worker_simulate_mode: bool = True
    run_created: bool
    run_readback_ok: bool
    safe_dry_run_task: bool = True
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    ai_project_director_total_loop: str = "Partial"
    p9_production_safe_long_running_executor_lifecycle: str = "Partial"
    message_bound: bool = False
    message: ProjectDirectorMessageResponse | None = None
    blocked_reasons: list[str] = Field(default_factory=list)


class ConfirmControlledExecutorDispatchRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    requested_agent_role: Literal["programmer", "reviewer"] = "programmer"
    requested_executor: Literal["codex", "claude-code"] = "codex"
    launch_mode: Literal["dry_run", "controlled_smoke"] = "dry_run"


class ConfirmControlledExecutorDispatchResponse(BaseModel):
    dispatch_status: Literal["planned", "blocked", "launched"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    requested_agent_role: Literal["programmer", "reviewer"] = "programmer"
    requested_executor: Literal["codex", "claude-code"] = "codex"
    launch_mode: Literal["dry_run", "controlled_smoke"] = "dry_run"
    controlled_executor_pilot: bool = True
    executor_backed_agent: bool = True
    programmer_agent_allowed: bool = True
    reviewer_agent_allowed: bool = True
    supervisor_required: bool = True
    auto_terminate_required: bool = True
    cleanup_required: bool = True
    product_runtime_git_write_allowed: bool = False
    worktree_write_allowed: bool = False
    frontend_required: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    agent_session_bound: bool = False
    process_handle_id_present: bool = False
    supervisor_registered: bool = False
    supervisor_cleanup_done: bool = False
    run_created: bool = False
    ai_project_director_total_loop: str = "Partial"
    p9_production_safe_long_running_executor_lifecycle: str = "Partial"
    message_bound: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ConfirmReadonlyReviewRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    requested_reviewer_executor: Literal["codex", "claude-code"] = "codex"
    review_mode: Literal["dry_run", "fake_review", "controlled_review"] = "dry_run"


class ReadonlyReviewFindingResponse(BaseModel):
    finding_id: str
    severity: Literal["low", "medium", "high"]
    title: str
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    recommended_action: str


class ConfirmReadonlyReviewResponse(BaseModel):
    review_status: Literal["planned", "reviewed", "blocked"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    p14_lifecycle_message_id: UUID | None = None
    requested_reviewer_executor: Literal["codex", "claude-code"] = "codex"
    review_mode: Literal["dry_run", "fake_review", "controlled_review"] = "dry_run"
    readonly_review: bool = True
    reviewer_agent: bool = True
    executor_backed_review_allowed: bool = True
    product_runtime_git_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    review_result_message_bound: bool = False
    review_summary: str = ""
    review_findings: list[ReadonlyReviewFindingResponse] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"
    recommended_next_step: str = ""
    ai_project_director_total_loop: str = "Partial"
    message: ProjectDirectorMessageResponse | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ConfirmProgrammerNoWritePlanRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    requested_programmer_executor: Literal["codex", "claude-code"] = "codex"
    planning_mode: Literal["dry_run", "fake_plan", "controlled_no_write"] = "dry_run"


class ProgrammerNoWritePlannedStepResponse(BaseModel):
    step_id: str
    title: str
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    affected_files_preview: list[str] = Field(default_factory=list)
    required_targeted_tests: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class ConfirmProgrammerNoWritePlanResponse(BaseModel):
    plan_status: Literal["planned", "blocked"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    requested_programmer_executor: Literal["codex", "claude-code"] = "codex"
    planning_mode: Literal["dry_run", "fake_plan", "controlled_no_write"] = "dry_run"
    programmer_agent: bool = True
    controlled_programmer_planning: bool = True
    no_write_plan: bool = True
    executor_backed_programmer_allowed: bool = True
    product_runtime_git_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    plan_message_bound: bool = False
    implementation_summary: str = ""
    planned_steps: list[ProgrammerNoWritePlannedStepResponse] = Field(
        default_factory=list
    )
    affected_files_preview: list[str] = Field(default_factory=list)
    required_evidence_refs: list[str] = Field(default_factory=list)
    required_targeted_tests: list[str] = Field(default_factory=list)
    reviewer_feedback_refs: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"
    recommended_next_step: str = ""
    ai_project_director_total_loop: str = "Partial"
    message: ProjectDirectorMessageResponse | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ConfirmProgrammerNoWriteExecutionRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    requested_programmer_executor: Literal["codex", "claude-code"] = "codex"
    execution_mode: Literal[
        "dry_run", "fake_execution", "controlled_no_write"
    ] = "dry_run"


class ProgrammerNoWriteExecutionStepResponse(BaseModel):
    step_id: str
    title: str
    summary: str
    source_plan_step_ids: list[str] = Field(default_factory=list)
    files_considered: list[str] = Field(default_factory=list)
    patch_preview: list[str] = Field(default_factory=list)
    tests_to_run: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class ConfirmProgrammerNoWriteExecutionResponse(BaseModel):
    execution_status: Literal["planned", "executed", "blocked"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    requested_programmer_executor: Literal["codex", "claude-code"] = "codex"
    execution_mode: Literal[
        "dry_run", "fake_execution", "controlled_no_write"
    ] = "dry_run"
    programmer_agent: bool = True
    controlled_programmer_execution: bool = True
    no_write_execution: bool = True
    executor_backed_programmer_allowed: bool = True
    product_runtime_git_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    execution_message_bound: bool = False
    execution_summary: str = ""
    execution_steps: list[ProgrammerNoWriteExecutionStepResponse] = Field(
        default_factory=list
    )
    patch_preview: list[str] = Field(default_factory=list)
    files_considered: list[str] = Field(default_factory=list)
    tests_to_run: list[str] = Field(default_factory=list)
    implementation_notes: list[str] = Field(default_factory=list)
    handoff_notes: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"
    recommended_next_step: str = ""
    source_plan_refs: list[str] = Field(default_factory=list)
    ai_project_director_total_loop: str = "Partial"
    message: ProjectDirectorMessageResponse | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class FileOperationPlanRequest(BaseModel):
    path: str
    operation: Literal["create", "update"]
    reason: str
    expected_current_hash: str | None = None
    content_preview_hash: str | None = None
    linked_evidence_refs: list[str] = Field(default_factory=list)
    patch_preview: list[str] = Field(default_factory=list)


class ConfirmSandboxWritePreflightRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    preflight_mode: Literal[
        "dry_run", "fake_preflight", "controlled_sandbox_write"
    ] = "dry_run"
    allowed_path_prefixes: list[str] = Field(default_factory=list)
    allow_frontend: bool = False
    allow_lockfile: bool = False
    allow_binary: bool = False
    file_operations: list[FileOperationPlanRequest] = Field(default_factory=list)


class SandboxPathPolicyFindingResponse(BaseModel):
    path: str
    reason: str
    rule: str


class SandboxPathPolicyResultResponse(BaseModel):
    allowed: bool
    path: str
    normalized_path: str | None = None
    findings: list[SandboxPathPolicyFindingResponse] = Field(default_factory=list)
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    git_write_performed: bool = False
    ai_project_director_total_loop: str = "Partial"


class AcceptedSandboxWriteOperationResponse(BaseModel):
    path: str
    operation: Literal["create", "update"]


class ConfirmSandboxWritePreflightResponse(BaseModel):
    preflight_status: Literal["passed", "blocked"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    preflight_mode: Literal[
        "dry_run", "fake_preflight", "controlled_sandbox_write"
    ] = "dry_run"
    policy_only_preflight: bool = True
    sandbox_write_allowed: bool = False
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    preflight_message_bound: bool = False
    checked_operations_count: int = 0
    allowed_operations_count: int = 0
    blocked_operations_count: int = 0
    accepted_operations: list[AcceptedSandboxWriteOperationResponse] = Field(
        default_factory=list
    )
    accepted_operation_paths: list[str] = Field(default_factory=list)
    blocked_operation_paths: list[str] = Field(default_factory=list)
    path_policy_results: list[SandboxPathPolicyResultResponse] = Field(
        default_factory=list
    )
    recommended_next_step: str = ""
    ai_project_director_total_loop: str = "Partial"
    message: ProjectDirectorMessageResponse | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ConfirmSandboxWriteExecutionRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    execution_mode: Literal[
        "dry_run", "fake_write", "controlled_sandbox_write"
    ] = "dry_run"


class SandboxWriteOperationResultResponse(BaseModel):
    operation_id: str
    path: str
    operation: str
    source_preflight_operation_type: str = "p20_preflight_accepted_path"
    execution_status: Literal["planned", "simulated", "blocked"]
    source_preflight_path_policy_allowed: bool = False
    before_hash: str | None = None
    after_hash: str | None = None
    content_preview_hash: str | None = None
    rollback_snapshot_available: bool = False
    cleanup_required: bool = False
    file_written: bool = False
    patch_applied: bool = False
    worktree_written: bool = False
    git_write_performed: bool = False
    notes: list[str] = Field(default_factory=list)


class ConfirmSandboxWriteExecutionResponse(BaseModel):
    execution_status: Literal["planned", "simulated", "blocked"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    execution_mode: Literal[
        "dry_run", "fake_write", "controlled_sandbox_write"
    ] = "dry_run"
    source_preflight_status: str | None = None
    source_preflight_message_bound: bool = False
    policy_only_source_verified: bool = False
    sandbox_write_execution: bool = True
    no_write_execution: bool = True
    dry_run_only: bool = True
    fake_write_only: bool = False
    controlled_sandbox_write_enabled: bool = False
    sandbox_write_allowed: bool = False
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    worktree_created: bool = False
    worktree_cleaned_up: bool = False
    rollback_snapshot_created: bool = False
    cleanup_required: bool = False
    execution_message_bound: bool = False
    checked_operations_count: int = 0
    simulated_operations_count: int = 0
    blocked_operations_count: int = 0
    operation_results: list[SandboxWriteOperationResultResponse] = Field(
        default_factory=list
    )
    accepted_operation_paths: list[str] = Field(default_factory=list)
    blocked_operation_paths: list[str] = Field(default_factory=list)
    execution_summary: str = ""
    recommended_next_step: str = ""
    ai_project_director_total_loop: str = "Partial"
    message: ProjectDirectorMessageResponse | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ConfirmSandboxWriteDesignLockRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    design_lock_mode: Literal["dry_run", "fake_lock"] = "dry_run"


class ConfirmSandboxWriteDesignLockResponse(BaseModel):
    design_lock_status: Literal["locked", "blocked"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    design_lock_mode: Literal["dry_run", "fake_lock"] = "dry_run"
    source_execution_status: str | None = None
    source_execution_mode: str | None = None
    source_execution_message_bound: bool = False
    source_operation_intent_preserved: bool = False
    controlled_sandbox_write_design_locked: bool = False
    controlled_sandbox_write_enabled: bool = False
    sandbox_write_allowed: bool = False
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    worktree_created: bool = False
    worktree_cleaned_up: bool = False
    rollback_snapshot_created: bool = False
    cleanup_required: bool = False
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_write_scope: list[str] = Field(default_factory=list)
    forbidden_runtime_actions: list[str] = Field(default_factory=list)
    failure_states: list[str] = Field(default_factory=list)
    design_lock_summary: str = ""
    recommended_next_step: str = ""
    ai_project_director_total_loop: str = "Partial"
    message: ProjectDirectorMessageResponse | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ConfirmSandboxWorkspaceGuardRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    guard_mode: Literal["dry_run", "fake_guard"] = "dry_run"
    requested_workspace_name: str | None = Field(default=None, max_length=200)


class ConfirmSandboxWorkspaceGuardResponse(BaseModel):
    guard_status: Literal["guarded", "blocked"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    guard_mode: Literal["dry_run", "fake_guard"] = "dry_run"
    source_design_lock_status: str | None = None
    source_design_lock_message_bound: bool = False
    source_design_lock_verified: bool = False
    sandbox_workspace_guarded: bool = False
    sandbox_workspace_root: str | None = None
    sandbox_workspace_root_policy: str = ""
    requested_workspace_name: str | None = None
    normalized_workspace_name: str | None = None
    workspace_path_preview: str | None = None
    workspace_path_within_root: bool = False
    workspace_created: bool = False
    workspace_written: bool = False
    controlled_sandbox_write_enabled: bool = False
    sandbox_write_allowed: bool = False
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    worktree_created: bool = False
    worktree_cleaned_up: bool = False
    rollback_snapshot_created: bool = False
    cleanup_required: bool = False
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_workspace_scope: list[str] = Field(default_factory=list)
    forbidden_workspace_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    guard_summary: str = ""
    recommended_next_step: str = ""
    ai_project_director_total_loop: str = "Partial"
    message: ProjectDirectorMessageResponse | None = None


class SandboxOperationManifestEntryResponse(BaseModel):
    operation_id: str
    path: str = ""
    operation: str = ""
    workspace_target_path_preview: str = ""
    source_execution_status: str | None = None
    source_preflight_path_policy_allowed: bool | None = None
    path_within_workspace: bool = False
    operation_manifest_allowed: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)


class ConfirmSandboxOperationManifestGuardRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    manifest_mode: Literal["dry_run", "fake_manifest"] = "dry_run"


class ConfirmSandboxOperationManifestGuardResponse(BaseModel):
    manifest_status: Literal["manifested", "blocked"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    manifest_mode: Literal["dry_run", "fake_manifest"] = "dry_run"
    source_workspace_guard_status: str | None = None
    source_workspace_guard_message_bound: bool = False
    source_workspace_guard_verified: bool = False
    source_design_lock_message_id: UUID | None = None
    source_execution_message_id: UUID | None = None
    workspace_path_preview: str | None = None
    workspace_path_within_root: bool = False
    operation_manifest_created: bool = False
    manifest_operations_count: int = 0
    manifest_allowed_operations_count: int = 0
    manifest_blocked_operations_count: int = 0
    manifest_operations: list[SandboxOperationManifestEntryResponse] = Field(
        default_factory=list
    )
    allowed_operation_paths: list[str] = Field(default_factory=list)
    blocked_operation_paths: list[str] = Field(default_factory=list)
    workspace_created: bool = False
    workspace_written: bool = False
    file_written: bool = False
    controlled_sandbox_write_enabled: bool = False
    sandbox_write_allowed: bool = False
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    real_code_modified: bool = False
    real_diff_generated: bool = False
    patch_applied: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    worktree_created: bool = False
    worktree_cleaned_up: bool = False
    rollback_snapshot_created: bool = False
    cleanup_required: bool = False
    target_file_content_read: bool = False
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_manifest_scope: list[str] = Field(default_factory=list)
    forbidden_manifest_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    manifest_summary: str = ""
    recommended_next_step: str = ""
    ai_project_director_total_loop: str = "Partial"
    message: ProjectDirectorMessageResponse | None = None


class ConfirmSandboxWorkspaceCreateRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    create_mode: Literal["mkdir_only"] = "mkdir_only"


class ConfirmSandboxWorkspaceCreateResponse(BaseModel):
    creation_status: Literal["created", "already_exists", "blocked"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    create_mode: Literal["mkdir_only"] = "mkdir_only"
    source_manifest_status: str | None = None
    source_manifest_message_bound: bool = False
    source_manifest_verified: bool = False
    workspace_path: str | None = None
    workspace_path_within_root: bool = False
    workspace_root: str | None = None
    workspace_created: bool = False
    workspace_already_existed: bool = False
    workspace_written: bool = False
    file_written: bool = False
    manifest_file_written: bool = False
    target_file_content_read: bool = False
    real_diff_generated: bool = False
    patch_applied: bool = False
    controlled_sandbox_write_enabled: bool = False
    sandbox_write_allowed: bool = False
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    worktree_created: bool = False
    worktree_cleaned_up: bool = False
    rollback_snapshot_created: bool = False
    cleanup_required: bool = False
    cleanup_hint: str = ""
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_creation_scope: list[str] = Field(default_factory=list)
    forbidden_creation_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    creation_summary: str = ""
    recommended_next_step: str = ""
    ai_project_director_total_loop: str = "Partial"
    message: ProjectDirectorMessageResponse | None = None


class ConfirmSandboxWorkspaceManifestWriteRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    write_mode: Literal["internal_manifest_only"] = "internal_manifest_only"


class ConfirmSandboxWorkspaceManifestWriteResponse(BaseModel):
    manifest_write_status: Literal["written", "overwritten", "blocked"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    write_mode: Literal["internal_manifest_only"] = "internal_manifest_only"
    source_workspace_creation_status: str | None = None
    source_workspace_creation_message_bound: bool = False
    source_workspace_creation_verified: bool = False
    workspace_path: str | None = None
    workspace_path_within_root: bool = False
    workspace_root: str | None = None
    manifest_dir_path: str | None = None
    manifest_file_path: str | None = None
    manifest_dir_created: bool = False
    manifest_file_written: bool = False
    manifest_file_overwritten: bool = False
    business_file_written: bool = False
    target_file_content_read: bool = False
    real_diff_generated: bool = False
    patch_applied: bool = False
    controlled_sandbox_write_enabled: bool = False
    sandbox_write_allowed: bool = False
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    worktree_created: bool = False
    worktree_cleaned_up: bool = False
    rollback_snapshot_created: bool = False
    cleanup_required: bool = False
    cleanup_hint: str = ""
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_manifest_write_scope: list[str] = Field(default_factory=list)
    forbidden_manifest_write_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    manifest_write_summary: str = ""
    recommended_next_step: str = ""
    ai_project_director_total_loop: str = "Partial"
    message: ProjectDirectorMessageResponse | None = None


class CandidateSandboxFileWriteRequest(BaseModel):
    relative_path: str
    content: str
    operation: Literal["create", "update"]
    content_encoding: Literal["utf-8"] = "utf-8"


class CandidateSandboxWrittenFileResponse(BaseModel):
    relative_path: str
    workspace_file_path: str
    operation: Literal["create", "update"]
    content_encoding: Literal["utf-8"] = "utf-8"
    content_size_bytes: int = 0


class CandidateSandboxBlockedFileResponse(BaseModel):
    relative_path: str = ""
    operation: str = ""
    blocked_reasons: list[str] = Field(default_factory=list)


class ConfirmSandboxCandidateFilesWriteRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    write_mode: Literal["candidate_files_only"] = "candidate_files_only"
    candidate_files: list[CandidateSandboxFileWriteRequest] = Field(default_factory=list)


class ConfirmSandboxCandidateFilesWriteResponse(BaseModel):
    candidate_write_status: Literal["written", "blocked"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    write_mode: Literal["candidate_files_only"] = "candidate_files_only"
    source_manifest_write_status: str | None = None
    source_manifest_write_message_bound: bool = False
    source_manifest_write_verified: bool = False
    source_workspace_creation_message_id: UUID | None = None
    source_operation_manifest_message_id: UUID | None = None
    workspace_path: str | None = None
    workspace_path_within_root: bool = False
    workspace_root: str | None = None
    internal_manifest_file_path: str | None = None
    internal_manifest_verified: bool = False
    candidate_files_requested_count: int = 0
    candidate_files_written_count: int = 0
    candidate_files_blocked_count: int = 0
    candidate_written_files: list[CandidateSandboxWrittenFileResponse] = Field(
        default_factory=list
    )
    candidate_blocked_files: list[CandidateSandboxBlockedFileResponse] = Field(
        default_factory=list
    )
    candidate_business_files_written: bool = False
    business_file_written: bool = False
    manifest_file_written: bool = False
    target_file_content_read: bool = False
    real_diff_generated: bool = False
    patch_applied: bool = False
    controlled_sandbox_write_enabled: bool = False
    sandbox_write_allowed: bool = False
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    worktree_created: bool = False
    worktree_cleaned_up: bool = False
    rollback_snapshot_created: bool = False
    cleanup_required: bool = False
    cleanup_hint: str = ""
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_candidate_write_scope: list[str] = Field(default_factory=list)
    forbidden_candidate_write_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    candidate_write_summary: str = ""
    recommended_next_step: str = ""
    ai_project_director_total_loop: str = "Partial"
    message: ProjectDirectorMessageResponse | None = None


class ConfirmSandboxCandidateDiffGenerateRequest(BaseModel):
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    diff_mode: Literal["readonly_unified_diff"] = "readonly_unified_diff"
    max_diff_bytes: int = Field(default=200_000, gt=0)


class CandidateSandboxDiffEntryResponse(BaseModel):
    relative_path: str
    operation: str
    target_file_path: str
    candidate_file_path: str
    target_file_existed: bool
    candidate_file_existed: bool
    target_file_content_read: bool
    candidate_file_content_read: bool
    unified_diff: str
    diff_bytes: int = 0


class CandidateSandboxDiffBlockedFileResponse(BaseModel):
    relative_path: str = ""
    operation: str = ""
    blocked_reasons: list[str] = Field(default_factory=list)


class ConfirmSandboxCandidateDiffGenerateResponse(BaseModel):
    diff_generation_status: Literal["generated", "blocked"]
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    diff_mode: Literal["readonly_unified_diff"] = "readonly_unified_diff"
    source_candidate_write_status: str | None = None
    source_candidate_write_message_bound: bool = False
    source_candidate_write_verified: bool = False
    source_workspace_manifest_write_message_id: UUID | None = None
    source_workspace_creation_message_id: UUID | None = None
    source_operation_manifest_message_id: UUID | None = None
    workspace_path: str | None = None
    workspace_path_within_root: bool = False
    workspace_root: str | None = None
    internal_manifest_file_path: str | None = None
    internal_manifest_verified: bool = False
    repo_root: str | None = None
    target_file_content_read: bool = False
    candidate_file_content_read: bool = False
    readonly_real_diff_generated: bool = False
    real_diff_generated: bool = False
    diff_bytes: int = 0
    diff_file_count: int = 0
    diff_entries: list[CandidateSandboxDiffEntryResponse] = Field(default_factory=list)
    unified_diff_text: str = ""
    candidate_files_considered_count: int = 0
    candidate_files_diffed_count: int = 0
    candidate_files_blocked_count: int = 0
    candidate_diff_blocked_files: list[
        CandidateSandboxDiffBlockedFileResponse
    ] = Field(default_factory=list)
    main_project_file_written: bool = False
    sandbox_file_written: bool = False
    manifest_file_written: bool = False
    patch_applied: bool = False
    controlled_sandbox_write_enabled: bool = False
    sandbox_write_allowed: bool = False
    product_runtime_git_write_allowed: bool = False
    main_worktree_write_allowed: bool = False
    worktree_write_allowed: bool = False
    file_write_allowed: bool = False
    actual_patch_applied: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    worktree_created: bool = False
    worktree_cleaned_up: bool = False
    rollback_snapshot_created: bool = False
    cleanup_required: bool = False
    cleanup_hint: str = ""
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_diff_scope: list[str] = Field(default_factory=list)
    forbidden_diff_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    diff_generation_summary: str = ""
    recommended_next_step: str = ""
    ai_project_director_total_loop: str = "Partial"
    message: ProjectDirectorMessageResponse | None = None


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


def _get_dry_run_task_dispatch_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorDryRunTaskDispatchService:
    return ProjectDirectorDryRunTaskDispatchService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_controlled_executor_dispatch_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorControlledExecutorDispatchService:
    return ProjectDirectorControlledExecutorDispatchService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_readonly_review_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorReadonlyReviewService:
    return ProjectDirectorReadonlyReviewService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_programmer_no_write_plan_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorProgrammerNoWritePlanService:
    return ProjectDirectorProgrammerNoWritePlanService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_programmer_no_write_execution_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorProgrammerNoWriteExecutionService:
    return ProjectDirectorProgrammerNoWriteExecutionService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_sandbox_write_preflight_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorSandboxWritePreflightService:
    return ProjectDirectorSandboxWritePreflightService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_sandbox_write_execution_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorSandboxWriteExecutionService:
    return ProjectDirectorSandboxWriteExecutionService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_sandbox_write_design_lock_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorSandboxWriteDesignLockService:
    return ProjectDirectorSandboxWriteDesignLockService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_sandbox_workspace_guard_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorSandboxWorkspaceGuardService:
    return ProjectDirectorSandboxWorkspaceGuardService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_sandbox_operation_manifest_guard_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorSandboxOperationManifestGuardService:
    return ProjectDirectorSandboxOperationManifestGuardService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_sandbox_workspace_creation_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorSandboxWorkspaceCreationService:
    return ProjectDirectorSandboxWorkspaceCreationService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_sandbox_workspace_manifest_write_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorSandboxWorkspaceManifestWriteService:
    return ProjectDirectorSandboxWorkspaceManifestWriteService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_sandbox_candidate_file_write_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorSandboxCandidateFileWriteService:
    return ProjectDirectorSandboxCandidateFileWriteService(
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
    )


def _get_sandbox_candidate_diff_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ProjectDirectorSandboxCandidateDiffService:
    return ProjectDirectorSandboxCandidateDiffService(
        repo_root=REPO_ROOT,
        session_repository=ProjectDirectorSessionRepository(session),
        message_repository=ProjectDirectorMessageRepository(session),
        task_repository=TaskRepository(session),
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


# ── Router ──────────────────────────────────────────────────────────


router = APIRouter(
    prefix="/project-director",
    tags=["project-director"],
)


@router.post(
    "/evidence-to-agent/dry-run",
    summary="Run a Project Director evidence-to-agent dry-run without execution",
)
def run_evidence_to_agent_dry_run(
    request: EvidenceToAgentDryRunRequest,
) -> dict:
    """Return a safe evidence-to-agent dry-run summary without task creation."""

    if not request.user_goal.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_goal must not be empty or whitespace-only",
        )

    try:
        return ProjectDirectorEvidenceToAgentDryRunService(repo_root=REPO_ROOT).run(
            user_goal=request.user_goal
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/sessions/{session_id}/evidence-to-agent/dry-run",
    response_model=EvidenceToAgentDryRunSessionResponse,
    summary="Run evidence-to-agent dry-run and bind the result to a session message",
)
def run_session_evidence_to_agent_dry_run(
    session_id: UUID,
    request: EvidenceToAgentDryRunRequest,
    message_service: Annotated[
        ProjectDirectorMessageService, Depends(_get_message_service)
    ],
) -> EvidenceToAgentDryRunSessionResponse:
    """Persist a safe dry-run trace message for one Project Director session."""

    if not request.user_goal.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_goal must not be empty or whitespace-only",
        )

    try:
        summary = ProjectDirectorEvidenceToAgentDryRunService(repo_root=REPO_ROOT).run(
            user_goal=request.user_goal
        )
        message = message_service.record_evidence_to_agent_dry_run(
            session_id=session_id,
            summary=summary,
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

    return EvidenceToAgentDryRunSessionResponse(
        dry_run_summary=summary,
        message=ProjectDirectorMessageResponse.from_domain(message),
    )


@router.post(
    "/sessions/{session_id}/dry-run-task-dispatch",
    response_model=ConfirmDryRunTaskDispatchResponse,
    summary="Confirm a P11 dry-run message and create one safe dry-run task",
)
def confirm_session_dry_run_task_dispatch(
    session_id: UUID,
    request: ConfirmDryRunTaskDispatchRequest,
    dispatch_service: Annotated[
        ProjectDirectorDryRunTaskDispatchService,
        Depends(_get_dry_run_task_dispatch_service),
    ],
) -> ConfirmDryRunTaskDispatchResponse:
    """Create a safe simulate-only Task from one confirmed P11 dry-run message."""

    try:
        dispatch = dispatch_service.confirm_dispatch(
            session_id=session_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "user_confirmation_required" in lowered:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if "source_message_not_in_session" in lowered:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = dispatch.result
    return ConfirmDryRunTaskDispatchResponse(
        dispatch_status="dispatched",
        session_id=result.session_id,
        source_message_id=result.source_message_id,
        created_task_id=result.created_task_id,
        evidence_pack_id=result.evidence_pack_id,
        safe_dry_run_task=result.safe_dry_run_task,
        worker_simulate_required=result.worker_simulate_required,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        frontend_required=result.frontend_required,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        worker_started=result.worker_started,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message_bound=result.message_bound,
        message=(
            ProjectDirectorMessageResponse.from_domain(dispatch.message)
            if dispatch.message is not None
            else None
        ),
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
    )


@router.post(
    "/sessions/{session_id}/dry-run-task-dispatch/worker-result",
    response_model=RecordDryRunTaskWorkerResultResponse,
    summary="Bind one safe dry-run task Worker simulate result to the session",
)
def record_session_dry_run_task_worker_result(
    session_id: UUID,
    request: RecordDryRunTaskWorkerResultRequest,
    message_service: Annotated[
        ProjectDirectorMessageService, Depends(_get_message_service)
    ],
) -> RecordDryRunTaskWorkerResultResponse:
    """Record a Worker simulate readback summary without starting execution."""

    result = ProjectDirectorDryRunTaskWorkerResult(
        session_id=session_id,
        task_id=request.task_id,
        run_id=request.run_id,
        worker_run_once_ok=request.worker_run_once_ok,
        worker_simulate_mode=request.worker_simulate_mode,
        run_created=request.run_created,
        run_readback_ok=request.run_readback_ok,
        blocked_reasons=request.blocked_reasons,
    )
    try:
        message = message_service.record_dry_run_task_worker_result(result=result)
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

    return RecordDryRunTaskWorkerResultResponse(
        session_id=session_id,
        task_id=request.task_id,
        run_id=request.run_id,
        worker_run_once_ok=request.worker_run_once_ok,
        worker_simulate_mode=request.worker_simulate_mode,
        run_created=request.run_created,
        run_readback_ok=request.run_readback_ok,
        message_bound=True,
        message=ProjectDirectorMessageResponse.from_domain(message),
        blocked_reasons=request.blocked_reasons,
    )


@router.post(
    "/sessions/{session_id}/controlled-executor-dispatch",
    response_model=ConfirmControlledExecutorDispatchResponse,
    summary="Confirm a P12 safe dry-run task for controlled executor dispatch",
)
def confirm_session_controlled_executor_dispatch(
    session_id: UUID,
    request: ConfirmControlledExecutorDispatchRequest,
    dispatch_service: Annotated[
        ProjectDirectorControlledExecutorDispatchService,
        Depends(_get_controlled_executor_dispatch_service),
    ],
) -> ConfirmControlledExecutorDispatchResponse:
    """Record a controlled executor pilot intent without starting execution."""

    try:
        dispatch = dispatch_service.confirm_dispatch(
            session_id=session_id,
            source_task_id=request.source_task_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
            requested_agent_role=request.requested_agent_role,
            requested_executor=request.requested_executor,
            launch_mode=request.launch_mode,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "user_confirmation_required" in lowered:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if (
            "source_message_not_in_session" in lowered
            or "source_task_not_bound_to_source_message" in lowered
            or "source_task_is_not_safe_dry_run" in lowered
            or "source_message_is_not_p12_dispatch" in lowered
            or "controlled_smoke_not_enabled_in_api" in lowered
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = dispatch.result
    return ConfirmControlledExecutorDispatchResponse(
        dispatch_status=result.dispatch_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        requested_agent_role=result.requested_agent_role,
        requested_executor=result.requested_executor,
        launch_mode=result.launch_mode,
        controlled_executor_pilot=result.controlled_executor_pilot,
        executor_backed_agent=result.executor_backed_agent,
        programmer_agent_allowed=result.programmer_agent_allowed,
        reviewer_agent_allowed=result.reviewer_agent_allowed,
        supervisor_required=result.supervisor_required,
        auto_terminate_required=result.auto_terminate_required,
        cleanup_required=result.cleanup_required,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        frontend_required=result.frontend_required,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        agent_session_bound=result.agent_session_bound,
        process_handle_id_present=result.process_handle_id_present,
        supervisor_registered=result.supervisor_registered,
        supervisor_cleanup_done=result.supervisor_cleanup_done,
        run_created=result.run_created,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        p9_production_safe_long_running_executor_lifecycle=(
            result.p9_production_safe_long_running_executor_lifecycle
        ),
        message_bound=result.message_bound,
        message=(
            ProjectDirectorMessageResponse.from_domain(dispatch.message)
            if dispatch.message is not None
            else None
        ),
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
    )


@router.post(
    "/sessions/{session_id}/readonly-review",
    response_model=ConfirmReadonlyReviewResponse,
    summary="Create a readonly reviewer review from one P14 lifecycle message",
)
def confirm_session_readonly_review(
    session_id: UUID,
    request: ConfirmReadonlyReviewRequest,
    review_service: Annotated[
        ProjectDirectorReadonlyReviewService,
        Depends(_get_readonly_review_service),
    ],
) -> ConfirmReadonlyReviewResponse:
    """Record a readonly reviewer result without starting an executor."""

    try:
        review = review_service.confirm_review(
            session_id=session_id,
            source_task_id=request.source_task_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
            requested_reviewer_executor=request.requested_reviewer_executor,
            review_mode=request.review_mode,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "user_confirmation_required" in lowered:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if (
            "source_message_not_in_session" in lowered
            or "source_message_is_not_p14_lifecycle_result" in lowered
            or "source_task_not_bound_to_p14_lifecycle" in lowered
            or "source_task_is_not_safe_dry_run" in lowered
            or "controlled_review_not_enabled_in_api" in lowered
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = review.result
    return ConfirmReadonlyReviewResponse(
        review_status=result.review_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        p14_lifecycle_message_id=result.p14_lifecycle_message_id,
        requested_reviewer_executor=result.requested_reviewer_executor,
        review_mode=result.review_mode,
        readonly_review=result.readonly_review,
        reviewer_agent=result.reviewer_agent,
        executor_backed_review_allowed=result.executor_backed_review_allowed,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        file_write_allowed=result.file_write_allowed,
        real_code_modified=result.real_code_modified,
        git_write_performed=result.git_write_performed,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        review_result_message_bound=result.review_result_message_bound,
        review_summary=result.review_summary,
        review_findings=[
            ReadonlyReviewFindingResponse(**finding.model_dump())
            for finding in result.review_findings
        ],
        risk_level=result.risk_level,
        recommended_next_step=result.recommended_next_step,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message=None,
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
    )


@router.post(
    "/sessions/{session_id}/programmer-no-write-plan",
    response_model=ConfirmProgrammerNoWritePlanResponse,
    summary="Create a programmer no-write implementation plan from P15 review",
)
def confirm_session_programmer_no_write_plan(
    session_id: UUID,
    request: ConfirmProgrammerNoWritePlanRequest,
    plan_service: Annotated[
        ProjectDirectorProgrammerNoWritePlanService,
        Depends(_get_programmer_no_write_plan_service),
    ],
) -> ConfirmProgrammerNoWritePlanResponse:
    """Record a structured programmer plan without execution or writes."""

    try:
        plan = plan_service.confirm_plan(
            session_id=session_id,
            source_task_id=request.source_task_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
            requested_programmer_executor=request.requested_programmer_executor,
            planning_mode=request.planning_mode,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "user_confirmation_required" in lowered:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if (
            "source_message_not_in_session" in lowered
            or "source_message_is_not_p15_readonly_review" in lowered
            or "source_task_not_bound_to_p15_review" in lowered
            or "source_task_is_not_p12_safe_dry_run" in lowered
            or "controlled_no_write_not_enabled_in_api" in lowered
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = plan.result
    return ConfirmProgrammerNoWritePlanResponse(
        plan_status=result.plan_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        requested_programmer_executor=result.requested_programmer_executor,
        planning_mode=result.planning_mode,
        programmer_agent=result.programmer_agent,
        controlled_programmer_planning=result.controlled_programmer_planning,
        no_write_plan=result.no_write_plan,
        executor_backed_programmer_allowed=result.executor_backed_programmer_allowed,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        file_write_allowed=result.file_write_allowed,
        real_code_modified=result.real_code_modified,
        git_write_performed=result.git_write_performed,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        worker_started=result.worker_started,
        task_created=result.task_created,
        run_created=result.run_created,
        plan_message_bound=result.plan_message_bound,
        implementation_summary=result.implementation_summary,
        planned_steps=[
            ProgrammerNoWritePlannedStepResponse(**step.model_dump())
            for step in result.planned_steps
        ],
        affected_files_preview=result.affected_files_preview,
        required_evidence_refs=result.required_evidence_refs,
        required_targeted_tests=result.required_targeted_tests,
        reviewer_feedback_refs=result.reviewer_feedback_refs,
        risk_level=result.risk_level,
        recommended_next_step=result.recommended_next_step,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message=(
            ProjectDirectorMessageResponse.from_domain(plan.message)
            if plan.message is not None
            else None
        ),
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
    )


@router.post(
    "/sessions/{session_id}/programmer-no-write-execution",
    response_model=ConfirmProgrammerNoWriteExecutionResponse,
    summary="Create a programmer no-write execution result from one P16 plan",
)
def confirm_session_programmer_no_write_execution(
    session_id: UUID,
    request: ConfirmProgrammerNoWriteExecutionRequest,
    execution_service: Annotated[
        ProjectDirectorProgrammerNoWriteExecutionService,
        Depends(_get_programmer_no_write_execution_service),
    ],
) -> ConfirmProgrammerNoWriteExecutionResponse:
    """Record a structured programmer execution result without writes."""

    try:
        execution = execution_service.confirm_execution(
            session_id=session_id,
            source_task_id=request.source_task_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
            requested_programmer_executor=request.requested_programmer_executor,
            execution_mode=request.execution_mode,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if "user_confirmation_required" in lowered:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        if (
            "source_message_not_in_session" in lowered
            or "source_message_is_not_p16_programmer_no_write_plan" in lowered
            or "source_task_not_bound_to_p16_plan" in lowered
            or "source_task_is_not_p12_safe_dry_run" in lowered
            or "controlled_no_write_not_enabled_in_api" in lowered
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = execution.result
    return ConfirmProgrammerNoWriteExecutionResponse(
        execution_status=result.execution_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        requested_programmer_executor=result.requested_programmer_executor,
        execution_mode=result.execution_mode,
        programmer_agent=result.programmer_agent,
        controlled_programmer_execution=result.controlled_programmer_execution,
        no_write_execution=result.no_write_execution,
        executor_backed_programmer_allowed=result.executor_backed_programmer_allowed,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        file_write_allowed=result.file_write_allowed,
        actual_patch_applied=result.actual_patch_applied,
        real_code_modified=result.real_code_modified,
        git_write_performed=result.git_write_performed,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        worker_started=result.worker_started,
        task_created=result.task_created,
        run_created=result.run_created,
        execution_message_bound=result.execution_message_bound,
        execution_summary=result.execution_summary,
        execution_steps=[
            ProgrammerNoWriteExecutionStepResponse(**step.model_dump())
            for step in result.execution_steps
        ],
        patch_preview=result.patch_preview,
        files_considered=result.files_considered,
        tests_to_run=result.tests_to_run,
        implementation_notes=result.implementation_notes,
        handoff_notes=result.handoff_notes,
        risk_notes=result.risk_notes,
        risk_level=result.risk_level,
        recommended_next_step=result.recommended_next_step,
        source_plan_refs=result.source_plan_refs,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message=(
            ProjectDirectorMessageResponse.from_domain(execution.message)
            if execution.message is not None
            else None
        ),
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
    )


@router.post(
    "/sessions/{session_id}/sandbox-write-preflight",
    response_model=ConfirmSandboxWritePreflightResponse,
    summary="Create a policy-only sandbox write preflight from one P17 result",
)
def confirm_session_sandbox_write_preflight(
    session_id: UUID,
    request: ConfirmSandboxWritePreflightRequest,
    preflight_service: Annotated[
        ProjectDirectorSandboxWritePreflightService,
        Depends(_get_sandbox_write_preflight_service),
    ],
) -> ConfirmSandboxWritePreflightResponse:
    """Record a no-write preflight result without files, worktrees, or Git writes."""

    try:
        file_operations = [
            ProjectDirectorFileOperationPlan(**operation.model_dump())
            for operation in request.file_operations
        ]
        preflight = preflight_service.confirm_preflight(
            session_id=session_id,
            source_task_id=request.source_task_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
            preflight_mode=request.preflight_mode,
            allowed_path_prefixes=request.allowed_path_prefixes,
            allow_frontend=request.allow_frontend,
            allow_lockfile=request.allow_lockfile,
            allow_binary=request.allow_binary,
            file_operations=file_operations,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if (
            "user_confirmation_required" in lowered
            or "source_message_not_in_session" in lowered
            or "source_message_is_not_p17_programmer_no_write_execution" in lowered
            or "source_task_not_bound_to_p17_execution" in lowered
            or "source_task_is_not_p12_safe_dry_run" in lowered
            or "file_operations_required" in lowered
            or "controlled_sandbox_write_not_enabled_in_api" in lowered
            or "path_policy_failed" in lowered
            or "patch_preview_contains_applyable_diff_marker" in lowered
            or "unsupported_operation" in lowered
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = preflight.result
    return ConfirmSandboxWritePreflightResponse(
        preflight_status=result.preflight_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        preflight_mode=result.preflight_mode,
        policy_only_preflight=result.policy_only_preflight,
        sandbox_write_allowed=result.sandbox_write_allowed,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        main_worktree_write_allowed=result.main_worktree_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        file_write_allowed=result.file_write_allowed,
        actual_patch_applied=result.actual_patch_applied,
        real_code_modified=result.real_code_modified,
        git_write_performed=result.git_write_performed,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        worker_started=result.worker_started,
        task_created=result.task_created,
        run_created=result.run_created,
        preflight_message_bound=result.preflight_message_bound,
        checked_operations_count=result.checked_operations_count,
        allowed_operations_count=result.allowed_operations_count,
        blocked_operations_count=result.blocked_operations_count,
        accepted_operations=[
            AcceptedSandboxWriteOperationResponse(**operation.model_dump())
            for operation in result.accepted_operations
        ],
        accepted_operation_paths=result.accepted_operation_paths,
        blocked_operation_paths=result.blocked_operation_paths,
        path_policy_results=[
            SandboxPathPolicyResultResponse(**policy.model_dump())
            for policy in result.path_policy_results
        ],
        recommended_next_step=result.recommended_next_step,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message=(
            ProjectDirectorMessageResponse.from_domain(preflight.message)
            if preflight.message is not None
            else None
        ),
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
    )


@router.post(
    "/sessions/{session_id}/sandbox-write-execution",
    response_model=ConfirmSandboxWriteExecutionResponse,
    summary="Create a P21-A dry-run/fake-write sandbox write execution result",
)
def confirm_session_sandbox_write_execution(
    session_id: UUID,
    request: ConfirmSandboxWriteExecutionRequest,
    execution_service: Annotated[
        ProjectDirectorSandboxWriteExecutionService,
        Depends(_get_sandbox_write_execution_service),
    ],
) -> ConfirmSandboxWriteExecutionResponse:
    """Record a no-write P21-A execution result from one P20 preflight message."""

    try:
        execution = execution_service.confirm_execution(
            session_id=session_id,
            source_task_id=request.source_task_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
            execution_mode=request.execution_mode,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        if (
            "user_confirmation_required" in lowered
            or "source_message_not_in_session" in lowered
            or "source_message_is_not_p20_sandbox_write_preflight" in lowered
            or "source_task_not_bound_to_p20_preflight" in lowered
            or "source_task_is_not_p12_safe_dry_run" in lowered
            or "controlled_sandbox_write_not_enabled_in_api" in lowered
            or "p20_preflight_record_missing" in lowered
            or "source_preflight_not_passed" in lowered
            or "source_preflight_not_policy_only" in lowered
            or "source_preflight_has_blocked_reasons" in lowered
            or "source_preflight_has_no_checked_operations" in lowered
            or "source_preflight_has_blocked_operations" in lowered
            or "accepted_operation_paths_required" in lowered
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = execution.result
    return ConfirmSandboxWriteExecutionResponse(
        execution_status=result.execution_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        execution_mode=result.execution_mode,
        source_preflight_status=result.source_preflight_status,
        source_preflight_message_bound=result.source_preflight_message_bound,
        policy_only_source_verified=result.policy_only_source_verified,
        sandbox_write_execution=result.sandbox_write_execution,
        no_write_execution=result.no_write_execution,
        dry_run_only=result.dry_run_only,
        fake_write_only=result.fake_write_only,
        controlled_sandbox_write_enabled=result.controlled_sandbox_write_enabled,
        sandbox_write_allowed=result.sandbox_write_allowed,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        main_worktree_write_allowed=result.main_worktree_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        file_write_allowed=result.file_write_allowed,
        actual_patch_applied=result.actual_patch_applied,
        real_code_modified=result.real_code_modified,
        git_write_performed=result.git_write_performed,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        worker_started=result.worker_started,
        task_created=result.task_created,
        run_created=result.run_created,
        worktree_created=result.worktree_created,
        worktree_cleaned_up=result.worktree_cleaned_up,
        rollback_snapshot_created=result.rollback_snapshot_created,
        cleanup_required=result.cleanup_required,
        execution_message_bound=result.execution_message_bound,
        checked_operations_count=result.checked_operations_count,
        simulated_operations_count=result.simulated_operations_count,
        blocked_operations_count=result.blocked_operations_count,
        operation_results=[
            SandboxWriteOperationResultResponse(**operation.model_dump())
            for operation in result.operation_results
        ],
        accepted_operation_paths=result.accepted_operation_paths,
        blocked_operation_paths=result.blocked_operation_paths,
        execution_summary=result.execution_summary,
        recommended_next_step=result.recommended_next_step,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message=(
            ProjectDirectorMessageResponse.from_domain(execution.message)
            if execution.message is not None
            else None
        ),
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
    )


@router.post(
    "/sessions/{session_id}/sandbox-write-design-lock",
    response_model=ConfirmSandboxWriteDesignLockResponse,
    summary="Create a P21-B controlled sandbox write design lock",
)
def confirm_session_sandbox_write_design_lock(
    session_id: UUID,
    request: ConfirmSandboxWriteDesignLockRequest,
    design_lock_service: Annotated[
        ProjectDirectorSandboxWriteDesignLockService,
        Depends(_get_sandbox_write_design_lock_service),
    ],
) -> ConfirmSandboxWriteDesignLockResponse:
    """Record design constraints before any real sandbox/worktree write exists."""

    try:
        design_lock = design_lock_service.confirm_design_lock(
            session_id=session_id,
            source_task_id=request.source_task_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
            design_lock_mode=request.design_lock_mode,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = design_lock.result
    if result.design_lock_status == "blocked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                ";".join(result.blocked_reasons)
                or "sandbox_write_design_lock_blocked"
            ),
        )

    return ConfirmSandboxWriteDesignLockResponse(
        design_lock_status=result.design_lock_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        design_lock_mode=result.design_lock_mode,
        source_execution_status=result.source_execution_status,
        source_execution_mode=result.source_execution_mode,
        source_execution_message_bound=result.source_execution_message_bound,
        source_operation_intent_preserved=result.source_operation_intent_preserved,
        controlled_sandbox_write_design_locked=(
            result.controlled_sandbox_write_design_locked
        ),
        controlled_sandbox_write_enabled=result.controlled_sandbox_write_enabled,
        sandbox_write_allowed=result.sandbox_write_allowed,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        main_worktree_write_allowed=result.main_worktree_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        file_write_allowed=result.file_write_allowed,
        actual_patch_applied=result.actual_patch_applied,
        real_code_modified=result.real_code_modified,
        git_write_performed=result.git_write_performed,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        worker_started=result.worker_started,
        task_created=result.task_created,
        run_created=result.run_created,
        worktree_created=result.worktree_created,
        worktree_cleaned_up=result.worktree_cleaned_up,
        rollback_snapshot_created=result.rollback_snapshot_created,
        cleanup_required=result.cleanup_required,
        required_preconditions=result.required_preconditions,
        allowed_future_write_scope=result.allowed_future_write_scope,
        forbidden_runtime_actions=result.forbidden_runtime_actions,
        failure_states=result.failure_states,
        design_lock_summary=result.design_lock_summary,
        recommended_next_step=result.recommended_next_step,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message=(
            ProjectDirectorMessageResponse.from_domain(design_lock.message)
            if design_lock.message is not None
            else None
        ),
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
    )


@router.post(
    "/sessions/{session_id}/sandbox-workspace-guard",
    response_model=ConfirmSandboxWorkspaceGuardResponse,
    summary="Create a P21-C sandbox workspace root guard",
)
def confirm_session_sandbox_workspace_guard(
    session_id: UUID,
    request: ConfirmSandboxWorkspaceGuardRequest,
    workspace_guard_service: Annotated[
        ProjectDirectorSandboxWorkspaceGuardService,
        Depends(_get_sandbox_workspace_guard_service),
    ],
) -> ConfirmSandboxWorkspaceGuardResponse:
    """Preview an isolated workspace path before any real write capability."""

    try:
        workspace_guard = workspace_guard_service.confirm_workspace_guard(
            session_id=session_id,
            source_task_id=request.source_task_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
            guard_mode=request.guard_mode,
            requested_workspace_name=request.requested_workspace_name,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = workspace_guard.result
    if result.guard_status == "blocked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                ";".join(result.blocked_reasons)
                or "sandbox_workspace_guard_blocked"
            ),
        )

    return ConfirmSandboxWorkspaceGuardResponse(
        guard_status=result.guard_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        guard_mode=result.guard_mode,
        source_design_lock_status=result.source_design_lock_status,
        source_design_lock_message_bound=result.source_design_lock_message_bound,
        source_design_lock_verified=result.source_design_lock_verified,
        sandbox_workspace_guarded=result.sandbox_workspace_guarded,
        sandbox_workspace_root=result.sandbox_workspace_root,
        sandbox_workspace_root_policy=result.sandbox_workspace_root_policy,
        requested_workspace_name=result.requested_workspace_name,
        normalized_workspace_name=result.normalized_workspace_name,
        workspace_path_preview=result.workspace_path_preview,
        workspace_path_within_root=result.workspace_path_within_root,
        workspace_created=result.workspace_created,
        workspace_written=result.workspace_written,
        controlled_sandbox_write_enabled=result.controlled_sandbox_write_enabled,
        sandbox_write_allowed=result.sandbox_write_allowed,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        main_worktree_write_allowed=result.main_worktree_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        file_write_allowed=result.file_write_allowed,
        actual_patch_applied=result.actual_patch_applied,
        real_code_modified=result.real_code_modified,
        git_write_performed=result.git_write_performed,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        worker_started=result.worker_started,
        task_created=result.task_created,
        run_created=result.run_created,
        worktree_created=result.worktree_created,
        worktree_cleaned_up=result.worktree_cleaned_up,
        rollback_snapshot_created=result.rollback_snapshot_created,
        cleanup_required=result.cleanup_required,
        required_preconditions=result.required_preconditions,
        allowed_future_workspace_scope=result.allowed_future_workspace_scope,
        forbidden_workspace_actions=result.forbidden_workspace_actions,
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
        guard_summary=result.guard_summary,
        recommended_next_step=result.recommended_next_step,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message=(
            ProjectDirectorMessageResponse.from_domain(workspace_guard.message)
            if workspace_guard.message is not None
            else None
        ),
    )


@router.post(
    "/sessions/{session_id}/sandbox-operation-manifest-guard",
    response_model=ConfirmSandboxOperationManifestGuardResponse,
    summary="Create a P21-C sandbox operation manifest guard",
)
def confirm_session_sandbox_operation_manifest_guard(
    session_id: UUID,
    request: ConfirmSandboxOperationManifestGuardRequest,
    manifest_guard_service: Annotated[
        ProjectDirectorSandboxOperationManifestGuardService,
        Depends(_get_sandbox_operation_manifest_guard_service),
    ],
) -> ConfirmSandboxOperationManifestGuardResponse:
    """Build a readonly operation manifest before any workspace/file write."""

    try:
        manifest_guard = manifest_guard_service.confirm_operation_manifest_guard(
            session_id=session_id,
            source_task_id=request.source_task_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
            manifest_mode=request.manifest_mode,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = manifest_guard.result
    if result.manifest_status == "blocked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                ";".join(result.blocked_reasons)
                or "sandbox_operation_manifest_guard_blocked"
            ),
        )

    return ConfirmSandboxOperationManifestGuardResponse(
        manifest_status=result.manifest_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        manifest_mode=result.manifest_mode,
        source_workspace_guard_status=result.source_workspace_guard_status,
        source_workspace_guard_message_bound=(
            result.source_workspace_guard_message_bound
        ),
        source_workspace_guard_verified=result.source_workspace_guard_verified,
        source_design_lock_message_id=result.source_design_lock_message_id,
        source_execution_message_id=result.source_execution_message_id,
        workspace_path_preview=result.workspace_path_preview,
        workspace_path_within_root=result.workspace_path_within_root,
        operation_manifest_created=result.operation_manifest_created,
        manifest_operations_count=result.manifest_operations_count,
        manifest_allowed_operations_count=result.manifest_allowed_operations_count,
        manifest_blocked_operations_count=result.manifest_blocked_operations_count,
        manifest_operations=[
            SandboxOperationManifestEntryResponse(**operation.model_dump())
            for operation in result.manifest_operations
        ],
        allowed_operation_paths=result.allowed_operation_paths,
        blocked_operation_paths=result.blocked_operation_paths,
        workspace_created=result.workspace_created,
        workspace_written=result.workspace_written,
        file_written=result.file_written,
        controlled_sandbox_write_enabled=result.controlled_sandbox_write_enabled,
        sandbox_write_allowed=result.sandbox_write_allowed,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        main_worktree_write_allowed=result.main_worktree_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        file_write_allowed=result.file_write_allowed,
        actual_patch_applied=result.actual_patch_applied,
        real_code_modified=result.real_code_modified,
        real_diff_generated=result.real_diff_generated,
        patch_applied=result.patch_applied,
        git_write_performed=result.git_write_performed,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        worker_started=result.worker_started,
        task_created=result.task_created,
        run_created=result.run_created,
        worktree_created=result.worktree_created,
        worktree_cleaned_up=result.worktree_cleaned_up,
        rollback_snapshot_created=result.rollback_snapshot_created,
        cleanup_required=result.cleanup_required,
        target_file_content_read=result.target_file_content_read,
        required_preconditions=result.required_preconditions,
        allowed_future_manifest_scope=result.allowed_future_manifest_scope,
        forbidden_manifest_actions=result.forbidden_manifest_actions,
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
        manifest_summary=result.manifest_summary,
        recommended_next_step=result.recommended_next_step,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message=(
            ProjectDirectorMessageResponse.from_domain(manifest_guard.message)
            if manifest_guard.message is not None
            else None
        ),
    )


@router.post(
    "/sessions/{session_id}/sandbox-workspace-create",
    response_model=ConfirmSandboxWorkspaceCreateResponse,
    summary="Create a P21-C sandbox workspace directory",
)
def confirm_session_sandbox_workspace_create(
    session_id: UUID,
    request: ConfirmSandboxWorkspaceCreateRequest,
    workspace_creation_service: Annotated[
        ProjectDirectorSandboxWorkspaceCreationService,
        Depends(_get_sandbox_workspace_creation_service),
    ],
) -> ConfirmSandboxWorkspaceCreateResponse:
    """Create only the guarded sandbox workspace directory after P21-C-B."""

    try:
        workspace_creation = (
            workspace_creation_service.confirm_workspace_creation(
                session_id=session_id,
                source_task_id=request.source_task_id,
                source_message_id=request.source_message_id,
                user_confirmed=request.user_confirmed,
                create_mode=request.create_mode,
            )
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = workspace_creation.result
    if result.creation_status == "blocked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                ";".join(result.blocked_reasons)
                or "sandbox_workspace_create_blocked"
            ),
        )

    return ConfirmSandboxWorkspaceCreateResponse(
        creation_status=result.creation_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        create_mode=result.create_mode,
        source_manifest_status=result.source_manifest_status,
        source_manifest_message_bound=result.source_manifest_message_bound,
        source_manifest_verified=result.source_manifest_verified,
        workspace_path=result.workspace_path,
        workspace_path_within_root=result.workspace_path_within_root,
        workspace_root=result.workspace_root,
        workspace_created=result.workspace_created,
        workspace_already_existed=result.workspace_already_existed,
        workspace_written=result.workspace_written,
        file_written=result.file_written,
        manifest_file_written=result.manifest_file_written,
        target_file_content_read=result.target_file_content_read,
        real_diff_generated=result.real_diff_generated,
        patch_applied=result.patch_applied,
        controlled_sandbox_write_enabled=(
            result.controlled_sandbox_write_enabled
        ),
        sandbox_write_allowed=result.sandbox_write_allowed,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        main_worktree_write_allowed=result.main_worktree_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        file_write_allowed=result.file_write_allowed,
        actual_patch_applied=result.actual_patch_applied,
        real_code_modified=result.real_code_modified,
        git_write_performed=result.git_write_performed,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        worker_started=result.worker_started,
        task_created=result.task_created,
        run_created=result.run_created,
        worktree_created=result.worktree_created,
        worktree_cleaned_up=result.worktree_cleaned_up,
        rollback_snapshot_created=result.rollback_snapshot_created,
        cleanup_required=result.cleanup_required,
        cleanup_hint=result.cleanup_hint,
        required_preconditions=result.required_preconditions,
        allowed_future_creation_scope=result.allowed_future_creation_scope,
        forbidden_creation_actions=result.forbidden_creation_actions,
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
        creation_summary=result.creation_summary,
        recommended_next_step=result.recommended_next_step,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message=(
            ProjectDirectorMessageResponse.from_domain(workspace_creation.message)
            if workspace_creation.message is not None
            else None
        ),
    )


@router.post(
    "/sessions/{session_id}/sandbox-workspace-evidence-manifest",
    response_model=ConfirmSandboxWorkspaceManifestWriteResponse,
    summary="Write a P21-C sandbox workspace evidence manifest",
)
def confirm_session_sandbox_workspace_manifest_write(
    session_id: UUID,
    request: ConfirmSandboxWorkspaceManifestWriteRequest,
    manifest_write_service: Annotated[
        ProjectDirectorSandboxWorkspaceManifestWriteService,
        Depends(_get_sandbox_workspace_manifest_write_service),
    ],
) -> ConfirmSandboxWorkspaceManifestWriteResponse:
    """Write only the fixed internal evidence manifest after P21-C-C."""

    try:
        manifest_write = manifest_write_service.confirm_workspace_manifest_write(
            session_id=session_id,
            source_task_id=request.source_task_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
            write_mode=request.write_mode,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = manifest_write.result
    if result.manifest_write_status == "blocked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                ";".join(result.blocked_reasons)
                or "sandbox_workspace_manifest_write_blocked"
            ),
        )

    return ConfirmSandboxWorkspaceManifestWriteResponse(
        manifest_write_status=result.manifest_write_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        write_mode=result.write_mode,
        source_workspace_creation_status=result.source_workspace_creation_status,
        source_workspace_creation_message_bound=(
            result.source_workspace_creation_message_bound
        ),
        source_workspace_creation_verified=result.source_workspace_creation_verified,
        workspace_path=result.workspace_path,
        workspace_path_within_root=result.workspace_path_within_root,
        workspace_root=result.workspace_root,
        manifest_dir_path=result.manifest_dir_path,
        manifest_file_path=result.manifest_file_path,
        manifest_dir_created=result.manifest_dir_created,
        manifest_file_written=result.manifest_file_written,
        manifest_file_overwritten=result.manifest_file_overwritten,
        business_file_written=result.business_file_written,
        target_file_content_read=result.target_file_content_read,
        real_diff_generated=result.real_diff_generated,
        patch_applied=result.patch_applied,
        controlled_sandbox_write_enabled=(
            result.controlled_sandbox_write_enabled
        ),
        sandbox_write_allowed=result.sandbox_write_allowed,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        main_worktree_write_allowed=result.main_worktree_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        file_write_allowed=result.file_write_allowed,
        actual_patch_applied=result.actual_patch_applied,
        real_code_modified=result.real_code_modified,
        git_write_performed=result.git_write_performed,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        worker_started=result.worker_started,
        task_created=result.task_created,
        run_created=result.run_created,
        worktree_created=result.worktree_created,
        worktree_cleaned_up=result.worktree_cleaned_up,
        rollback_snapshot_created=result.rollback_snapshot_created,
        cleanup_required=result.cleanup_required,
        cleanup_hint=result.cleanup_hint,
        required_preconditions=result.required_preconditions,
        allowed_future_manifest_write_scope=(
            result.allowed_future_manifest_write_scope
        ),
        forbidden_manifest_write_actions=result.forbidden_manifest_write_actions,
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
        manifest_write_summary=result.manifest_write_summary,
        recommended_next_step=result.recommended_next_step,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message=(
            ProjectDirectorMessageResponse.from_domain(manifest_write.message)
            if manifest_write.message is not None
            else None
        ),
    )


@router.post(
    "/sessions/{session_id}/sandbox-candidate-files-write",
    response_model=ConfirmSandboxCandidateFilesWriteResponse,
    summary="Write P21-C sandbox candidate business files",
)
def confirm_session_sandbox_candidate_files_write(
    session_id: UUID,
    request: ConfirmSandboxCandidateFilesWriteRequest,
    candidate_write_service: Annotated[
        ProjectDirectorSandboxCandidateFileWriteService,
        Depends(_get_sandbox_candidate_file_write_service),
    ],
) -> ConfirmSandboxCandidateFilesWriteResponse:
    """Write only requested candidate files after P21-C-D manifest write."""

    candidate_files = [
        CandidateSandboxFileWrite(
            relative_path=item.relative_path,
            content=item.content,
            operation=item.operation,
            content_encoding=item.content_encoding,
        )
        for item in request.candidate_files
    ]

    try:
        candidate_write = candidate_write_service.confirm_candidate_files_write(
            session_id=session_id,
            source_task_id=request.source_task_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
            candidate_files=candidate_files,
            write_mode=request.write_mode,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = candidate_write.result
    if result.candidate_write_status == "blocked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                ";".join(result.blocked_reasons)
                or "sandbox_candidate_files_write_blocked"
            ),
        )

    return ConfirmSandboxCandidateFilesWriteResponse(
        candidate_write_status=result.candidate_write_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        write_mode=result.write_mode,
        source_manifest_write_status=result.source_manifest_write_status,
        source_manifest_write_message_bound=(
            result.source_manifest_write_message_bound
        ),
        source_manifest_write_verified=result.source_manifest_write_verified,
        source_workspace_creation_message_id=(
            result.source_workspace_creation_message_id
        ),
        source_operation_manifest_message_id=(
            result.source_operation_manifest_message_id
        ),
        workspace_path=result.workspace_path,
        workspace_path_within_root=result.workspace_path_within_root,
        workspace_root=result.workspace_root,
        internal_manifest_file_path=result.internal_manifest_file_path,
        internal_manifest_verified=result.internal_manifest_verified,
        candidate_files_requested_count=result.candidate_files_requested_count,
        candidate_files_written_count=result.candidate_files_written_count,
        candidate_files_blocked_count=result.candidate_files_blocked_count,
        candidate_written_files=[
            CandidateSandboxWrittenFileResponse(**item.model_dump(mode="json"))
            for item in result.candidate_written_files
        ],
        candidate_blocked_files=[
            CandidateSandboxBlockedFileResponse(**item.model_dump(mode="json"))
            for item in result.candidate_blocked_files
        ],
        candidate_business_files_written=result.candidate_business_files_written,
        business_file_written=result.business_file_written,
        manifest_file_written=result.manifest_file_written,
        target_file_content_read=result.target_file_content_read,
        real_diff_generated=result.real_diff_generated,
        patch_applied=result.patch_applied,
        controlled_sandbox_write_enabled=(
            result.controlled_sandbox_write_enabled
        ),
        sandbox_write_allowed=result.sandbox_write_allowed,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        main_worktree_write_allowed=result.main_worktree_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        file_write_allowed=result.file_write_allowed,
        actual_patch_applied=result.actual_patch_applied,
        real_code_modified=result.real_code_modified,
        git_write_performed=result.git_write_performed,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        worker_started=result.worker_started,
        task_created=result.task_created,
        run_created=result.run_created,
        worktree_created=result.worktree_created,
        worktree_cleaned_up=result.worktree_cleaned_up,
        rollback_snapshot_created=result.rollback_snapshot_created,
        cleanup_required=result.cleanup_required,
        cleanup_hint=result.cleanup_hint,
        required_preconditions=result.required_preconditions,
        allowed_future_candidate_write_scope=(
            result.allowed_future_candidate_write_scope
        ),
        forbidden_candidate_write_actions=result.forbidden_candidate_write_actions,
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
        candidate_write_summary=result.candidate_write_summary,
        recommended_next_step=result.recommended_next_step,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message=(
            ProjectDirectorMessageResponse.from_domain(candidate_write.message)
            if candidate_write.message is not None
            else None
        ),
    )


@router.post(
    "/sessions/{session_id}/sandbox-candidate-diff-generate",
    response_model=ConfirmSandboxCandidateDiffGenerateResponse,
    summary="Generate P21-C-F readonly real diff from sandbox candidate files",
)
def confirm_session_sandbox_candidate_diff_generate(
    session_id: UUID,
    request: ConfirmSandboxCandidateDiffGenerateRequest,
    candidate_diff_service: Annotated[
        ProjectDirectorSandboxCandidateDiffService,
        Depends(_get_sandbox_candidate_diff_service),
    ],
) -> ConfirmSandboxCandidateDiffGenerateResponse:
    """Generate a readonly unified diff after P21-C-E candidate file write."""

    try:
        candidate_diff = candidate_diff_service.confirm_candidate_diff_generation(
            session_id=session_id,
            source_task_id=request.source_task_id,
            source_message_id=request.source_message_id,
            user_confirmed=request.user_confirmed,
            diff_mode=request.diff_mode,
            max_diff_bytes=request.max_diff_bytes,
        )
    except ValueError as exc:
        detail = str(exc)
        lowered = detail.lower()
        if "not found" in lowered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc

    result = candidate_diff.result
    if result.diff_generation_status == "blocked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                ";".join(result.blocked_reasons)
                or "sandbox_candidate_diff_generate_blocked"
            ),
        )

    return ConfirmSandboxCandidateDiffGenerateResponse(
        diff_generation_status=result.diff_generation_status,
        session_id=result.session_id,
        source_task_id=result.source_task_id,
        source_message_id=result.source_message_id,
        diff_mode=result.diff_mode,
        source_candidate_write_status=result.source_candidate_write_status,
        source_candidate_write_message_bound=(
            result.source_candidate_write_message_bound
        ),
        source_candidate_write_verified=result.source_candidate_write_verified,
        source_workspace_manifest_write_message_id=(
            result.source_workspace_manifest_write_message_id
        ),
        source_workspace_creation_message_id=(
            result.source_workspace_creation_message_id
        ),
        source_operation_manifest_message_id=(
            result.source_operation_manifest_message_id
        ),
        workspace_path=result.workspace_path,
        workspace_path_within_root=result.workspace_path_within_root,
        workspace_root=result.workspace_root,
        internal_manifest_file_path=result.internal_manifest_file_path,
        internal_manifest_verified=result.internal_manifest_verified,
        repo_root=result.repo_root,
        target_file_content_read=result.target_file_content_read,
        candidate_file_content_read=result.candidate_file_content_read,
        readonly_real_diff_generated=result.readonly_real_diff_generated,
        real_diff_generated=result.real_diff_generated,
        diff_bytes=result.diff_bytes,
        diff_file_count=result.diff_file_count,
        diff_entries=[
            CandidateSandboxDiffEntryResponse(**item.model_dump(mode="json"))
            for item in result.diff_entries
        ],
        unified_diff_text=result.unified_diff_text,
        candidate_files_considered_count=result.candidate_files_considered_count,
        candidate_files_diffed_count=result.candidate_files_diffed_count,
        candidate_files_blocked_count=result.candidate_files_blocked_count,
        candidate_diff_blocked_files=[
            CandidateSandboxDiffBlockedFileResponse(**item.model_dump(mode="json"))
            for item in result.candidate_diff_blocked_files
        ],
        main_project_file_written=result.main_project_file_written,
        sandbox_file_written=result.sandbox_file_written,
        manifest_file_written=result.manifest_file_written,
        patch_applied=result.patch_applied,
        controlled_sandbox_write_enabled=(
            result.controlled_sandbox_write_enabled
        ),
        sandbox_write_allowed=result.sandbox_write_allowed,
        product_runtime_git_write_allowed=result.product_runtime_git_write_allowed,
        main_worktree_write_allowed=result.main_worktree_write_allowed,
        worktree_write_allowed=result.worktree_write_allowed,
        file_write_allowed=result.file_write_allowed,
        actual_patch_applied=result.actual_patch_applied,
        real_code_modified=result.real_code_modified,
        git_write_performed=result.git_write_performed,
        native_executor_started=result.native_executor_started,
        codex_started=result.codex_started,
        claude_code_started=result.claude_code_started,
        worker_started=result.worker_started,
        task_created=result.task_created,
        run_created=result.run_created,
        worktree_created=result.worktree_created,
        worktree_cleaned_up=result.worktree_cleaned_up,
        rollback_snapshot_created=result.rollback_snapshot_created,
        cleanup_required=result.cleanup_required,
        cleanup_hint=result.cleanup_hint,
        required_preconditions=result.required_preconditions,
        allowed_future_diff_scope=result.allowed_future_diff_scope,
        forbidden_diff_actions=result.forbidden_diff_actions,
        blocked_reasons=result.blocked_reasons,
        risks=result.risks,
        unknowns=result.unknowns,
        diff_generation_summary=result.diff_generation_summary,
        recommended_next_step=result.recommended_next_step,
        ai_project_director_total_loop=result.ai_project_director_total_loop,
        message=(
            ProjectDirectorMessageResponse.from_domain(candidate_diff.message)
            if candidate_diff.message is not None
            else None
        ),
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


class WorkbenchResumeResponse(BaseModel):
    session: SessionResponse | None = None
    plan_version: PlanVersionResponse | None = None
    task_creation: TaskCreationResponse | None = None
    recent_messages: list[ProjectDirectorMessageResponse] = Field(default_factory=list)
    source: str = Field(default="none")
    next_action: str = Field(default="暂无可恢复的 Project Director 流程。")


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
    "/inbox",
    response_model=DirectorInboxResponse,
    summary="List synthetic Project Director inbox items",
)
def list_project_director_inbox(
    db_session: Annotated[Session, Depends(get_db_session)],
    project_id: UUID | None = None,
    kind: InboxItemKind | None = None,
    status_filter: InboxItemStatus | None = Query(default=None, alias="status"),
    priority: InboxItemPriority | None = None,
    limit: int = 50,
) -> DirectorInboxResponse:
    """Return the P7-D1 synthetic DirectorInbox read model.

    This endpoint is read-only. It never creates inbox items, conversations,
    sessions, messages, tasks, runs, workers, provider calls, approvals,
    retries, executor launches, or Git state.
    """

    result = ProjectDirectorInboxService(db_session).list_inbox_items(
        project_id=project_id,
        kind=kind,
        status=status_filter,
        priority=priority,
        limit=limit,
    )
    return DirectorInboxResponse(
        items=[DirectorInboxItemResponse.from_domain(item) for item in result.items],
        has_more=result.has_more,
    )


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
