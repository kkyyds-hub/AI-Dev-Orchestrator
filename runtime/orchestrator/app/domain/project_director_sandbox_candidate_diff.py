"""Readonly real diff generation result for Project Director P21-C-F."""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel


SandboxCandidateDiffMode = Literal["readonly_unified_diff"]
SandboxCandidateDiffGenerationStatus = Literal["generated", "blocked"]
SandboxCandidateDiffBaseContentSource = Literal["exact_git_commit_object"]

P21_C_SANDBOX_CANDIDATE_DIFF_BASE_EVIDENCE_SCHEMA_VERSION = (
    "p21-c-f.base-evidence.v1"
)
P21_C_SANDBOX_CANDIDATE_DIFF_BASE_CONTENT_SOURCE_EXACT_GIT_COMMIT_OBJECT = (
    "exact_git_commit_object"
)

_LOWER_HEX_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CandidateSandboxDiffEntry(DomainModel):
    """One readonly unified diff generated from a sandbox candidate file."""

    relative_path: str = Field(min_length=1, max_length=2_000)
    operation: str = Field(min_length=1, max_length=40)
    target_file_path: str = Field(min_length=1, max_length=2_000)
    candidate_file_path: str = Field(min_length=1, max_length=2_000)
    target_file_existed: bool
    candidate_file_existed: bool
    target_file_content_read: bool
    candidate_file_content_read: bool
    unified_diff: str
    diff_bytes: int = Field(ge=0)


class CandidateSandboxDiffBlockedFile(DomainModel):
    """One candidate file rejected before readonly diff generation."""

    relative_path: str = Field(default="", max_length=2_000)
    operation: str = Field(default="", max_length=40)
    blocked_reasons: list[str] = Field(default_factory=list)


