"""Project Director controlled programmer no-write planning contract."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel


ProgrammerExecutor = Literal["codex", "claude-code"]
ProgrammerNoWritePlanningMode = Literal[
    "dry_run", "fake_plan", "controlled_no_write"
]
ProgrammerNoWritePlanStatus = Literal["planned", "blocked"]
RiskLevel = Literal["low", "medium", "high"]


class ProjectDirectorProgrammerNoWritePlanRequest(DomainModel):
    """Request to produce a no-write programmer implementation plan."""

    session_id: UUID
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    requested_programmer_executor: ProgrammerExecutor = "codex"
    planning_mode: ProgrammerNoWritePlanningMode = "dry_run"


class ProjectDirectorProgrammerNoWritePlannedStep(DomainModel):
    """One structured implementation step without any repository write."""

    step_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1_000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=12)
    affected_files_preview: list[str] = Field(default_factory=list, max_length=20)
    required_targeted_tests: list[str] = Field(default_factory=list, max_length=20)
    risk_notes: list[str] = Field(default_factory=list, max_length=12)


class _ProgrammerNoWritePlanSafetyModel(DomainModel):
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
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
        "product_runtime_git_write_allowed",
        "worktree_write_allowed",
        "file_write_allowed",
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
    def reject_write_and_start_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError("programmer no-write planning flags must remain false")
        return value


class ProjectDirectorProgrammerNoWritePlanResult(
    _ProgrammerNoWritePlanSafetyModel
):
    """Result returned after preparing a programmer no-write plan."""

    plan_status: ProgrammerNoWritePlanStatus
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    requested_programmer_executor: ProgrammerExecutor = "codex"
    planning_mode: ProgrammerNoWritePlanningMode = "dry_run"
    plan_message_bound: bool = False
    implementation_summary: str = ""
    planned_steps: list[ProjectDirectorProgrammerNoWritePlannedStep] = Field(
        default_factory=list
    )
    affected_files_preview: list[str] = Field(default_factory=list, max_length=20)
    required_evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    required_targeted_tests: list[str] = Field(default_factory=list, max_length=20)
    reviewer_feedback_refs: list[str] = Field(default_factory=list, max_length=20)
    risk_level: RiskLevel = "low"
    recommended_next_step: str = ""
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


__all__ = (
    "ProgrammerExecutor",
    "ProgrammerNoWritePlanningMode",
    "ProgrammerNoWritePlanStatus",
    "ProjectDirectorProgrammerNoWritePlanRequest",
    "ProjectDirectorProgrammerNoWritePlanResult",
    "ProjectDirectorProgrammerNoWritePlannedStep",
)
