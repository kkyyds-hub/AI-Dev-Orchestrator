"""Pure domain contracts for P9 runtime safety gates and launch approvals.

This module freezes P9-C safety data shapes only. It does not execute safety
checks against the host, read local configuration, inspect environment values,
launch external processes, or create real runtime sessions.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class RuntimeSafetyGateName(StrEnum):
    FEATURE_FLAG = "feature_flag"
    HUMAN_CONFIRMATION = "human_confirmation"
    EXECUTOR_READINESS = "executor_readiness"
    LAUNCH_PREVIEW = "launch_preview"
    WORKSPACE = "workspace"
    COST_BUDGET = "cost_budget"
    CONCURRENCY = "concurrency"
    NO_SECRET_EXPOSURE = "no_secret_exposure"
    NO_ENV_DUMP = "no_env_dump"
    NO_PRODUCT_GIT_WRITE = "no_product_git_write"
    TIMEOUT = "timeout"
    CANCELLATION = "cancellation"
    AUDIT_EVENT = "audit_event"


class RuntimeSafetyGateStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class RuntimeLaunchRequestStatus(StrEnum):
    DRAFT = "draft"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    CONSUMED = "consumed"
    CANCELLED = "cancelled"


class RuntimeApprovalDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RuntimeLaunchBlockReason(StrEnum):
    FEATURE_FLAG_DISABLED = "feature_flag_disabled"
    HUMAN_CONFIRMATION_REQUIRED = "human_confirmation_required"
    EXECUTOR_NOT_READY = "executor_not_ready"
    LAUNCH_PREVIEW_MISSING = "launch_preview_missing"
    WORKSPACE_NOT_BOUND = "workspace_not_bound"
    BUDGET_EXCEEDED = "budget_exceeded"
    CONCURRENCY_LIMIT_REACHED = "concurrency_limit_reached"
    SECRET_EXPOSURE_RISK = "secret_exposure_risk"
    ENV_DUMP_RISK = "env_dump_risk"
    PRODUCT_GIT_WRITE_FORBIDDEN = "product_git_write_forbidden"
    TIMEOUT_MISSING = "timeout_missing"
    CANCELLATION_MISSING = "cancellation_missing"
    AUDIT_EVENT_MISSING = "audit_event_missing"
    UNKNOWN = "unknown"


class RuntimeApprovalScope(StrEnum):
    EXECUTOR_LAUNCH = "executor_launch"


REQUIRED_RUNTIME_SAFETY_GATES: frozenset[RuntimeSafetyGateName] = frozenset(
    {
        RuntimeSafetyGateName.FEATURE_FLAG,
        RuntimeSafetyGateName.HUMAN_CONFIRMATION,
        RuntimeSafetyGateName.EXECUTOR_READINESS,
        RuntimeSafetyGateName.LAUNCH_PREVIEW,
        RuntimeSafetyGateName.WORKSPACE,
        RuntimeSafetyGateName.COST_BUDGET,
        RuntimeSafetyGateName.CONCURRENCY,
        RuntimeSafetyGateName.NO_SECRET_EXPOSURE,
        RuntimeSafetyGateName.NO_ENV_DUMP,
        RuntimeSafetyGateName.NO_PRODUCT_GIT_WRITE,
        RuntimeSafetyGateName.TIMEOUT,
        RuntimeSafetyGateName.CANCELLATION,
        RuntimeSafetyGateName.AUDIT_EVENT,
    },
)


_SECRET_TEXT_PATTERN = re.compile(
    r"(api\s*key|token|secret|password|bearer|sk-)",
    re.IGNORECASE,
)
_WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")


def _trim_optional_string(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _normalize_optional_datetime(value: datetime | None) -> datetime | None:
    return ensure_utc_datetime(value)


def _normalize_required_datetime(value: datetime) -> datetime:
    normalized = ensure_utc_datetime(value)
    if normalized is None:
        raise ValueError("datetime must not be None")
    return normalized


def _validate_no_sensitive_text(value: str | None) -> str | None:
    if value is not None and _SECRET_TEXT_PATTERN.search(value):
        raise ValueError("text must not contain suspected credential material")
    return value


def _dedupe_reasons(
    reasons: list[RuntimeLaunchBlockReason],
) -> list[RuntimeLaunchBlockReason]:
    normalized: list[RuntimeLaunchBlockReason] = []
    seen: set[RuntimeLaunchBlockReason] = set()
    for reason in reasons:
        if reason in seen:
            continue
        normalized.append(reason)
        seen.add(reason)
    return normalized


def _is_sensitive_workspace_hint(value: str) -> bool:
    return (
        value.startswith("/")
        or value.startswith("~")
        or value.startswith("\\\\")
        or _WINDOWS_DRIVE_PATH_PATTERN.match(value) is not None
    )


def _passed_gate(
    gate_name: RuntimeSafetyGateName,
    safe_summary: str | None = None,
) -> "RuntimeSafetyGateCheck":
    return RuntimeSafetyGateCheck(
        gate_name=gate_name,
        status=RuntimeSafetyGateStatus.PASSED,
        passed=True,
        safe_summary=safe_summary,
        checked_at=utc_now(),
    )


def _blocked_gate(
    gate_name: RuntimeSafetyGateName,
    block_reason: RuntimeLaunchBlockReason,
    safe_summary: str | None = None,
) -> "RuntimeSafetyGateCheck":
    return RuntimeSafetyGateCheck(
        gate_name=gate_name,
        status=RuntimeSafetyGateStatus.BLOCKED,
        passed=False,
        block_reason=block_reason,
        safe_summary=safe_summary,
        checked_at=utc_now(),
    )


class RuntimeSafetyGateCheck(DomainModel):
    gate_name: RuntimeSafetyGateName
    status: RuntimeSafetyGateStatus = RuntimeSafetyGateStatus.UNKNOWN
    passed: bool = False
    block_reason: RuntimeLaunchBlockReason | None = None
    safe_summary: str | None = None
    checked_at: datetime | None = None

    @field_validator("safe_summary", mode="before")
    @classmethod
    def trim_safe_summary(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("safe_summary")
    @classmethod
    def reject_sensitive_summary(cls, value: str | None) -> str | None:
        return _validate_no_sensitive_text(value)

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime | None) -> datetime | None:
        return _normalize_optional_datetime(value)

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "RuntimeSafetyGateCheck":
        if self.status == RuntimeSafetyGateStatus.PASSED:
            if self.passed is not True:
                raise ValueError("passed gate status requires passed=True")
            if self.block_reason is not None:
                raise ValueError("passed gate status must not include block_reason")
        if self.status == RuntimeSafetyGateStatus.BLOCKED:
            if self.passed is not False:
                raise ValueError("blocked gate status requires passed=False")
            if self.block_reason is None:
                raise ValueError("blocked gate status requires block_reason")
        return self


class RuntimeSafetyGateSnapshot(DomainModel):
    gate_checks: list[RuntimeSafetyGateCheck] = Field(default_factory=list)
    all_passed: bool = False
    blocking_reasons: list[RuntimeLaunchBlockReason] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @model_validator(mode="after")
    def validate_gate_snapshot(self) -> "RuntimeSafetyGateSnapshot":
        provided_gates = {check.gate_name for check in self.gate_checks}
        missing_gates = REQUIRED_RUNTIME_SAFETY_GATES.difference(provided_gates)
        if missing_gates:
            missing_names = ", ".join(sorted(gate.value for gate in missing_gates))
            raise ValueError(f"missing required runtime safety gates: {missing_names}")

        derived_all_passed = all(
            check.status == RuntimeSafetyGateStatus.PASSED for check in self.gate_checks
        )
        derived_blocking_reasons = _dedupe_reasons(
            [
                check.block_reason
                for check in self.gate_checks
                if check.status == RuntimeSafetyGateStatus.BLOCKED
                and check.block_reason is not None
            ],
        )
        object.__setattr__(self, "all_passed", derived_all_passed)
        object.__setattr__(self, "blocking_reasons", derived_blocking_reasons)

        if self.all_passed and self.blocking_reasons:
            raise ValueError("all_passed snapshots must not include blocking_reasons")
        if any(
            check.status == RuntimeSafetyGateStatus.BLOCKED for check in self.gate_checks
        ) and self.all_passed:
            raise ValueError("blocked gate snapshots must not be all_passed")
        return self

    def failed_gates(self) -> list[RuntimeSafetyGateCheck]:
        return [
            check
            for check in self.gate_checks
            if check.status == RuntimeSafetyGateStatus.BLOCKED
        ]

    def get_gate(
        self,
        name: RuntimeSafetyGateName,
    ) -> RuntimeSafetyGateCheck | None:
        return next((check for check in self.gate_checks if check.gate_name == name), None)


class RuntimeFeatureFlagPolicy(DomainModel):
    executor_runtime_enabled: bool = False
    real_executor_pilot_enabled: bool = False
    product_runtime_git_write_enabled: bool = False

    def gate_check(self) -> RuntimeSafetyGateCheck:
        if not self.executor_runtime_enabled:
            return _blocked_gate(
                RuntimeSafetyGateName.FEATURE_FLAG,
                RuntimeLaunchBlockReason.FEATURE_FLAG_DISABLED,
                "executor runtime feature flag disabled",
            )
        return _passed_gate(
            RuntimeSafetyGateName.FEATURE_FLAG,
            "executor runtime feature flag enabled",
        )


class RuntimeWorkspaceGateInput(DomainModel):
    workspace_id: str | None = None
    workspace_bound: bool = False
    workspace_path_hint: str | None = None
    repository_id: str | None = None
    worktree_id: str | None = None
    branch_name: str | None = None

    @field_validator(
        "workspace_id",
        "workspace_path_hint",
        "repository_id",
        "worktree_id",
        "branch_name",
        mode="before",
    )
    @classmethod
    def trim_workspace_strings(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("workspace_path_hint")
    @classmethod
    def sanitize_workspace_hint(cls, value: str | None) -> str | None:
        if value is not None and _is_sensitive_workspace_hint(value):
            return "workspace hint provided"
        return value

    def gate_check(self) -> RuntimeSafetyGateCheck:
        if not self.workspace_bound:
            return _blocked_gate(
                RuntimeSafetyGateName.WORKSPACE,
                RuntimeLaunchBlockReason.WORKSPACE_NOT_BOUND,
                "workspace is not bound",
            )
        return _passed_gate(RuntimeSafetyGateName.WORKSPACE, "workspace is bound")


class RuntimeBudgetGateInput(DomainModel):
    estimated_cost: Decimal | None = None
    session_budget_limit: Decimal | None = None
    daily_budget_remaining: Decimal | None = None
    currency: str | None = None

    @field_validator("estimated_cost", "session_budget_limit", "daily_budget_remaining")
    @classmethod
    def validate_non_negative_amount(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("amounts must be greater than or equal to 0")
        return value

    @field_validator("currency", mode="before")
    @classmethod
    def trim_currency(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    def gate_check(self) -> RuntimeSafetyGateCheck:
        if (
            self.estimated_cost is not None
            and self.session_budget_limit is not None
            and self.estimated_cost > self.session_budget_limit
        ):
            return _blocked_gate(
                RuntimeSafetyGateName.COST_BUDGET,
                RuntimeLaunchBlockReason.BUDGET_EXCEEDED,
                "estimated cost exceeds session budget",
            )
        if (
            self.estimated_cost is not None
            and self.daily_budget_remaining is not None
            and self.estimated_cost > self.daily_budget_remaining
        ):
            return _blocked_gate(
                RuntimeSafetyGateName.COST_BUDGET,
                RuntimeLaunchBlockReason.BUDGET_EXCEEDED,
                "estimated cost exceeds daily budget remaining",
            )
        return _passed_gate(RuntimeSafetyGateName.COST_BUDGET, "budget gate passed")


class RuntimeConcurrencyGateInput(DomainModel):
    active_session_count: int = 0
    max_concurrent_sessions: int = 1

    @field_validator("active_session_count")
    @classmethod
    def validate_active_session_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("active_session_count must be greater than or equal to 0")
        return value

    @field_validator("max_concurrent_sessions")
    @classmethod
    def validate_max_concurrent_sessions(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("max_concurrent_sessions must be a positive integer")
        return value

    def gate_check(self) -> RuntimeSafetyGateCheck:
        if self.active_session_count >= self.max_concurrent_sessions:
            return _blocked_gate(
                RuntimeSafetyGateName.CONCURRENCY,
                RuntimeLaunchBlockReason.CONCURRENCY_LIMIT_REACHED,
                "concurrency limit reached",
            )
        return _passed_gate(RuntimeSafetyGateName.CONCURRENCY, "concurrency gate passed")


class RuntimeSafetyEvaluationInput(DomainModel):
    feature_flags: RuntimeFeatureFlagPolicy = Field(
        default_factory=RuntimeFeatureFlagPolicy,
    )
    executor_ready: bool = False
    launch_preview_ready: bool = False
    workspace: RuntimeWorkspaceGateInput = Field(default_factory=RuntimeWorkspaceGateInput)
    budget: RuntimeBudgetGateInput = Field(default_factory=RuntimeBudgetGateInput)
    concurrency: RuntimeConcurrencyGateInput = Field(
        default_factory=RuntimeConcurrencyGateInput,
    )
    human_confirmed: bool = False
    timeout_configured: bool = False
    cancellation_supported: bool = False
    audit_event_ready: bool = False
    no_secret_exposure: bool = True
    no_env_dump: bool = True
    no_product_git_write: bool = True

    def evaluate(self) -> RuntimeSafetyGateSnapshot:
        gate_checks = [
            self.feature_flags.gate_check(),
            _passed_gate(
                RuntimeSafetyGateName.HUMAN_CONFIRMATION,
                "human confirmation provided",
            )
            if self.human_confirmed
            else _blocked_gate(
                RuntimeSafetyGateName.HUMAN_CONFIRMATION,
                RuntimeLaunchBlockReason.HUMAN_CONFIRMATION_REQUIRED,
                "human confirmation required",
            ),
            _passed_gate(
                RuntimeSafetyGateName.EXECUTOR_READINESS,
                "executor readiness provided",
            )
            if self.executor_ready
            else _blocked_gate(
                RuntimeSafetyGateName.EXECUTOR_READINESS,
                RuntimeLaunchBlockReason.EXECUTOR_NOT_READY,
                "executor is not ready",
            ),
            _passed_gate(RuntimeSafetyGateName.LAUNCH_PREVIEW, "launch preview ready")
            if self.launch_preview_ready
            else _blocked_gate(
                RuntimeSafetyGateName.LAUNCH_PREVIEW,
                RuntimeLaunchBlockReason.LAUNCH_PREVIEW_MISSING,
                "launch preview missing",
            ),
            self.workspace.gate_check(),
            self.budget.gate_check(),
            self.concurrency.gate_check(),
            _passed_gate(
                RuntimeSafetyGateName.NO_SECRET_EXPOSURE,
                "credential exposure guard passed",
            )
            if self.no_secret_exposure
            else _blocked_gate(
                RuntimeSafetyGateName.NO_SECRET_EXPOSURE,
                RuntimeLaunchBlockReason.SECRET_EXPOSURE_RISK,
                "credential exposure risk",
            ),
            _passed_gate(RuntimeSafetyGateName.NO_ENV_DUMP, "environment dump guard passed")
            if self.no_env_dump
            else _blocked_gate(
                RuntimeSafetyGateName.NO_ENV_DUMP,
                RuntimeLaunchBlockReason.ENV_DUMP_RISK,
                "environment dump risk",
            ),
            _passed_gate(
                RuntimeSafetyGateName.NO_PRODUCT_GIT_WRITE,
                "product runtime git write remains disabled",
            )
            if self.no_product_git_write
            else _blocked_gate(
                RuntimeSafetyGateName.NO_PRODUCT_GIT_WRITE,
                RuntimeLaunchBlockReason.PRODUCT_GIT_WRITE_FORBIDDEN,
                "product runtime git write forbidden",
            ),
            _passed_gate(RuntimeSafetyGateName.TIMEOUT, "timeout configured")
            if self.timeout_configured
            else _blocked_gate(
                RuntimeSafetyGateName.TIMEOUT,
                RuntimeLaunchBlockReason.TIMEOUT_MISSING,
                "timeout missing",
            ),
            _passed_gate(RuntimeSafetyGateName.CANCELLATION, "cancellation supported")
            if self.cancellation_supported
            else _blocked_gate(
                RuntimeSafetyGateName.CANCELLATION,
                RuntimeLaunchBlockReason.CANCELLATION_MISSING,
                "cancellation missing",
            ),
            _passed_gate(RuntimeSafetyGateName.AUDIT_EVENT, "audit event ready")
            if self.audit_event_ready
            else _blocked_gate(
                RuntimeSafetyGateName.AUDIT_EVENT,
                RuntimeLaunchBlockReason.AUDIT_EVENT_MISSING,
                "audit event missing",
            ),
        ]

        return RuntimeSafetyGateSnapshot(gate_checks=gate_checks)


class ExecutorLaunchRequest(DomainModel):
    request_id: str
    executor_id: str
    launch_preview_id: str
    project_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    requested_by: str | None = None
    status: RuntimeLaunchRequestStatus = RuntimeLaunchRequestStatus.DRAFT
    safety_snapshot: RuntimeSafetyGateSnapshot
    human_confirmation_required: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None
    approved_at: datetime | None = None
    consumed_at: datetime | None = None
    blocked_reasons: list[RuntimeLaunchBlockReason] = Field(default_factory=list)

    @field_validator("request_id", "executor_id", "launch_preview_id", mode="before")
    @classmethod
    def trim_required_request_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator(
        "project_id",
        "task_id",
        "run_id",
        "requested_by",
        mode="before",
    )
    @classmethod
    def trim_optional_request_strings(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("request_id", "executor_id", "launch_preview_id")
    @classmethod
    def require_request_strings(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @field_validator("expires_at", "approved_at", "consumed_at")
    @classmethod
    def normalize_optional_request_datetime(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        return _normalize_optional_datetime(value)

    @model_validator(mode="after")
    def validate_request_state(self) -> "ExecutorLaunchRequest":
        if self.status == RuntimeLaunchRequestStatus.APPROVED:
            if self.human_confirmation_required and self.approved_at is None:
                raise ValueError("approved launch requests require approved_at")
            if not self.safety_snapshot.all_passed:
                raise ValueError("launch request cannot be approved when safety gates failed")
        if self.expires_at is not None and self.expires_at < self.created_at:
            raise ValueError("expires_at must not be earlier than created_at")
        if self.approved_at is not None and self.approved_at < self.created_at:
            raise ValueError("approved_at must not be earlier than created_at")
        if (
            self.consumed_at is not None
            and self.approved_at is not None
            and self.consumed_at < self.approved_at
        ):
            raise ValueError("consumed_at must not be earlier than approved_at")
        merged_blocked_reasons = _dedupe_reasons(
            [*self.safety_snapshot.blocking_reasons, *self.blocked_reasons],
        )
        object.__setattr__(self, "blocked_reasons", merged_blocked_reasons)
        return self


class ExecutorLaunchApproval(DomainModel):
    approval_id: str
    request_id: str
    scope: RuntimeApprovalScope = RuntimeApprovalScope.EXECUTOR_LAUNCH
    decision: RuntimeApprovalDecision = RuntimeApprovalDecision.PENDING
    decided_by: str | None = None
    decided_at: datetime | None = None
    confirmation_text: str | None = None
    safe_summary: str | None = None

    @field_validator("approval_id", "request_id", mode="before")
    @classmethod
    def trim_required_approval_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("decided_by", "confirmation_text", "safe_summary", mode="before")
    @classmethod
    def trim_optional_approval_strings(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("approval_id", "request_id")
    @classmethod
    def require_approval_strings(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("confirmation_text", "safe_summary")
    @classmethod
    def reject_sensitive_approval_text(cls, value: str | None) -> str | None:
        return _validate_no_sensitive_text(value)

    @field_validator("decided_at")
    @classmethod
    def normalize_decided_at(cls, value: datetime | None) -> datetime | None:
        return _normalize_optional_datetime(value)

    @model_validator(mode="after")
    def validate_decision_fields(self) -> "ExecutorLaunchApproval":
        if self.decision in {
            RuntimeApprovalDecision.APPROVED,
            RuntimeApprovalDecision.REJECTED,
            RuntimeApprovalDecision.CANCELLED,
        }:
            if not self.decided_by:
                raise ValueError("decided_by is required for final approval decisions")
            if self.decided_at is None:
                raise ValueError("decided_at is required for final approval decisions")
        return self
