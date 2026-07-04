"""Readonly real diff review handoff result for Project Director P21-C-G."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel


SandboxCandidateDiffReviewHandoffMode = Literal["readonly_real_diff_review"]
SandboxCandidateDiffReviewHandoffStatus = Literal["created", "blocked"]
SandboxCandidateDiffReviewExecutor = Literal["codex", "claude-code"]


class ProjectDirectorSandboxCandidateDiffReviewHandoffResult(DomainModel):
    """P21-C-G result for creating a readonly real diff review handoff record."""

    review_handoff_status: SandboxCandidateDiffReviewHandoffStatus
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    source_diff_message_id: UUID | None = None
    handoff_mode: SandboxCandidateDiffReviewHandoffMode = "readonly_real_diff_review"
    requested_reviewer_executor: SandboxCandidateDiffReviewExecutor = "codex"
    source_diff_message_bound: bool = False
    source_diff_verified: bool = False
    source_diff_sha256: str = Field(default="", max_length=64)
    diff_file_count: int = Field(default=0, ge=0)
    diff_bytes: int = Field(default=0, ge=0)
    review_scope_paths: list[str] = Field(default_factory=list)
    target_file_content_read: bool = False
    candidate_file_content_read: bool = False
    readonly_real_diff_generated: bool = False
    real_diff_generated: bool = False
    reviewer_started: bool = False
    review_executed: bool = False
    review_verdict_generated: bool = False
    review_findings_generated: bool = False
    main_project_file_written: bool = False
    sandbox_file_written: bool = False
    manifest_file_written: bool = False
    diff_file_written: bool = False
    patch_applied: bool = False
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
    cleanup_hint: str = Field(default="", max_length=1_000)
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_review_scope: list[str] = Field(default_factory=list)
    forbidden_handoff_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    review_handoff_summary: str = Field(min_length=1, max_length=2_000)
    recommended_next_step: str = Field(min_length=1, max_length=1_000)
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
        "reviewer_started",
        "review_executed",
        "review_verdict_generated",
        "review_findings_generated",
        "main_project_file_written",
        "sandbox_file_written",
        "manifest_file_written",
        "diff_file_written",
        "patch_applied",
        "product_runtime_git_write_allowed",
        "main_worktree_write_allowed",
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
        "worktree_created",
        "worktree_cleaned_up",
        "rollback_snapshot_created",
        mode="after",
    )
    @classmethod
    def reject_forbidden_side_effect_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError("P21-C-G handoff may not review, write, or execute")
        return value


__all__ = (
    "ProjectDirectorSandboxCandidateDiffReviewHandoffResult",
    "SandboxCandidateDiffReviewExecutor",
    "SandboxCandidateDiffReviewHandoffMode",
    "SandboxCandidateDiffReviewHandoffStatus",
)
