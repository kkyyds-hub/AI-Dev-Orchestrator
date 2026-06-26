"""Project Director controlled programmer no-write execution contract."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel


ProgrammerExecutor = Literal["codex", "claude-code"]
ProgrammerNoWriteExecutionMode = Literal[
    "dry_run", "fake_execution", "controlled_no_write"
]
ProgrammerNoWriteExecutionStatus = Literal["planned", "executed", "blocked"]
RiskLevel = Literal["low", "medium", "high"]


class ProjectDirectorProgrammerNoWriteExecutionRequest(DomainModel):
    """Request to produce a no-write programmer execution result."""

    session_id: UUID
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    requested_programmer_executor: ProgrammerExecutor = "codex"
    execution_mode: ProgrammerNoWriteExecutionMode = "dry_run"


class ProjectDirectorProgrammerNoWriteExecutionStep(DomainModel):
    """One structured no-write execution step."""

    step_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1_000)
    source_plan_step_ids: list[str] = Field(default_factory=list, max_length=20)
    files_considered: list[str] = Field(default_factory=list, max_length=20)
    patch_preview: list[str] = Field(default_factory=list, max_length=20)
    tests_to_run: list[str] = Field(default_factory=list, max_length=20)
    risk_notes: list[str] = Field(default_factory=list, max_length=12)


class _ProgrammerNoWriteExecutionSafetyModel(DomainModel):
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
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
        "product_runtime_git_write_allowed",
        "worktree_write_allowed",
        "file_write_allowed",
        "actual_patch_applied",
        "real_code_modified",
        "git_write_performed",
        "native_executor_started",
        "codex_started",
        "claude_code_started",
        "worker_started",
        "task_created",
        "run_created",
        mode="after",
    )
    @classmethod
    def reject_write_start_and_patch_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError("programmer no-write execution flags must remain false")
        return value


class ProjectDirectorProgrammerNoWriteExecutionResult(
    _ProgrammerNoWriteExecutionSafetyModel
):
    """Result returned after preparing a programmer no-write execution."""

    execution_status: ProgrammerNoWriteExecutionStatus
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    requested_programmer_executor: ProgrammerExecutor = "codex"
    execution_mode: ProgrammerNoWriteExecutionMode = "dry_run"
    execution_message_bound: bool = False
    execution_summary: str = ""
    execution_steps: list[ProjectDirectorProgrammerNoWriteExecutionStep] = Field(
        default_factory=list
    )
    patch_preview: list[str] = Field(default_factory=list, max_length=20)
    files_considered: list[str] = Field(default_factory=list, max_length=20)
    tests_to_run: list[str] = Field(default_factory=list, max_length=20)
    implementation_notes: list[str] = Field(default_factory=list, max_length=20)
    handoff_notes: list[str] = Field(default_factory=list, max_length=20)
    risk_notes: list[str] = Field(default_factory=list, max_length=20)
    risk_level: RiskLevel = "low"
    recommended_next_step: str = ""
    source_plan_refs: list[str] = Field(default_factory=list, max_length=20)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


__all__ = (
    "ProgrammerExecutor",
    "ProgrammerNoWriteExecutionMode",
    "ProgrammerNoWriteExecutionStatus",
    "ProjectDirectorProgrammerNoWriteExecutionRequest",
    "ProjectDirectorProgrammerNoWriteExecutionResult",
    "ProjectDirectorProgrammerNoWriteExecutionStep",
)
