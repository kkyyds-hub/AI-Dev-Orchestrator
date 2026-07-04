"""Readonly reviewer adapter result domain model for P21-C-H-B2-A."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel
from app.domain.project_director_sandbox_candidate_diff_review_output import (
    ProjectDirectorSandboxCandidateDiffReviewFinding,
    ReviewOutputValidationStatus,
    ReviewRiskLevel,
    ReviewVerdict,
)


ReadonlyReviewerAdapterStatus = Literal["validated_output", "blocked"]
ReadonlyReviewerAdapterExecutionMode = Literal["fake_transport"]


class ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult(DomainModel):
    """P21-C-H-B2-A adapter result with explicit blocked/validated state."""

    adapter_status: ReadonlyReviewerAdapterStatus
    execution_mode: ReadonlyReviewerAdapterExecutionMode = "fake_transport"
    requested_reviewer_executor: str = ""

    review_prompt_verified: bool = False
    review_prompt_sha256: str = Field(default="", max_length=64)
    review_prompt_bytes: int = Field(default=0, ge=0)

    review_scope_paths: list[str] = Field(default_factory=list)
    review_output_schema_version: str = ""

    transport_invoked: bool = False
    transport_status: str = ""
    transport_error_code: str | None = None

    output_validation_status: ReviewOutputValidationStatus | None = None
    raw_output_sha256: str = ""
    raw_output_bytes: int = Field(default=0, ge=0)

    strict_json_valid: bool = False
    schema_valid: bool = False
    semantics_valid: bool = False
    evidence_scope_valid: bool = False

    review_status: Literal["reviewed"] | None = None
    verdict: ReviewVerdict | None = None
    risk_level: ReviewRiskLevel | None = None
    summary: str = ""
    findings: list[ProjectDirectorSandboxCandidateDiffReviewFinding] = Field(
        default_factory=list
    )
    recommended_next_step: str = ""

    output_validation_blocked_reasons: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)

    real_reviewer_started: bool = False
    real_reviewer_executed: bool = False
    native_process_started: bool = False
    provider_called: bool = False
    codex_started: bool = False
    claude_code_started: bool = False

    main_project_file_written: bool = False
    sandbox_file_written: bool = False
    manifest_file_written: bool = False
    diff_file_written: bool = False
    patch_applied: bool = False
    git_write_performed: bool = False
    worktree_created: bool = False
    worker_started: bool = False
    task_created: bool = False
    run_created: bool = False

    ai_project_director_total_loop: str = "Partial"

    @field_validator(
        "real_reviewer_started",
        "real_reviewer_executed",
        "native_process_started",
        "provider_called",
        "codex_started",
        "claude_code_started",
        "main_project_file_written",
        "sandbox_file_written",
        "manifest_file_written",
        "diff_file_written",
        "patch_applied",
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
            raise ValueError("readonly reviewer adapter may not execute or write")
        return value


__all__ = (
    "ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult",
    "ReadonlyReviewerAdapterExecutionMode",
    "ReadonlyReviewerAdapterStatus",
)
