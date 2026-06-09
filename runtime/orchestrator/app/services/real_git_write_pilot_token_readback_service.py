"""Token reference readback service for the P9 real Git write pilot.

The service returns a safe reference readback only. It does not issue token
values, consume tokens, inspect workspaces, start executors, or perform Git
operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.real_git_write_pilot import reject_pilot_suspicious_text
from app.domain.real_git_write_pilot_token import (
    RealGitWritePilotOneShotTokenReference,
    RealGitWritePilotTokenAuditReadback,
    RealGitWritePilotTokenPurpose,
    RealGitWritePilotTokenScope,
    build_real_git_write_pilot_token_reference,
)


class RealGitWritePilotTokenReadbackRequest(DomainModel):
    token_id: str = Field(min_length=1, max_length=120)
    scope: RealGitWritePilotTokenScope
    purpose: RealGitWritePilotTokenPurpose
    token_hint: str = Field(min_length=1, max_length=64)
    issued_reference_at: datetime
    expires_at: datetime
    requested_by: str = Field(min_length=1, max_length=120)
    requested_at: datetime
    bound_executor_id: str | None = Field(default=None, max_length=120)
    bound_workspace_id: str | None = Field(default=None, max_length=120)
    bound_target_branch: str | None = Field(default=None, max_length=200)
    bound_file_paths: list[str] | None = None

    @field_validator(
        "token_id",
        "token_hint",
        "requested_by",
        "bound_executor_id",
        "bound_workspace_id",
        "bound_target_branch",
        mode="before",
    )
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("issued_reference_at", "expires_at", "requested_at")
    @classmethod
    def normalize_required_datetime(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def validate_request_contract(self) -> "RealGitWritePilotTokenReadbackRequest":
        if self.expires_at <= self.issued_reference_at:
            raise ValueError("expires_at must be later than issued_reference_at")
        if self.expires_at <= self.requested_at:
            raise ValueError("expires_at must be later than requested_at")
        return self


class RealGitWritePilotTokenReadback(DomainModel):
    token_reference: RealGitWritePilotOneShotTokenReference
    audit_readback: RealGitWritePilotTokenAuditReadback
    token_issue_started: bool = False
    token_consume_started: bool = False
    ready_for_execution: bool = False
    product_runtime_git_write_executed: bool = False
    real_executor_started: bool = False
    safe_summary: str = Field(min_length=1, max_length=1_000)
    created_at: datetime

    @field_validator("safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str) -> str:
        normalized = reject_pilot_suspicious_text(value, "token_readback_safe_summary")
        if normalized is None:
            raise ValueError("safe_summary must not be blank")
        return normalized

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def enforce_readback_only_contract(self) -> "RealGitWritePilotTokenReadback":
        if self.token_issue_started is not False:
            raise ValueError("token readback must not start token issue")
        if self.token_consume_started is not False:
            raise ValueError("token readback must not start token consume")
        if self.ready_for_execution is not False:
            raise ValueError("token readback must not mark execution ready")
        if self.product_runtime_git_write_executed is not False:
            raise ValueError("product runtime Git write must remain Not started")
        if self.real_executor_started is not False:
            raise ValueError("real executor must remain Not started")
        if self.audit_readback.append_only is not True:
            raise ValueError("token readback audit must be append-only")
        return self


class RealGitWritePilotTokenReadbackService:
    """Build a token reference readback without issue or consume capability."""

    def build_readback(
        self,
        request: RealGitWritePilotTokenReadbackRequest,
    ) -> RealGitWritePilotTokenReadback:
        created_at = utc_now()
        token_reference = build_real_git_write_pilot_token_reference(
            token_id=request.token_id,
            scope=request.scope,
            purpose=request.purpose,
            token_hint=request.token_hint,
            issued_reference_at=request.issued_reference_at,
            expires_at=request.expires_at,
            bound_executor_id=request.bound_executor_id,
            bound_workspace_id=request.bound_workspace_id,
            bound_target_branch=request.bound_target_branch,
            bound_file_paths=request.bound_file_paths,
        )
        safe_summary = _safe_summary_for_reference(token_reference)

        return RealGitWritePilotTokenReadback(
            token_reference=token_reference,
            audit_readback=RealGitWritePilotTokenAuditReadback(
                event_id=f"token-readback-{request.token_id}",
                pilot_id=request.scope.pilot_id,
                token_id=request.token_id,
                event_type="token_reference_readback",
                safe_summary=safe_summary,
                append_only=True,
                created_at=created_at,
                metadata_count=len(token_reference.block_reasons),
            ),
            token_issue_started=False,
            token_consume_started=False,
            ready_for_execution=False,
            product_runtime_git_write_executed=False,
            real_executor_started=False,
            safe_summary=safe_summary,
            created_at=created_at,
        )


def _safe_summary_for_reference(
    token_reference: RealGitWritePilotOneShotTokenReference,
) -> str:
    if token_reference.status == "issuable":
        return "One-shot token reference is issuable as readback only."
    return "One-shot token reference is blocked as readback only."


def _normalize_required_datetime(value: datetime) -> datetime:
    normalized = ensure_utc_datetime(value)
    if normalized is None:
        raise ValueError("datetime must not be None")
    return normalized