class ProjectDirectorSandboxCandidateDiffResult(DomainModel):
    """P21-C-F result for readonly real diff generation."""

    diff_generation_status: SandboxCandidateDiffGenerationStatus
    session_id: UUID
    source_task_id: UUID | None = None
    source_message_id: UUID | None = None
    diff_mode: SandboxCandidateDiffMode = "readonly_unified_diff"
    source_candidate_write_status: str | None = Field(default=None, max_length=120)
    source_candidate_write_message_bound: bool = False
    source_candidate_write_verified: bool = False
    source_workspace_manifest_write_message_id: UUID | None = None
    source_workspace_creation_message_id: UUID | None = None
    source_operation_manifest_message_id: UUID | None = None
    workspace_path: str | None = Field(default=None, max_length=2_000)
    workspace_path_within_root: bool = False
    workspace_root: str | None = Field(default=None, max_length=2_000)
    internal_manifest_file_path: str | None = Field(default=None, max_length=2_000)
    internal_manifest_verified: bool = False
    repo_root: str | None = Field(default=None, max_length=2_000)
    base_evidence_schema_version: str | None = Field(default=None, max_length=80)
    base_commit_sha: str | None = Field(default=None, min_length=40, max_length=40)
    base_snapshot_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    base_content_source: SandboxCandidateDiffBaseContentSource | None = None
    readonly_base_snapshot_verified: bool = False
    target_file_content_read: bool = False
    candidate_file_content_read: bool = False
    readonly_real_diff_generated: bool = False
    real_diff_generated: bool = False
    diff_bytes: int = Field(default=0, ge=0)
    diff_file_count: int = Field(default=0, ge=0)
    diff_entries: list[CandidateSandboxDiffEntry] = Field(default_factory=list)
    unified_diff_text: str = ""
    candidate_files_considered_count: int = Field(default=0, ge=0)
    candidate_files_diffed_count: int = Field(default=0, ge=0)
    candidate_files_blocked_count: int = Field(default=0, ge=0)
    candidate_diff_blocked_files: list[CandidateSandboxDiffBlockedFile] = Field(
        default_factory=list
    )
    main_project_file_written: bool = False
    sandbox_file_written: bool = False
    manifest_file_written: bool = False
    patch_applied: bool = False
    controlled_sandbox_write_enabled: bool = False
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
    worktree_created: bool = False
    worktree_cleaned_up: bool = False
    rollback_snapshot_created: bool = False
    cleanup_required: bool = False
    cleanup_hint: str = Field(default="", max_length=1_000)
    required_preconditions: list[str] = Field(default_factory=list)
    allowed_future_diff_scope: list[str] = Field(default_factory=list)
    forbidden_diff_actions: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    diff_generation_summary: str = Field(min_length=1, max_length=2_000)
    recommended_next_step: str = Field(min_length=1, max_length=1_000)
    ai_project_director_total_loop: str = "Partial"

    @field_validator(
        "main_project_file_written",
        "sandbox_file_written",
        "manifest_file_written",
        "patch_applied",
        "controlled_sandbox_write_enabled",
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
        "worktree_created",
        "worktree_cleaned_up",
        "rollback_snapshot_created",
        mode="after",
    )
    @classmethod
    def reject_forbidden_side_effect_flags(cls, value: bool) -> bool:
        if value:
            raise ValueError("P21-C-F readonly diff generation may not write or execute")
        return value

    @field_validator("base_evidence_schema_version")
    @classmethod
    def validate_base_evidence_schema_version(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value != P21_C_SANDBOX_CANDIDATE_DIFF_BASE_EVIDENCE_SCHEMA_VERSION:
            raise ValueError("unexpected P21-C-F base evidence schema version")
        return value

    @field_validator("base_commit_sha")
    @classmethod
    def validate_base_commit_sha(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _LOWER_HEX_GIT_SHA.fullmatch(value):
            raise ValueError("P21-C-F base commit must be a lowercase 40-character SHA")
        return value

    @field_validator("base_snapshot_fingerprint")
    @classmethod
    def validate_base_snapshot_fingerprint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _LOWER_HEX_SHA256.fullmatch(value):
            raise ValueError(
                "P21-C-F base snapshot fingerprint must be a lowercase SHA-256"
            )
        return value

    @model_validator(mode="after")
    def validate_base_evidence(self) -> "ProjectDirectorSandboxCandidateDiffResult":
        if self.diff_generation_status == "blocked":
            if self.readonly_base_snapshot_verified:
                raise ValueError(
                    "blocked P21-C-F results may not claim a verified base snapshot"
                )
            if any(
                value is not None
                for value in (
                    self.base_evidence_schema_version,
                    self.base_commit_sha,
                    self.base_snapshot_fingerprint,
                    self.base_content_source,
                )
            ):
                raise ValueError(
                    "blocked P21-C-F results may not carry successful base authority evidence"
                )
            return self

        if not self.readonly_base_snapshot_verified:
            raise ValueError(
                "generated P21-C-F results require a verified base snapshot"
            )
        if (
            self.base_evidence_schema_version
            != P21_C_SANDBOX_CANDIDATE_DIFF_BASE_EVIDENCE_SCHEMA_VERSION
        ):
            raise ValueError(
                "generated P21-C-F results require the exact base evidence schema version"
            )
        if self.base_commit_sha is None:
            raise ValueError(
                "generated P21-C-F results require an exact persisted base commit"
            )
        if self.base_snapshot_fingerprint is None:
            raise ValueError(
                "generated P21-C-F results require a persisted base snapshot fingerprint"
            )
        if (
            self.base_content_source
            != P21_C_SANDBOX_CANDIDATE_DIFF_BASE_CONTENT_SOURCE_EXACT_GIT_COMMIT_OBJECT
        ):
            raise ValueError(
                "generated P21-C-F base content must come from an exact Git commit object"
            )
        return self


__all__ = (
    "CandidateSandboxDiffBlockedFile",
    "CandidateSandboxDiffEntry",
    "P21_C_SANDBOX_CANDIDATE_DIFF_BASE_CONTENT_SOURCE_EXACT_GIT_COMMIT_OBJECT",
    "P21_C_SANDBOX_CANDIDATE_DIFF_BASE_EVIDENCE_SCHEMA_VERSION",
    "ProjectDirectorSandboxCandidateDiffResult",
    "SandboxCandidateDiffGenerationStatus",
    "SandboxCandidateDiffBaseContentSource",
    "SandboxCandidateDiffMode",
)
