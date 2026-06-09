"""Readiness readback service for the P9 real Git write pilot.

The service evaluates executor readiness and workspace binding from explicit
caller input only. It does not inspect repositories, scan host workspaces,
launch executors, or perform Git operations.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.real_git_write_pilot import (
    RealGitWritePilotBlockReason,
    RealGitWritePilotGateStatus,
    reject_pilot_suspicious_text,
)


_BRANCH_FORBIDDEN_PATTERN = re.compile(r"[\s~^:?*\[\\]")
_PILOT_BRANCH_PATTERN = re.compile(
    r"^ai/gitwrite-pilot/\d{4}-\d{2}-\d{2}-doc-only$",
)
_DOCS_MARKDOWN_PATH_PATTERN = re.compile(r"^docs/(?:[^/]+/)*[^/]+\.md$")
_COMMIT_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{7,64}$")
_WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")
_PROTECTED_BRANCH_NAMES = {"main", "master", "release", "production", "staging", "gh-pages"}
_PROTECTED_BRANCH_PREFIXES = ("release/", "production/", "staging/", "gh-pages/")


class RealGitWritePilotExecutorReadinessInput(DomainModel):
    executor_id: str = Field(min_length=1, max_length=120)
    executor_kind: str = Field(min_length=1, max_length=80)
    configured: bool = False
    authenticated: bool = False
    available: bool = False
    model_or_profile: str | None = Field(default=None, max_length=200)
    safe_summary: str | None = Field(default=None, max_length=1_000)
    checked_at: datetime

    @field_validator("executor_id", "executor_kind", "model_or_profile", mode="before")
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return _trim_optional_string(value) if value is not None else value

    @field_validator("executor_id", "executor_kind", mode="after")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value:
            raise ValueError("text value must not be blank")
        return value

    @field_validator("model_or_profile", "safe_summary")
    @classmethod
    def validate_safe_text(cls, value: str | None) -> str | None:
        return reject_pilot_suspicious_text(value, "executor_readiness")

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)


class RealGitWritePilotWorkspaceBindingInput(DomainModel):
    workspace_id: str = Field(min_length=1, max_length=120)
    repository_id: str = Field(min_length=1, max_length=120)
    base_commit: str = Field(min_length=7, max_length=64)
    target_branch: str = Field(min_length=1, max_length=200)
    file_paths: list[str] = Field(min_length=1)
    workspace_bound: bool = False
    worktree_registered: bool = False
    stale_workspace_detected: bool = False
    safe_path_confirmed: bool = False
    safe_summary: str | None = Field(default=None, max_length=1_000)
    checked_at: datetime

    @field_validator(
        "workspace_id",
        "repository_id",
        "base_commit",
        "target_branch",
        mode="before",
    )
    @classmethod
    def trim_required_text(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("base_commit")
    @classmethod
    def validate_base_commit(cls, value: str) -> str:
        normalized = value.strip()
        if _COMMIT_ID_PATTERN.fullmatch(normalized) is None:
            raise ValueError("base_commit must be a commit id")
        return normalized

    @field_validator("file_paths")
    @classmethod
    def normalize_file_paths(cls, values: list[str]) -> list[str]:
        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for value in values:
            normalized = _normalize_file_path_for_readback(value)
            if normalized not in seen_items:
                normalized_items.append(normalized)
                seen_items.add(normalized)
        if not normalized_items:
            raise ValueError("file_paths must not be empty")
        return normalized_items

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str | None) -> str | None:
        return reject_pilot_suspicious_text(value, "workspace_binding")

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)


class RealGitWritePilotReadinessRequest(DomainModel):
    pilot_id: str = Field(min_length=1, max_length=120)
    executor: RealGitWritePilotExecutorReadinessInput
    workspace: RealGitWritePilotWorkspaceBindingInput
    requested_by: str = Field(min_length=1, max_length=120)
    requested_at: datetime

    @field_validator("pilot_id", "requested_by", mode="before")
    @classmethod
    def trim_required_text(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)


class RealGitWritePilotReadinessGateCheck(DomainModel):
    gate_name: str = Field(min_length=1, max_length=120)
    status: RealGitWritePilotGateStatus
    passed: bool = False
    block_reason: RealGitWritePilotBlockReason | None = None
    safe_summary: str | None = Field(default=None, max_length=1_000)
    checked_at: datetime

    @field_validator("gate_name", mode="before")
    @classmethod
    def trim_gate_name(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str | None) -> str | None:
        return reject_pilot_suspicious_text(value, "readiness_gate")

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def validate_status_contract(self) -> "RealGitWritePilotReadinessGateCheck":
        if self.status == RealGitWritePilotGateStatus.PASSED:
            if self.passed is not True:
                raise ValueError("passed gate requires passed=True")
            if self.block_reason is not None:
                raise ValueError("passed gate must not include block_reason")
        if self.status == RealGitWritePilotGateStatus.BLOCKED:
            if self.passed is not False:
                raise ValueError("blocked gate requires passed=False")
            if self.block_reason is None:
                raise ValueError("blocked gate requires block_reason")
        return self


class RealGitWritePilotExecutorReadinessReadback(DomainModel):
    executor_id: str
    executor_kind: str
    configured: bool
    authenticated: bool
    available: bool
    model_or_profile: str | None = None
    ready: bool
    safe_summary: str
    checked_at: datetime


class RealGitWritePilotWorkspaceBindingReadback(DomainModel):
    workspace_id: str
    repository_id: str
    base_commit: str
    target_branch: str
    file_paths: list[str]
    workspace_bound: bool
    worktree_registered: bool
    stale_workspace_detected: bool
    safe_path_confirmed: bool
    bound: bool
    safe_summary: str
    checked_at: datetime


class RealGitWritePilotReadinessReadback(DomainModel):
    pilot_id: str
    executor_readiness: RealGitWritePilotExecutorReadinessReadback
    workspace_binding: RealGitWritePilotWorkspaceBindingReadback
    gate_checks: list[RealGitWritePilotReadinessGateCheck] = Field(min_length=1)
    ready_for_preview: bool
    ready_for_execution: bool = False
    product_runtime_git_write_executed: bool = False
    real_executor_started: bool = False
    safe_summary: str
    audit_event_summaries: list[str]
    created_at: datetime

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str) -> str:
        normalized = reject_pilot_suspicious_text(value, "readiness_readback")
        if normalized is None:
            raise ValueError("safe_summary must not be blank")
        return normalized

    @field_validator("audit_event_summaries")
    @classmethod
    def validate_audit_summaries(cls, values: list[str]) -> list[str]:
        normalized_items: list[str] = []
        for value in values:
            safe_value = reject_pilot_suspicious_text(value, "audit_event_summary")
            if safe_value is not None:
                normalized_items.append(safe_value)
        return normalized_items

    @model_validator(mode="after")
    def enforce_no_execution_contract(self) -> "RealGitWritePilotReadinessReadback":
        if self.ready_for_execution is not False:
            raise ValueError("readiness readback must not mark execution ready")
        if self.product_runtime_git_write_executed is not False:
            raise ValueError("product runtime Git write must remain Not started")
        if self.real_executor_started is not False:
            raise ValueError("real executor must remain Not started")
        return self


class RealGitWritePilotReadinessService:
    """Build executor and workspace readiness readback without side effects."""

    def build_readiness(
        self,
        request: RealGitWritePilotReadinessRequest,
    ) -> RealGitWritePilotReadinessReadback:
        created_at = utc_now()
        executor_ready = (
            request.executor.configured
            and request.executor.authenticated
            and request.executor.available
        )
        workspace_bound = (
            request.workspace.workspace_bound
            and request.workspace.worktree_registered
            and request.workspace.safe_path_confirmed
            and not request.workspace.stale_workspace_detected
        )
        branch_allowed = _is_pilot_branch_allowed(request.workspace.target_branch)
        file_scope_allowed = all(
            _DOCS_MARKDOWN_PATH_PATTERN.fullmatch(path) is not None
            for path in request.workspace.file_paths
        )

        gate_checks = [
            _gate(
                "executor_readiness",
                executor_ready,
                RealGitWritePilotBlockReason.EXECUTOR_NOT_READY,
                "executor readiness evaluated from caller input",
                created_at,
            ),
            _gate(
                "workspace_binding",
                workspace_bound,
                RealGitWritePilotBlockReason.WORKSPACE_NOT_BOUND,
                "workspace binding evaluated from caller input",
                created_at,
            ),
            _gate(
                "target_branch_allowlist",
                branch_allowed,
                _branch_block_reason(request.workspace.target_branch),
                "target branch evaluated against pilot allowlist",
                created_at,
            ),
            _gate(
                "file_scope",
                file_scope_allowed,
                RealGitWritePilotBlockReason.FILE_SCOPE_NOT_ALLOWED,
                "file scope evaluated against docs markdown allowlist",
                created_at,
            ),
        ]
        ready_for_preview = all(check.passed for check in gate_checks)

        return RealGitWritePilotReadinessReadback(
            pilot_id=request.pilot_id,
            executor_readiness=RealGitWritePilotExecutorReadinessReadback(
                executor_id=request.executor.executor_id,
                executor_kind=request.executor.executor_kind,
                configured=request.executor.configured,
                authenticated=request.executor.authenticated,
                available=request.executor.available,
                model_or_profile=request.executor.model_or_profile,
                ready=executor_ready,
                safe_summary=(
                    request.executor.safe_summary
                    or "Executor readiness was supplied by caller input."
                ),
                checked_at=request.executor.checked_at,
            ),
            workspace_binding=RealGitWritePilotWorkspaceBindingReadback(
                workspace_id=request.workspace.workspace_id,
                repository_id=request.workspace.repository_id,
                base_commit=request.workspace.base_commit,
                target_branch=request.workspace.target_branch,
                file_paths=request.workspace.file_paths,
                workspace_bound=request.workspace.workspace_bound,
                worktree_registered=request.workspace.worktree_registered,
                stale_workspace_detected=request.workspace.stale_workspace_detected,
                safe_path_confirmed=request.workspace.safe_path_confirmed,
                bound=workspace_bound,
                safe_summary=(
                    request.workspace.safe_summary
                    or "Workspace binding was supplied by caller input."
                ),
                checked_at=request.workspace.checked_at,
            ),
            gate_checks=gate_checks,
            ready_for_preview=ready_for_preview,
            ready_for_execution=False,
            product_runtime_git_write_executed=False,
            real_executor_started=False,
            safe_summary=(
                "Readiness readback generated from caller input only; no executor "
                "launch or product runtime Git write was started."
            ),
            audit_event_summaries=[
                "Executor readiness readback evaluated without host probing.",
                "Workspace binding readback evaluated without host path inspection.",
            ],
            created_at=created_at,
        )


def _trim_optional_string(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _normalize_required_datetime(value: datetime) -> datetime:
    normalized = ensure_utc_datetime(value)
    if normalized is None:
        raise ValueError("datetime must not be None")
    return normalized


def _normalize_file_path_for_readback(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("file path must not be blank")
    if "\x00" in normalized:
        raise ValueError("file path must not contain NUL")
    if (
        normalized.startswith("/")
        or normalized.startswith("\\")
        or normalized.startswith("~")
        or _WINDOWS_DRIVE_PATH_PATTERN.match(normalized) is not None
    ):
        raise ValueError("file path must be a relative path")
    parts = re.split(r"[\\/]+", normalized)
    if any(part == ".." for part in parts):
        raise ValueError("file path must not contain traversal")
    return normalized.replace("\\", "/")


def _is_pilot_branch_allowed(value: str) -> bool:
    normalized = value.strip()
    if not normalized or normalized == "HEAD":
        return False
    if (
        ".." in normalized
        or normalized.startswith("/")
        or normalized.endswith("/")
        or _BRANCH_FORBIDDEN_PATTERN.search(normalized)
    ):
        return False
    if normalized in _PROTECTED_BRANCH_NAMES or normalized.startswith(
        _PROTECTED_BRANCH_PREFIXES,
    ):
        return False
    return _PILOT_BRANCH_PATTERN.fullmatch(normalized) is not None


def _branch_block_reason(value: str) -> RealGitWritePilotBlockReason:
    normalized = value.strip()
    if normalized in _PROTECTED_BRANCH_NAMES or normalized.startswith(
        _PROTECTED_BRANCH_PREFIXES,
    ):
        return RealGitWritePilotBlockReason.MAIN_BRANCH_BLOCKED
    return RealGitWritePilotBlockReason.TARGET_BRANCH_NOT_ALLOWED


def _gate(
    gate_name: str,
    passed: bool,
    block_reason: RealGitWritePilotBlockReason,
    safe_summary: str,
    checked_at: datetime,
) -> RealGitWritePilotReadinessGateCheck:
    if passed:
        return RealGitWritePilotReadinessGateCheck(
            gate_name=gate_name,
            status=RealGitWritePilotGateStatus.PASSED,
            passed=True,
            checked_at=checked_at,
            safe_summary=safe_summary,
        )
    return RealGitWritePilotReadinessGateCheck(
        gate_name=gate_name,
        status=RealGitWritePilotGateStatus.BLOCKED,
        passed=False,
        block_reason=block_reason,
        checked_at=checked_at,
        safe_summary=safe_summary,
    )
