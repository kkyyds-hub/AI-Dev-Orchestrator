"""Strict readonly reviewer output validation contract for P21-C-H-B1."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.domain._base import DomainModel


ReviewOutputValidationStatus = Literal["validated", "blocked"]
ReviewVerdict = Literal[
    "no_blocking_findings",
    "non_blocking_findings",
    "changes_required",
]
ReviewRiskLevel = Literal["low", "medium", "high"]


class ProjectDirectorSandboxCandidateDiffReviewFinding(DomainModel):
    """One validated readonly reviewer finding."""

    finding_id: str = Field(min_length=1, max_length=80)
    severity: ReviewRiskLevel
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1_000)
    evidence_paths: list[str] = Field(min_length=1, max_length=12)
    recommended_action: str = Field(min_length=1, max_length=500)


class ProjectDirectorSandboxCandidateDiffValidatedReviewOutput(DomainModel):
    """Trusted reviewer output after strict JSON, schema, and semantic checks."""

    review_status: Literal["reviewed"]
    verdict: ReviewVerdict
    risk_level: ReviewRiskLevel
    summary: str = Field(min_length=1, max_length=2_000)
    findings: list[ProjectDirectorSandboxCandidateDiffReviewFinding] = Field(
        max_length=20
    )
    recommended_next_step: str = Field(min_length=1, max_length=1_000)


class ProjectDirectorSandboxCandidateDiffReviewOutputValidationResult(
    DomainModel
):
    """P21-C-H-B1 parser result with explicit blocked/validated state."""

    validation_status: ReviewOutputValidationStatus
    review_output_schema_version: str
    raw_output_sha256: str
    raw_output_bytes: int = Field(ge=0)

    strict_json_valid: bool
    schema_valid: bool
    semantics_valid: bool
    evidence_scope_valid: bool

    review_status: Literal["reviewed"] | None = None
    verdict: ReviewVerdict | None = None
    risk_level: ReviewRiskLevel | None = None
    summary: str = ""
    findings: list[ProjectDirectorSandboxCandidateDiffReviewFinding] = Field(
        default_factory=list
    )
    recommended_next_step: str = ""

    blocked_reasons: list[str] = Field(default_factory=list)

    reviewer_started: bool = False
    review_executed: bool = False
    provider_called: bool = False
    native_executor_started: bool = False
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
        "reviewer_started",
        "review_executed",
        "provider_called",
        "native_executor_started",
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
            raise ValueError("review output validation may not execute or write")
        return value


__all__ = (
    "ProjectDirectorSandboxCandidateDiffReviewFinding",
    "ProjectDirectorSandboxCandidateDiffReviewOutputValidationResult",
    "ProjectDirectorSandboxCandidateDiffValidatedReviewOutput",
    "ReviewOutputValidationStatus",
    "ReviewRiskLevel",
    "ReviewVerdict",
)
