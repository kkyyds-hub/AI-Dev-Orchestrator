"""Pure contract for future real executor adapters.

This module freezes the P9-REL-B adapter boundary only. It does not implement
an adapter, start a process, read native executor output, inspect environment
variables, or perform product runtime Git writes.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SENSITIVE_TEXT_PATTERN = re.compile(
    r"(api\s*key|token|secret|password|bearer|sk-)",
    re.IGNORECASE,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim_optional_string(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _reject_sensitive_text(value: str | None) -> str | None:
    if value is not None and _SENSITIVE_TEXT_PATTERN.search(value):
        raise ValueError("safe summary text must not contain suspected credential material")
    return value


def _dedupe_trimmed_strings(value: list[str]) -> list[str]:
    normalized_items: list[str] = []
    seen_items: set[str] = set()
    for item in value:
        normalized_item = item.strip()
        if not normalized_item or normalized_item in seen_items:
            continue
        normalized_items.append(normalized_item)
        seen_items.add(normalized_item)
    return normalized_items


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorCapability(StrEnum):
    LAUNCH = "launch"
    POLL = "poll"
    CANCEL = "cancel"
    KILL = "kill"
    CLEANUP = "cleanup"
    TIMEOUT = "timeout"
    APPEND_ONLY_AUDIT = "append_only_audit"
    BLOCK_CREDENTIAL_EXPOSURE = "block_credential_exposure"
    BLOCK_ENVIRONMENT_DUMP = "block_environment_dump"
    BLOCK_PRODUCT_RUNTIME_GIT_WRITE = "block_product_runtime_git_write"


class RealExecutorLifecycleIntent(StrEnum):
    LAUNCH = "launch"
    POLL = "poll"
    CANCEL = "cancel"
    KILL = "kill"
    CLEANUP = "cleanup"


class RealExecutorOperationStatus(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    NOT_FOUND = "not_found"
    FAILED = "failed"
    COMPLETED = "completed"


class RealExecutorPollState(StrEnum):
    UNKNOWN = "unknown"
    LAUNCH_PENDING = "launch_pending"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    IDLE = "idle"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    KILLED = "killed"
    CLEANUP_REQUIRED = "cleanup_required"
    CLEANED_UP = "cleaned_up"


class RealExecutorSafetyBoundary(_ContractModel):
    feature_flag_enabled: bool = False
    human_confirmation_present: bool = False
    executor_readiness_available: bool = False
    workspace_worktree_gate_passed: bool = False
    budget_cost_gate_passed: bool = False
    concurrency_gate_passed: bool = False
    timeout_supported: bool = False
    cancel_supported: bool = False
    kill_supported: bool = False
    audit_events_append_only: bool = True
    credential_exposure_blocked: bool = True
    environment_dump_blocked: bool = True
    product_runtime_git_write_allowed: bool = False

    @field_validator("product_runtime_git_write_allowed")
    @classmethod
    def prevent_product_runtime_git_write(cls, value: bool) -> bool:
        if value is True:
            raise ValueError("product runtime Git write is outside the P9-REL-B contract")
        return value

    def blocking_reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if not self.feature_flag_enabled:
            reasons.append("feature_flag_disabled")
        if not self.human_confirmation_present:
            reasons.append("human_confirmation_missing")
        if not self.executor_readiness_available:
            reasons.append("executor_readiness_missing")
        if not self.workspace_worktree_gate_passed:
            reasons.append("workspace_worktree_gate_failed")
        if not self.budget_cost_gate_passed:
            reasons.append("budget_cost_gate_failed")
        if not self.concurrency_gate_passed:
            reasons.append("concurrency_gate_failed")
        if not self.timeout_supported:
            reasons.append("timeout_not_supported")
        if not self.cancel_supported:
            reasons.append("cancel_not_supported")
        if not self.kill_supported:
            reasons.append("kill_not_supported")
        if not self.audit_events_append_only:
            reasons.append("audit_events_not_append_only")
        if not self.credential_exposure_blocked:
            reasons.append("credential_exposure_not_blocked")
        if not self.environment_dump_blocked:
            reasons.append("environment_dump_not_blocked")
        if self.product_runtime_git_write_allowed:
            reasons.append("product_runtime_git_write_not_allowed")
        return tuple(reasons)

    def is_launchable(self) -> bool:
        return len(self.blocking_reasons()) == 0


class RealExecutorLaunchContext(_ContractModel):
    request_id: str
    executor_label: str
    command_summary: str | None = None
    workspace_hint: str | None = None
    lifecycle_intent: RealExecutorLifecycleIntent = RealExecutorLifecycleIntent.LAUNCH
    safety_boundary: RealExecutorSafetyBoundary = Field(
        default_factory=RealExecutorSafetyBoundary,
    )
    requested_at: datetime = Field(default_factory=_utc_now)

    @field_validator("request_id", "executor_label", mode="before")
    @classmethod
    def trim_required_context_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("command_summary", "workspace_hint", mode="before")
    @classmethod
    def trim_optional_context_strings(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("request_id", "executor_label")
    @classmethod
    def require_context_strings(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("executor_label", "command_summary", "workspace_hint")
    @classmethod
    def validate_safe_context_text(cls, value: str | None) -> str | None:
        return _reject_sensitive_text(value)

    @model_validator(mode="after")
    def validate_launch_intent(self) -> "RealExecutorLaunchContext":
        if self.lifecycle_intent != RealExecutorLifecycleIntent.LAUNCH:
            raise ValueError("launch context lifecycle_intent must be launch")
        return self

    def operation_status(self) -> RealExecutorOperationStatus:
        if self.safety_boundary.is_launchable():
            return RealExecutorOperationStatus.ACCEPTED
        return RealExecutorOperationStatus.BLOCKED


class RealExecutorOperationResult(_ContractModel):
    lifecycle_intent: RealExecutorLifecycleIntent
    status: RealExecutorOperationStatus
    session_id: str | None = None
    message: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    audit_event_count: int = 0
    product_runtime_git_write_allowed: bool = False
    recorded_at: datetime = Field(default_factory=_utc_now)

    @field_validator("session_id", "message", mode="before")
    @classmethod
    def trim_optional_result_strings(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("message")
    @classmethod
    def validate_safe_result_text(cls, value: str | None) -> str | None:
        return _reject_sensitive_text(value)

    @field_validator("blocking_reasons", mode="before")
    @classmethod
    def default_blocking_reasons(cls, value: Any) -> Any:
        if value is None:
            return []
        return value

    @field_validator("blocking_reasons")
    @classmethod
    def normalize_blocking_reasons(cls, value: list[str]) -> list[str]:
        return _dedupe_trimmed_strings(value)

    @field_validator("audit_event_count")
    @classmethod
    def validate_audit_event_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("audit_event_count must be greater than or equal to 0")
        return value

    @field_validator("product_runtime_git_write_allowed")
    @classmethod
    def prevent_product_runtime_git_write(cls, value: bool) -> bool:
        if value is True:
            raise ValueError("product runtime Git write is outside the P9-REL-B contract")
        return value


class RealExecutorPollSnapshot(_ContractModel):
    session_id: str
    lifecycle_intent: RealExecutorLifecycleIntent = RealExecutorLifecycleIntent.POLL
    poll_state: RealExecutorPollState = RealExecutorPollState.UNKNOWN
    executor_label: str | None = None
    command_summary: str | None = None
    workspace_hint: str | None = None
    message: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    audit_event_count: int = 0
    product_runtime_git_write_allowed: bool = False
    observed_at: datetime = Field(default_factory=_utc_now)

    @field_validator("session_id", mode="before")
    @classmethod
    def trim_required_poll_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("executor_label", "command_summary", "workspace_hint", "message", mode="before")
    @classmethod
    def trim_optional_poll_strings(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("session_id")
    @classmethod
    def require_session_id(cls, value: str) -> str:
        if not value:
            raise ValueError("session_id must not be empty")
        return value

    @field_validator("executor_label", "command_summary", "workspace_hint", "message")
    @classmethod
    def validate_safe_poll_text(cls, value: str | None) -> str | None:
        return _reject_sensitive_text(value)

    @field_validator("blocking_reasons", mode="before")
    @classmethod
    def default_poll_blocking_reasons(cls, value: Any) -> Any:
        if value is None:
            return []
        return value

    @field_validator("blocking_reasons")
    @classmethod
    def normalize_poll_blocking_reasons(cls, value: list[str]) -> list[str]:
        return _dedupe_trimmed_strings(value)

    @field_validator("audit_event_count")
    @classmethod
    def validate_poll_audit_event_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("audit_event_count must be greater than or equal to 0")
        return value

    @field_validator("product_runtime_git_write_allowed")
    @classmethod
    def prevent_product_runtime_git_write(cls, value: bool) -> bool:
        if value is True:
            raise ValueError("product runtime Git write is outside the P9-REL-B contract")
        return value

    @model_validator(mode="after")
    def validate_poll_intent(self) -> "RealExecutorPollSnapshot":
        if self.lifecycle_intent != RealExecutorLifecycleIntent.POLL:
            raise ValueError("poll snapshot lifecycle_intent must be poll")
        return self


@runtime_checkable
class RealExecutorAdapterProtocol(Protocol):
    def launch(self, context: RealExecutorLaunchContext) -> RealExecutorOperationResult: ...

    def poll(self, session_id: str) -> RealExecutorPollSnapshot: ...

    def cancel(self, session_id: str, reason: str) -> RealExecutorOperationResult: ...

    def kill(self, session_id: str, reason: str) -> RealExecutorOperationResult: ...

    def cleanup(self, session_id: str) -> RealExecutorOperationResult: ...


__all__ = (
    "RealExecutorAdapterProtocol",
    "RealExecutorCapability",
    "RealExecutorLaunchContext",
    "RealExecutorLifecycleIntent",
    "RealExecutorOperationResult",
    "RealExecutorOperationStatus",
    "RealExecutorPollSnapshot",
    "RealExecutorPollState",
    "RealExecutorSafetyBoundary",
)
