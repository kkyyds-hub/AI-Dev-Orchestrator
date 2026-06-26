"""Project Director readonly reviewer deep-review contract."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel


ReviewerExecutor = Literal["codex", "claude-code"]
ReviewMode = Literal["dry_run", "fake_review", "controlled_review"]
ReviewStatus = Literal["planned", "reviewed", "blocked"]
RiskLevel = Literal["low", "medium", "high"]


class ProjectDirectorReadonlyReviewFinding(DomainModel):
    """One sanitized readonly review finding."""

    finding_id: str = Field(min_length=1, max_length=80)
    severity: RiskLevel = "low"
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1_000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=12)
    recommended_action: str = Field(min_length=1, max_length=500)


class ProjectDirectorReadonlyReviewRequest(DomainModel):
    """Request to plan or record a readonly reviewer review."""

    session_id: UUID
    source_task_id: UUID
    source_message_id: UUID
    p14_lifecycle_message_id: UUID | None = None
    user_confirmed: bool = False
    requested_reviewer_executor: ReviewerExecutor = "codex"
    review_mode: ReviewMode = "dry_run"


class _ReadonlyReviewSafetyModel(DomainModel):
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
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
        "product_runtime_git_write_allowed",
        "worktree_write_allowed",
        "file_write_allowed",
        "real_code_modified",
        "git_write_performed",
        mode="after",
    )
    @classmethod
    def reject_write_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError("readonly review write flags must remain false")
        return value


class ProjectDirectorReadonlyReviewPlan(_ReadonlyReviewSafetyModel):
    """Safe plan for one readonly reviewer deep-review request."""

    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    p14_lifecycle_message_id: UUID | None = None
    user_confirmed: bool = False
    requested_reviewer_executor: ReviewerExecutor = "codex"
    review_mode: ReviewMode = "dry_run"
    review_status: ReviewStatus = "blocked"
    review_result_message_bound: bool = False
    review_findings: list[ProjectDirectorReadonlyReviewFinding] = Field(
        default_factory=list
    )
    review_summary: str = ""
    risk_level: RiskLevel = "low"
    recommended_next_step: str = ""
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ProjectDirectorReadonlyReviewResult(_ReadonlyReviewSafetyModel):
    """Result returned after planning or recording a readonly review."""

    review_status: ReviewStatus
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    p14_lifecycle_message_id: UUID | None = None
    requested_reviewer_executor: ReviewerExecutor = "codex"
    review_mode: ReviewMode = "dry_run"
    review_result_message_bound: bool = False
    review_summary: str = ""
    review_findings: list[ProjectDirectorReadonlyReviewFinding] = Field(
        default_factory=list
    )
    risk_level: RiskLevel = "low"
    recommended_next_step: str = ""
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
