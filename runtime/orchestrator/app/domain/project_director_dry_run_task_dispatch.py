"""Project Director confirmed dry-run task dispatch contract."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.domain._base import DomainModel


class ProjectDirectorDryRunTaskDispatchRequest(DomainModel):
    """Request to confirm one P11 dry-run message for safe task dispatch."""

    session_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False


class ProjectDirectorDryRunTaskDispatchPlan(DomainModel):
    """Safe dry-run task draft derived from a P11 evidence-to-agent message."""

    session_id: UUID
    source_message_id: UUID
    evidence_pack_id: str | None = None
    user_goal: str
    task_title: str
    task_input_summary: str
    allowed_files: list[str] = Field(default_factory=list)
    forbidden_files: list[str] = Field(default_factory=list)
    targeted_tests: list[str] = Field(default_factory=list)
    dispatch_status: str = "ready_for_confirmation"
    safe_dry_run_task: bool = True
    worker_simulate_required: bool = True
    product_runtime_git_write_allowed: bool = False
    frontend_required: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    ai_project_director_total_loop: str = "Partial"
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ProjectDirectorDryRunTaskDispatchResult(DomainModel):
    """Result of confirming and creating one safe dry-run task."""

    dispatch_status: str
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
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
