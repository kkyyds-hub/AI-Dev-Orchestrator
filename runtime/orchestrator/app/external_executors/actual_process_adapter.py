"""Guarded real executor process adapter skeleton for P9-REL-Pilot-A.

The adapter implements the lifecycle protocol without starting native tools.
It keeps a process-free in-memory session record so callers can read back why a
launch is blocked or where a future launch would wait after all gates pass.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.external_executors.actual_contract import (
    RealExecutorLaunchContext,
    RealExecutorLifecycleIntent,
    RealExecutorOperationResult,
    RealExecutorOperationStatus,
    RealExecutorPollSnapshot,
    RealExecutorPollState,
)
from app.external_executors.actual_preflight import RealExecutorPreflightService


PROCESS_ADAPTER_GATE_REASON = "real_executor_process_adapter_guarded"
_SESSION_NOT_FOUND_REASON = "session_not_found"
_SUPPORTED_EXECUTOR_LABELS = frozenset({"codex", "claude code", "claude-code"})
_SENSITIVE_TEXT_PATTERN = re.compile(
    r"(api\s*key|token|secret|bearer|sk-)",
    re.IGNORECASE,
)
_SAFE_SESSION_TEXT_PATTERN = re.compile(r"[^a-zA-Z0-9_.-]+")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim_required_string(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _trim_optional_string(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _reject_sensitive_text(value: str | None) -> str | None:
    if value is not None and _SENSITIVE_TEXT_PATTERN.search(value):
        raise ValueError("process adapter text must not contain suspected credential material")
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


def _normalize_label(value: str) -> str:
    return value.strip().lower()


def _session_id_for(request_id: str) -> str:
    request_marker = "redacted"
    if not _SENSITIVE_TEXT_PATTERN.search(request_id):
        request_marker = _SAFE_SESSION_TEXT_PATTERN.sub("-", request_id.strip()).strip("-")
    return f"real-executor-session-{request_marker or 'redacted'}"


class _ProcessAdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealExecutorProcessSession(_ProcessAdapterModel):
    session_id: str
    executor_label: str
    command_summary: str | None = None
    workspace_hint: str | None = None
    poll_state: RealExecutorPollState = RealExecutorPollState.LAUNCH_PENDING
    audit_event_count: int = 1
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @field_validator("session_id", "executor_label", mode="before")
    @classmethod
    def trim_required_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("command_summary", "workspace_hint", mode="before")
    @classmethod
    def trim_optional_strings(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("session_id", "executor_label")
    @classmethod
    def validate_required_safe_text(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return _reject_sensitive_text(value) or value

    @field_validator("command_summary", "workspace_hint")
    @classmethod
    def validate_optional_safe_text(cls, value: str | None) -> str | None:
        return _reject_sensitive_text(value)

    @field_validator("audit_event_count")
    @classmethod
    def validate_audit_event_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("audit_event_count must be greater than or equal to 0")
        return value


class RealExecutorProcessAdapter:
    def __init__(
        self,
        preflight_service: RealExecutorPreflightService | None = None,
    ) -> None:
        self._preflight_service = preflight_service or RealExecutorPreflightService()
        self._sessions: dict[str, RealExecutorProcessSession] = {}

    def launch(self, context: RealExecutorLaunchContext) -> RealExecutorOperationResult:
        preflight = self._preflight_service.evaluate_launch(context)
        label_reason = self._executor_label_block_reason(context.executor_label)
        blocking_reasons = [PROCESS_ADAPTER_GATE_REASON]
        blocking_reasons.extend(preflight.blocking_reasons)
        if label_reason is not None:
            blocking_reasons.append(label_reason)

        if blocking_reasons != [PROCESS_ADAPTER_GATE_REASON]:
            return RealExecutorOperationResult(
                lifecycle_intent=RealExecutorLifecycleIntent.LAUNCH,
                status=RealExecutorOperationStatus.BLOCKED,
                message="Real executor launch is blocked by controlled safety gates",
                blocking_reasons=_dedupe_trimmed_strings(blocking_reasons),
                audit_event_count=1,
                product_runtime_git_write_allowed=False,
            )

        session = RealExecutorProcessSession(
            session_id=_session_id_for(context.request_id),
            executor_label=context.executor_label,
            command_summary=context.command_summary,
            workspace_hint=context.workspace_hint,
            poll_state=RealExecutorPollState.LAUNCH_PENDING,
            audit_event_count=1,
        )
        self._sessions[session.session_id] = session
        return RealExecutorOperationResult(
            lifecycle_intent=RealExecutorLifecycleIntent.LAUNCH,
            status=RealExecutorOperationStatus.ACCEPTED,
            session_id=session.session_id,
            message="Real executor launch accepted as a noop launch_pending skeleton",
            blocking_reasons=[],
            audit_event_count=session.audit_event_count,
            product_runtime_git_write_allowed=False,
        )

    def poll(self, session_id: str) -> RealExecutorPollSnapshot:
        session = self._sessions.get(session_id.strip())
        if session is None:
            return RealExecutorPollSnapshot(
                session_id=session_id,
                poll_state=RealExecutorPollState.UNKNOWN,
                message="Real executor session was not found",
                blocking_reasons=[_SESSION_NOT_FOUND_REASON],
                audit_event_count=1,
                product_runtime_git_write_allowed=False,
            )

        return RealExecutorPollSnapshot(
            session_id=session.session_id,
            poll_state=session.poll_state,
            executor_label=session.executor_label,
            command_summary=session.command_summary,
            workspace_hint=session.workspace_hint,
            message="Real executor session readback only",
            blocking_reasons=[],
            audit_event_count=session.audit_event_count,
            product_runtime_git_write_allowed=False,
        )

    def cancel(self, session_id: str, reason: str) -> RealExecutorOperationResult:
        return self._transition_session(
            session_id,
            lifecycle_intent=RealExecutorLifecycleIntent.CANCEL,
            poll_state=RealExecutorPollState.CANCELLED,
            message="Real executor session cancelled before native execution",
        )

    def kill(self, session_id: str, reason: str) -> RealExecutorOperationResult:
        return self._transition_session(
            session_id,
            lifecycle_intent=RealExecutorLifecycleIntent.KILL,
            poll_state=RealExecutorPollState.KILLED,
            message="Real executor session killed before native execution",
        )

    def cleanup(self, session_id: str) -> RealExecutorOperationResult:
        return self._transition_session(
            session_id,
            lifecycle_intent=RealExecutorLifecycleIntent.CLEANUP,
            poll_state=RealExecutorPollState.CLEANED_UP,
            message="Real executor session cleanup completed for noop skeleton",
        )

    def _transition_session(
        self,
        session_id: str,
        *,
        lifecycle_intent: RealExecutorLifecycleIntent,
        poll_state: RealExecutorPollState,
        message: str,
    ) -> RealExecutorOperationResult:
        session = self._sessions.get(session_id.strip())
        if session is None:
            return RealExecutorOperationResult(
                lifecycle_intent=lifecycle_intent,
                status=RealExecutorOperationStatus.NOT_FOUND,
                session_id=session_id,
                message="Real executor session was not found",
                blocking_reasons=[_SESSION_NOT_FOUND_REASON],
                audit_event_count=1,
                product_runtime_git_write_allowed=False,
            )

        updated = session.model_copy(
            update={
                "poll_state": poll_state,
                "audit_event_count": session.audit_event_count + 1,
                "updated_at": _utc_now(),
            },
        )
        self._sessions[updated.session_id] = updated
        return RealExecutorOperationResult(
            lifecycle_intent=lifecycle_intent,
            status=RealExecutorOperationStatus.COMPLETED,
            session_id=updated.session_id,
            message=message,
            blocking_reasons=[],
            audit_event_count=updated.audit_event_count,
            product_runtime_git_write_allowed=False,
        )

    def _executor_label_block_reason(self, executor_label: str) -> str | None:
        if _normalize_label(executor_label) in _SUPPORTED_EXECUTOR_LABELS:
            return None
        return "executor_label_not_supported"


__all__ = (
    "PROCESS_ADAPTER_GATE_REASON",
    "RealExecutorProcessAdapter",
    "RealExecutorProcessSession",
)
