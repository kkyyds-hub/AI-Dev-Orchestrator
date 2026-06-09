"""Pure one-shot token reference contract for the P9 real Git write pilot.

This module defines token reference and audit readback shapes only. It does not
issue token values, consume tokens, start executors, call APIs or services, read
environment values, inspect workspaces, or perform product runtime Git writes.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.real_git_write_pilot import (
    RealGitWritePilotApprovalDecision,
    reject_pilot_suspicious_text,
)


class RealGitWritePilotTokenStatus(StrEnum):
    PENDING = "pending"
    ISSUABLE = "issuable"
    ISSUED_REFERENCE = "issued_reference"
    CONSUMED_REFERENCE = "consumed_reference"
    EXPIRED = "expired"
    REVOKED = "revoked"
    BLOCKED = "blocked"


class RealGitWritePilotTokenPurpose(StrEnum):
    AUTHORIZE_SINGLE_DOC_ONLY_PILOT = "authorize_single_doc_only_pilot"
    VERIFY_MANUAL_APPROVAL_SCOPE = "verify_manual_approval_scope"
    BIND_EXECUTOR_AND_WORKSPACE_READBACK = "bind_executor_and_workspace_readback"


class RealGitWritePilotTokenBlockReason(StrEnum):
    APPROVAL_MISSING = "approval_missing"
    DRY_RUN_NOT_READY = "dry_run_not_ready"
    SCOPE_MISMATCH = "scope_mismatch"
    EXPIRED = "expired"
    ALREADY_CONSUMED = "already_consumed"
    ALREADY_REVOKED = "already_revoked"
    RAW_TOKEN_VALUE_PRESENT = "raw_token_value_present"
    EXECUTION_NOT_STARTED = "execution_not_started"
    PRODUCT_RUNTIME_GIT_WRITE_NOT_STARTED = "product_runtime_git_write_not_started"


_SECRET_LIKE_TOKEN_HINT_PATTERN = re.compile(
    r"("
    r"api\s*[_-]?\s*key|"
    r"token\s*[=:]|"
    r"secret|"
    r"password|"
    r"bearer\s+[A-Za-z0-9._~+/=-]{8,}|"
    r"sk-(?:ant-)?(?:proj-|svcacct-)?[A-Za-z0-9_-]{12,}|"
    r"github_pat_[A-Za-z0-9_]{12,}|"
    r"gh[pousr]_[A-Za-z0-9_]{12,}|"
    r"[A-Za-z0-9_-]{32,}"
    r")",
    re.IGNORECASE,
)


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _normalize_required_datetime(value: datetime) -> datetime:
    normalized = ensure_utc_datetime(value)
    if normalized is None:
        raise ValueError("datetime must not be None")
    return normalized


def _normalize_optional_datetime(value: datetime | None) -> datetime | None:
    return ensure_utc_datetime(value)


def _normalize_file_paths(values: list[str]) -> list[str]:
    normalized_items: list[str] = []
    seen_items: set[str] = set()
    for value in values:
        normalized = _trim_required_string(value)
        if not isinstance(normalized, str) or not normalized:
            raise ValueError("file path must not be blank")
        safe_value = reject_pilot_suspicious_text(normalized, "bound_file_paths")
        if safe_value is None:
            raise ValueError("file path must not be blank")
        if safe_value not in seen_items:
            normalized_items.append(safe_value)
            seen_items.add(safe_value)
    return normalized_items


def _validate_token_hint(value: str) -> str:
    normalized = reject_pilot_suspicious_text(value, "token_hint")
    if normalized is None:
        raise ValueError("token_hint must not be blank")
    if _SECRET_LIKE_TOKEN_HINT_PATTERN.search(normalized):
        raise ValueError("token_hint must be a short non-secret reference hint")
    return normalized


class RealGitWritePilotTokenScope(DomainModel):
    pilot_id: str = Field(min_length=1, max_length=120)
    approval_id: str = Field(min_length=1, max_length=120)
    executor_id: str = Field(min_length=1, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    target_branch: str = Field(min_length=1, max_length=200)
    file_paths: list[str] = Field(min_length=1)
    dry_run_ready: bool
    approval_decision: RealGitWritePilotApprovalDecision
    approval_phrase_matched: bool
    approved_scope_summary: str = Field(min_length=1, max_length=1_000)

    @field_validator(
        "pilot_id",
        "approval_id",
        "executor_id",
        "workspace_id",
        "target_branch",
        mode="before",
    )
    @classmethod
    def trim_required_text(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("file_paths")
    @classmethod
    def normalize_paths(cls, values: list[str]) -> list[str]:
        normalized = _normalize_file_paths(values)
        if not normalized:
            raise ValueError("file_paths must not be empty")
        return normalized

    @field_validator("approved_scope_summary")
    @classmethod
    def validate_approved_scope_summary(cls, value: str) -> str:
        normalized = reject_pilot_suspicious_text(value, "approved_scope_summary")
        if normalized is None:
            raise ValueError("approved_scope_summary must not be blank")
        return normalized


class RealGitWritePilotOneShotTokenReference(DomainModel):
    token_id: str = Field(min_length=1, max_length=120)
    pilot_id: str = Field(min_length=1, max_length=120)
    approval_id: str = Field(min_length=1, max_length=120)
    purpose: RealGitWritePilotTokenPurpose
    status: RealGitWritePilotTokenStatus
    token_hint: str = Field(min_length=1, max_length=64)
    issued_reference_at: datetime | None = None
    expires_at: datetime
    consumed_reference_at: datetime | None = None
    revoked_at: datetime | None = None
    bound_executor_id: str = Field(min_length=1, max_length=120)
    bound_workspace_id: str = Field(min_length=1, max_length=120)
    bound_target_branch: str = Field(min_length=1, max_length=200)
    bound_file_paths: list[str] = Field(min_length=1)
    block_reasons: list[RealGitWritePilotTokenBlockReason] = Field(default_factory=list)
    ready_for_execution: bool = False
    product_runtime_git_write_executed: bool = False
    real_executor_started: bool = False

    @field_validator(
        "token_id",
        "pilot_id",
        "approval_id",
        "bound_executor_id",
        "bound_workspace_id",
        "bound_target_branch",
        mode="before",
    )
    @classmethod
    def trim_required_text(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("token_hint")
    @classmethod
    def validate_hint(cls, value: str) -> str:
        return _validate_token_hint(value)

    @field_validator("bound_file_paths")
    @classmethod
    def normalize_bound_paths(cls, values: list[str]) -> list[str]:
        normalized = _normalize_file_paths(values)
        if not normalized:
            raise ValueError("bound_file_paths must not be empty")
        return normalized

    @field_validator("issued_reference_at", "consumed_reference_at", "revoked_at")
    @classmethod
    def normalize_optional_timestamps(cls, value: datetime | None) -> datetime | None:
        return _normalize_optional_datetime(value)

    @field_validator("expires_at")
    @classmethod
    def normalize_expires_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def enforce_reference_contract(self) -> "RealGitWritePilotOneShotTokenReference":
        created_at = self.issued_reference_at or utc_now()
        if self.expires_at <= created_at:
            raise ValueError("expires_at must be later than issued_reference_at or created_at")
        if self.status == RealGitWritePilotTokenStatus.CONSUMED_REFERENCE:
            if self.consumed_reference_at is None:
                raise ValueError("consumed_reference status requires consumed_reference_at")
        elif self.consumed_reference_at is not None:
            raise ValueError("consumed_reference_at is only allowed for consumed_reference")
        if self.status == RealGitWritePilotTokenStatus.REVOKED:
            if self.revoked_at is None:
                raise ValueError("revoked status requires revoked_at")
        elif self.revoked_at is not None:
            raise ValueError("revoked_at is only allowed for revoked")
        if self.status == RealGitWritePilotTokenStatus.BLOCKED and not self.block_reasons:
            raise ValueError("blocked token reference requires block_reasons")
        if self.status != RealGitWritePilotTokenStatus.BLOCKED and self.block_reasons:
            raise ValueError("non-blocked token reference must not include block_reasons")
        if self.ready_for_execution is not False:
            raise ValueError("token reference must not mark execution ready")
        if self.product_runtime_git_write_executed is not False:
            raise ValueError("product runtime Git write must remain Not started")
        if self.real_executor_started is not False:
            raise ValueError("real executor must remain Not started")
        return self


class RealGitWritePilotTokenAuditReadback(DomainModel):
    event_id: str = Field(min_length=1, max_length=120)
    pilot_id: str = Field(min_length=1, max_length=120)
    token_id: str = Field(min_length=1, max_length=120)
    event_type: str = Field(min_length=1, max_length=120)
    safe_summary: str = Field(min_length=1, max_length=1_000)
    append_only: bool = True
    created_at: datetime
    metadata_count: int = Field(default=0, ge=0)

    @field_validator("event_id", "pilot_id", "token_id", "event_type", mode="before")
    @classmethod
    def trim_required_text(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str) -> str:
        normalized = reject_pilot_suspicious_text(value, "token_audit_safe_summary")
        if normalized is None:
            raise ValueError("safe_summary must not be blank")
        return normalized

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def enforce_append_only(self) -> "RealGitWritePilotTokenAuditReadback":
        if self.append_only is not True:
            raise ValueError("token audit readback must be append-only")
        return self


def build_real_git_write_pilot_token_reference(
    *,
    token_id: str,
    scope: RealGitWritePilotTokenScope,
    purpose: RealGitWritePilotTokenPurpose,
    token_hint: str,
    issued_reference_at: datetime,
    expires_at: datetime,
    bound_executor_id: str | None = None,
    bound_workspace_id: str | None = None,
    bound_target_branch: str | None = None,
    bound_file_paths: list[str] | None = None,
) -> RealGitWritePilotOneShotTokenReference:
    """Build a safe token reference readback without creating a token value."""

    normalized_bound_paths = (
        _normalize_file_paths(bound_file_paths)
        if bound_file_paths is not None
        else list(scope.file_paths)
    )
    effective_executor_id = bound_executor_id or scope.executor_id
    effective_workspace_id = bound_workspace_id or scope.workspace_id
    effective_target_branch = bound_target_branch or scope.target_branch

    block_reasons = _derive_block_reasons(
        scope=scope,
        issued_reference_at=issued_reference_at,
        expires_at=expires_at,
        bound_executor_id=effective_executor_id,
        bound_workspace_id=effective_workspace_id,
        bound_target_branch=effective_target_branch,
        bound_file_paths=normalized_bound_paths,
    )
    status = (
        RealGitWritePilotTokenStatus.BLOCKED
        if block_reasons
        else RealGitWritePilotTokenStatus.ISSUABLE
    )

    return RealGitWritePilotOneShotTokenReference(
        token_id=token_id,
        pilot_id=scope.pilot_id,
        approval_id=scope.approval_id,
        purpose=purpose,
        status=status,
        token_hint=token_hint,
        issued_reference_at=issued_reference_at,
        expires_at=expires_at,
        consumed_reference_at=None,
        revoked_at=None,
        bound_executor_id=effective_executor_id,
        bound_workspace_id=effective_workspace_id,
        bound_target_branch=effective_target_branch,
        bound_file_paths=normalized_bound_paths,
        block_reasons=block_reasons,
        ready_for_execution=False,
        product_runtime_git_write_executed=False,
        real_executor_started=False,
    )


def _derive_block_reasons(
    *,
    scope: RealGitWritePilotTokenScope,
    issued_reference_at: datetime,
    expires_at: datetime,
    bound_executor_id: str,
    bound_workspace_id: str,
    bound_target_branch: str,
    bound_file_paths: list[str],
) -> list[RealGitWritePilotTokenBlockReason]:
    reasons: list[RealGitWritePilotTokenBlockReason] = []
    if scope.approval_decision != RealGitWritePilotApprovalDecision.APPROVED:
        reasons.append(RealGitWritePilotTokenBlockReason.APPROVAL_MISSING)
    if scope.approval_phrase_matched is not True:
        reasons.append(RealGitWritePilotTokenBlockReason.APPROVAL_MISSING)
    if scope.dry_run_ready is not True:
        reasons.append(RealGitWritePilotTokenBlockReason.DRY_RUN_NOT_READY)
    if (
        bound_executor_id != scope.executor_id
        or bound_workspace_id != scope.workspace_id
        or bound_target_branch != scope.target_branch
        or bound_file_paths != scope.file_paths
    ):
        reasons.append(RealGitWritePilotTokenBlockReason.SCOPE_MISMATCH)
    if expires_at <= issued_reference_at:
        reasons.append(RealGitWritePilotTokenBlockReason.EXPIRED)
    return _dedupe_block_reasons(reasons)


def _dedupe_block_reasons(
    reasons: list[RealGitWritePilotTokenBlockReason],
) -> list[RealGitWritePilotTokenBlockReason]:
    normalized: list[RealGitWritePilotTokenBlockReason] = []
    seen: set[RealGitWritePilotTokenBlockReason] = set()
    for reason in reasons:
        if reason in seen:
            continue
        normalized.append(reason)
        seen.add(reason)
    return normalized
