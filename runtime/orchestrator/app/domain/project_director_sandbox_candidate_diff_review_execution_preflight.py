"""Readonly diff review execution preflight for Project Director P21-C-H-A."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel
from app.domain.project_director_sandbox_candidate_diff_review_handoff import (
    SandboxCandidateDiffReviewExecutor,
)


SandboxCandidateDiffReviewExecutionPreflightStatus = Literal["ready", "blocked"]


class ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightResult(
    DomainModel
):
    """P21-C-H-A locks readonly reviewer execution input without execution."""

    review_execution_preflight_status: (
        SandboxCandidateDiffReviewExecutionPreflightStatus
    )
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    source_handoff_message_id: UUID | None = None
    source_diff_message_id: UUID | None = None
    requested_reviewer_executor: SandboxCandidateDiffReviewExecutor = "codex"
    source_handoff_verified: bool = False
    source_diff_verified: bool = False
    source_diff_sha256: str = Field(default="", max_length=64)
    review_input_schema_version: str = Field(default="p21-c-h-a.v1")
    review_output_schema_version: str = Field(
        default="p21-c-h-review-output.v1"
    )
    review_prompt_sha256: str = Field(default="", max_length=64)
    review_prompt_bytes: int = Field(default=0, ge=0)
    review_scope_paths: list[str] = Field(default_factory=list)
    reviewer_started: bool = False
    review_executed: bool = False
    review_findings_generated: bool = False
    review_verdict_generated: bool = False
    provider_called: bool = False
    native_executor_started: bool = False
    codex_started: bool = False
    claude_code_started: bool = False
    main_project_file_written: bool = False
    sandbox_file_written: bool = False
    manifest_file_written: bool = False
    diff_file_written: bool = False
    patch_applied: bool = False
    product_runtime_git_write_allowed: bool = False
    git_write_performed: bool = False
    worktree_created: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_review_execution_scope: list[str] = Field(
        default_factory=list
    )
    forbidden_preflight_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    review_execution_preflight_summary: str = Field(
        min_length=1,
        max_length=2_000,
    )
    recommended_next_step: str = Field(min_length=1, max_length=1_000)
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
        "reviewer_started",
        "review_executed",
        "review_findings_generated",
        "review_verdict_generated",
        "provider_called",
        "native_executor_started",
        "codex_started",
        "claude_code_started",
        "main_project_file_written",
        "sandbox_file_written",
        "manifest_file_written",
        "diff_file_written",
        "patch_applied",
        "product_runtime_git_write_allowed",
        "git_write_performed",
        "worktree_created",
        "worker_started",
        "task_created",
        "run_created",
        mode="after",
    )
    @classmethod
    def reject_forbidden_side_effect_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError("P21-C-H-A preflight may not review, write, or execute")
        return value


__all__ = (
    "ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightResult",
    "SandboxCandidateDiffReviewExecutionPreflightStatus",
)
