"""Manual approval readback service for the P9 real Git write pilot.

The service records a caller-provided approval intent as safe readback only. It
does not issue tokens, start executors, inspect workspaces, or perform Git
operations.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.real_git_write_pilot import reject_pilot_suspicious_text
from app.services.real_git_write_pilot_dry_run_plan_service import (
    RealGitWritePilotDryRunPlan,
)


EXPLICIT_APPROVAL_PHRASES: frozenset[str] = frozenset(
    {
        "我确认此次试点写入",
        "I confirm this pilot write",
    },
)


class RealGitWritePilotApprovalReadbackDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    BLOCKED = "blocked"


class RealGitWritePilotApprovalReadbackRequest(DomainModel):
    pilot_id: str = Field(min_length=1, max_length=120)
    dry_run_plan: RealGitWritePilotDryRunPlan
    approved_by: str = Field(min_length=1, max_length=120)
    approval_phrase: str = Field(min_length=1, max_length=120)
    approved_scope_summary: str = Field(min_length=1, max_length=1_000)
    requested_at: datetime
    expires_at: datetime

    @field_validator("pilot_id", "approved_by", "approval_phrase", mode="before")
    @classmethod
    def trim_required_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("approved_scope_summary")
    @classmethod
    def validate_scope_summary(cls, value: str) -> str:
        normalized = reject_pilot_suspicious_text(value, "approved_scope_summary")
        if normalized is None:
            raise ValueError("approved_scope_summary must not be blank")
        return normalized

    @field_validator("requested_at", "expires_at")
    @classmethod
    def normalize_required_datetime(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def validate_request_contract(self) -> "RealGitWritePilotApprovalReadbackRequest":
        if self.dry_run_plan.pilot_id != self.pilot_id:
            raise ValueError("dry_run_plan pilot_id must match request pilot_id")
        if self.dry_run_plan.ready_for_execution is not False:
            raise ValueError("dry-run plan must not be execution-ready")
        if self.expires_at <= self.requested_at:
            raise ValueError("expires_at must be later than requested_at")
        return self


class RealGitWritePilotApprovalReadback(DomainModel):
    approval_id: str = Field(min_length=1, max_length=120)
    pilot_id: str = Field(min_length=1, max_length=120)
    decision: RealGitWritePilotApprovalReadbackDecision
    approved_by: str = Field(min_length=1, max_length=120)
    approval_phrase_matched: bool
    approved_scope_summary: str = Field(min_length=1, max_length=1_000)
    dry_run_ready: bool
    ready_for_execution: bool = False
    one_shot_token_issued: bool = False
    product_runtime_git_write_executed: bool = False
    real_executor_started: bool = False
    safe_summary: str = Field(min_length=1, max_length=1_000)
    audit_event_summaries: list[str] = Field(min_length=1)
    created_at: datetime
    expires_at: datetime

    @field_validator("approved_scope_summary", "safe_summary")
    @classmethod
    def validate_safe_summary(cls, value: str) -> str:
        normalized = reject_pilot_suspicious_text(value, "approval_readback")
        if normalized is None:
            raise ValueError("approval readback text must not be blank")
        return normalized

    @field_validator("audit_event_summaries")
    @classmethod
    def validate_audit_summaries(cls, values: list[str]) -> list[str]:
        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for value in values:
            safe_value = reject_pilot_suspicious_text(value, "approval_audit_summary")
            if safe_value is not None and safe_value not in seen_items:
                normalized_items.append(safe_value)
                seen_items.add(safe_value)
        if not normalized_items:
            raise ValueError("audit_event_summaries must not be empty")
        return normalized_items

    @field_validator("created_at", "expires_at")
    @classmethod
    def normalize_datetimes(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def enforce_no_execution_contract(self) -> "RealGitWritePilotApprovalReadback":
        if self.ready_for_execution is not False:
            raise ValueError("approval readback must not mark execution ready")
        if self.one_shot_token_issued is not False:
            raise ValueError("approval readback must not issue one-shot tokens")
        if self.product_runtime_git_write_executed is not False:
            raise ValueError("product runtime Git write must remain Not started")
        if self.real_executor_started is not False:
            raise ValueError("real executor must remain Not started")
        if self.decision == RealGitWritePilotApprovalReadbackDecision.APPROVED:
            if self.approval_phrase_matched is not True or self.dry_run_ready is not True:
                raise ValueError("approved readback requires matched phrase and ready dry-run")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be later than created_at")
        return self


class RealGitWritePilotApprovalReadbackService:
    """Build a manual approval readback without execution capability."""

    def build_readback(
        self,
        request: RealGitWritePilotApprovalReadbackRequest,
    ) -> RealGitWritePilotApprovalReadback:
        created_at = utc_now()
        phrase_matched = request.approval_phrase in EXPLICIT_APPROVAL_PHRASES
        dry_run_ready = request.dry_run_plan.dry_run_ready is True
        decision = _derive_decision(phrase_matched, dry_run_ready)

        return RealGitWritePilotApprovalReadback(
            approval_id=f"pilot-approval-readback-{request.pilot_id}",
            pilot_id=request.pilot_id,
            decision=decision,
            approved_by=request.approved_by,
            approval_phrase_matched=phrase_matched,
            approved_scope_summary=request.approved_scope_summary,
            dry_run_ready=dry_run_ready,
            ready_for_execution=False,
            one_shot_token_issued=False,
            product_runtime_git_write_executed=False,
            real_executor_started=False,
            safe_summary=_safe_summary_for_decision(decision),
            audit_event_summaries=[
                "Manual approval intent recorded as readback only.",
                "No one-shot token, executor launch, or product runtime Git write occurred.",
            ],
            created_at=created_at,
            expires_at=request.expires_at,
        )


def _derive_decision(
    phrase_matched: bool,
    dry_run_ready: bool,
) -> RealGitWritePilotApprovalReadbackDecision:
    if not dry_run_ready:
        return RealGitWritePilotApprovalReadbackDecision.BLOCKED
    if not phrase_matched:
        return RealGitWritePilotApprovalReadbackDecision.PENDING
    return RealGitWritePilotApprovalReadbackDecision.APPROVED


def _safe_summary_for_decision(
    decision: RealGitWritePilotApprovalReadbackDecision,
) -> str:
    if decision == RealGitWritePilotApprovalReadbackDecision.APPROVED:
        return "Explicit manual approval phrase matched for readback only."
    if decision == RealGitWritePilotApprovalReadbackDecision.BLOCKED:
        return "Manual approval readback blocked because dry-run readiness is incomplete."
    return "Manual approval readback is pending an explicit confirmation phrase."


def _normalize_required_datetime(value: datetime) -> datetime:
    normalized = ensure_utc_datetime(value)
    if normalized is None:
        raise ValueError("datetime must not be None")
    return normalized
