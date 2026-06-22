"""Project Director controlled executor-backed dispatch pilot contract."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.domain._base import DomainModel


AgentRole = Literal["programmer", "reviewer"]
ExecutorLabel = Literal["codex", "claude-code"]
LaunchMode = Literal["dry_run", "controlled_smoke"]
DispatchStatus = Literal["planned", "blocked", "launched"]


class ProjectDirectorControlledExecutorDispatchRequest(DomainModel):
    """Request to plan a controlled executor-backed pilot from a P12 source."""

    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    user_confirmed: bool = False
    requested_agent_role: AgentRole = "programmer"
    requested_executor: ExecutorLabel = "codex"
    launch_mode: LaunchMode = "dry_run"


class ProjectDirectorControlledExecutorDispatchPlan(DomainModel):
    """Safe plan for one controlled executor lifecycle pilot."""

    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    user_confirmed: bool = False
    requested_agent_role: AgentRole = "programmer"
    requested_executor: ExecutorLabel = "codex"
    launch_mode: LaunchMode = "dry_run"
    dispatch_status: DispatchStatus = "blocked"
    controlled_executor_pilot: bool = True
    executor_backed_agent: bool = True
    programmer_agent_allowed: bool = True
    reviewer_agent_allowed: bool = True
    product_runtime_git_write_allowed: bool = False
    worktree_write_allowed: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    supervisor_required: bool = True
    auto_terminate_required: bool = True
    cleanup_required: bool = True
    frontend_required: bool = False
    agent_session_bound: bool = False
    process_handle_id_present: bool = False
    supervisor_registered: bool = False
    supervisor_cleanup_done: bool = False
    run_created: bool = False
    ai_project_director_total_loop: str = "Partial"
    p9_production_safe_long_running_executor_lifecycle: str = "Partial"
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ProjectDirectorControlledExecutorDispatchResult(DomainModel):
    """Result of confirmed controlled executor dispatch planning."""

    dispatch_status: DispatchStatus
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    requested_agent_role: AgentRole = "programmer"
    requested_executor: ExecutorLabel = "codex"
    launch_mode: LaunchMode = "dry_run"
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


class ProjectDirectorControlledExecutorLifecycleResult(DomainModel):
    """Session message contract for one controlled executor lifecycle readback."""

    session_id: UUID
    source_task_id: UUID
    source_message_id: UUID
    requested_agent_role: AgentRole
    requested_executor: ExecutorLabel
    launch_mode: LaunchMode = "dry_run"
    controlled_executor_pilot: bool = True
    executor_backed_agent: bool = True
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    agent_session_bound: bool = False
    runtime_handle_id_present: bool = False
    process_handle_id_present: bool = False
    supervisor_required: bool = True
    supervisor_registered: bool = False
    auto_terminate_required: bool = True
    terminate_attempted: bool = False
    cleanup_required: bool = True
    supervisor_cleanup_done: bool = False
    product_runtime_git_write_allowed: bool = False
    worktree_write_allowed: bool = False
    frontend_required: bool = False
    run_created: bool = False
    real_code_modified: bool = False
    git_write_performed: bool = False
    ai_project_director_total_loop: str = "Partial"
    p9_production_safe_long_running_executor_lifecycle: str = "Partial"
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
