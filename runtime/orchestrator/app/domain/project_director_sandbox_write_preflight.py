"""Policy-only sandbox write preflight domain for Project Director P20."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.domain._base import DomainModel
from app.domain.project_director_patch_preview_safety import (
    assert_patch_preview_safe,
)
from app.domain.project_director_sandbox_write_policy import (
    ProjectDirectorSandboxPathPolicyResult,
    SandboxFileOperationType,
)


SandboxWritePreflightMode = Literal[
    "dry_run", "fake_preflight", "controlled_sandbox_write"
]
SandboxWritePreflightStatus = Literal["passed", "blocked"]


class ProjectDirectorFileOperationPlan(DomainModel):
    """One proposed file operation for policy-only preflight."""

    path: str = Field(min_length=1, max_length=1_000)
    operation: SandboxFileOperationType
    reason: str = Field(min_length=1, max_length=1_000)
    expected_current_hash: str | None = Field(default=None, max_length=200)
    content_preview_hash: str | None = Field(default=None, max_length=200)
    linked_evidence_refs: list[str] = Field(default_factory=list, max_length=50)
    patch_preview: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("patch_preview", mode="after")
    @classmethod
    def reject_applyable_patch_preview(cls, value: list[str]) -> list[str]:
        return assert_patch_preview_safe(value)


class ProjectDirectorAcceptedSandboxWriteOperation(DomainModel):
    """Accepted no-write operation intent from P20 path policy."""

    path: str = Field(min_length=1, max_length=1_000)
    operation: SandboxFileOperationType


class ProjectDirectorSandboxWritePreflightRequest(DomainModel):
    """Request to evaluate a sandbox write plan without performing writes."""

    session_id: UUID
    source_task_id: UUID
    source_message_id: UUID
    user_confirmed: bool = False
    preflight_mode: SandboxWritePreflightMode = "dry_run"
    allowed_path_prefixes: list[str] = Field(default_factory=list, max_length=50)
    allow_frontend: bool = False
    allow_lockfile: bool = False
    allow_binary: bool = False
    file_operations: list[ProjectDirectorFileOperationPlan] = Field(
        default_factory=list, max_length=100
    )


class ProjectDirectorSandboxWritePreflightResult(DomainModel):
    """No-write result for a policy-only sandbox write preflight."""

    preflight_status: SandboxWritePreflightStatus
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    preflight_mode: SandboxWritePreflightMode = "dry_run"
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
    path_policy_results: list[ProjectDirectorSandboxPathPolicyResult] = Field(
        default_factory=list
    )
    accepted_operations: list[ProjectDirectorAcceptedSandboxWriteOperation] = Field(
        default_factory=list
    )
    accepted_operation_paths: list[str] = Field(default_factory=list)
    blocked_operation_paths: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    recommended_next_step: str = ""
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
        "sandbox_write_allowed",
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
        mode="after",
    )
    @classmethod
    def reject_write_start_and_creation_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError("sandbox write preflight flags must remain false")
        return value


__all__ = (
    "ProjectDirectorAcceptedSandboxWriteOperation",
    "ProjectDirectorFileOperationPlan",
    "ProjectDirectorSandboxWritePreflightRequest",
    "ProjectDirectorSandboxWritePreflightResult",
    "SandboxWritePreflightMode",
    "SandboxWritePreflightStatus",
)
