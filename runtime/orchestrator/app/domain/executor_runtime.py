"""Pure domain contracts for P9 controlled executor runtime sessions.

This module freezes P9-B runtime data shapes only. It does not read local
configuration, inspect environment variables, launch external processes, or
create real executor sessions.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


class ExecutorRuntimeState(StrEnum):
    PENDING = "pending"
    LAUNCH_REQUESTED = "launch_requested"
    AWAITING_HUMAN_CONFIRMATION = "awaiting_human_confirmation"
    LAUNCH_APPROVED = "launch_approved"
    LAUNCHING = "launching"
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


class ExecutorRuntimeEventType(StrEnum):
    SESSION_CREATED = "session.created"
    SESSION_LAUNCH_REQUESTED = "session.launch_requested"
    SESSION_AWAITING_HUMAN_CONFIRMATION = "session.awaiting_human_confirmation"
    SESSION_LAUNCH_APPROVED = "session.launch_approved"
    SESSION_LAUNCHING = "session.launching"
    SESSION_RUNNING = "session.running"
    SESSION_WAITING_INPUT = "session.waiting_input"
    SESSION_IDLE = "session.idle"
    SESSION_BLOCKED = "session.blocked"
    SESSION_COMPLETED = "session.completed"
    SESSION_FAILED = "session.failed"
    SESSION_CANCELLED = "session.cancelled"
    SESSION_TIMED_OUT = "session.timed_out"
    SESSION_KILLED = "session.killed"
    SESSION_CLEANUP_REQUIRED = "session.cleanup_required"
    SESSION_CLEANED_UP = "session.cleaned_up"
    SESSION_SAFETY_GATE_BLOCKED = "session.safety_gate_blocked"
    SESSION_COST_BUDGET_BLOCKED = "session.cost_budget_blocked"
    SESSION_WORKSPACE_GATE_BLOCKED = "session.workspace_gate_blocked"
    SESSION_HUMAN_INPUT_REQUIRED = "session.human_input_required"
    SESSION_AUDIT_NOTE = "session.audit_note"


class ExecutorRuntimeExitReason(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED_BY_USER = "cancelled_by_user"
    TIMEOUT = "timeout"
    KILLED_BY_USER = "killed_by_user"
    SAFETY_GATE_BLOCKED = "safety_gate_blocked"
    WORKSPACE_GATE_BLOCKED = "workspace_gate_blocked"
    BUDGET_GATE_BLOCKED = "budget_gate_blocked"
    UNKNOWN = "unknown"


class ExecutorRuntimeSource(StrEnum):
    FAKE_ADAPTER = "fake_adapter"
    DRY_RUN = "dry_run"
    REAL_EXECUTOR_PILOT = "real_executor_pilot"
    UNKNOWN = "unknown"


TERMINAL_RUNTIME_STATES: frozenset[ExecutorRuntimeState] = frozenset(
    {
        ExecutorRuntimeState.COMPLETED,
        ExecutorRuntimeState.FAILED,
        ExecutorRuntimeState.CANCELLED,
        ExecutorRuntimeState.TIMED_OUT,
        ExecutorRuntimeState.KILLED,
        ExecutorRuntimeState.CLEANED_UP,
    },
)

UNCLEAN_TERMINAL_RUNTIME_STATES: frozenset[ExecutorRuntimeState] = frozenset(
    {
        ExecutorRuntimeState.COMPLETED,
        ExecutorRuntimeState.FAILED,
        ExecutorRuntimeState.CANCELLED,
        ExecutorRuntimeState.TIMED_OUT,
        ExecutorRuntimeState.KILLED,
    },
)

RUNTIME_STATE_TRANSITIONS: dict[ExecutorRuntimeState, frozenset[ExecutorRuntimeState]] = {
    ExecutorRuntimeState.PENDING: frozenset(
        {
            ExecutorRuntimeState.LAUNCH_REQUESTED,
            ExecutorRuntimeState.CANCELLED,
        },
    ),
    ExecutorRuntimeState.LAUNCH_REQUESTED: frozenset(
        {
            ExecutorRuntimeState.AWAITING_HUMAN_CONFIRMATION,
            ExecutorRuntimeState.LAUNCH_APPROVED,
            ExecutorRuntimeState.BLOCKED,
            ExecutorRuntimeState.CANCELLED,
        },
    ),
    ExecutorRuntimeState.AWAITING_HUMAN_CONFIRMATION: frozenset(
        {
            ExecutorRuntimeState.LAUNCH_APPROVED,
            ExecutorRuntimeState.CANCELLED,
        },
    ),
    ExecutorRuntimeState.LAUNCH_APPROVED: frozenset(
        {
            ExecutorRuntimeState.LAUNCHING,
            ExecutorRuntimeState.CANCELLED,
        },
    ),
    ExecutorRuntimeState.LAUNCHING: frozenset(
        {
            ExecutorRuntimeState.RUNNING,
            ExecutorRuntimeState.FAILED,
            ExecutorRuntimeState.TIMED_OUT,
            ExecutorRuntimeState.CANCELLED,
        },
    ),
    ExecutorRuntimeState.RUNNING: frozenset(
        {
            ExecutorRuntimeState.IDLE,
            ExecutorRuntimeState.WAITING_INPUT,
            ExecutorRuntimeState.COMPLETED,
            ExecutorRuntimeState.FAILED,
            ExecutorRuntimeState.TIMED_OUT,
            ExecutorRuntimeState.CANCELLED,
            ExecutorRuntimeState.KILLED,
        },
    ),
    ExecutorRuntimeState.WAITING_INPUT: frozenset(
        {
            ExecutorRuntimeState.RUNNING,
            ExecutorRuntimeState.CANCELLED,
            ExecutorRuntimeState.TIMED_OUT,
        },
    ),
    ExecutorRuntimeState.IDLE: frozenset(
        {
            ExecutorRuntimeState.RUNNING,
            ExecutorRuntimeState.COMPLETED,
            ExecutorRuntimeState.CANCELLED,
            ExecutorRuntimeState.TIMED_OUT,
        },
    ),
    ExecutorRuntimeState.BLOCKED: frozenset(
        {
            ExecutorRuntimeState.CANCELLED,
            ExecutorRuntimeState.CLEANUP_REQUIRED,
        },
    ),
    ExecutorRuntimeState.COMPLETED: frozenset(
        {
            ExecutorRuntimeState.CLEANUP_REQUIRED,
            ExecutorRuntimeState.CLEANED_UP,
        },
    ),
    ExecutorRuntimeState.FAILED: frozenset(
        {
            ExecutorRuntimeState.CLEANUP_REQUIRED,
            ExecutorRuntimeState.CLEANED_UP,
        },
    ),
    ExecutorRuntimeState.CANCELLED: frozenset(
        {
            ExecutorRuntimeState.CLEANUP_REQUIRED,
            ExecutorRuntimeState.CLEANED_UP,
        },
    ),
    ExecutorRuntimeState.TIMED_OUT: frozenset(
        {
            ExecutorRuntimeState.CLEANUP_REQUIRED,
            ExecutorRuntimeState.CLEANED_UP,
        },
    ),
    ExecutorRuntimeState.KILLED: frozenset(
        {
            ExecutorRuntimeState.CLEANUP_REQUIRED,
            ExecutorRuntimeState.CLEANED_UP,
        },
    ),
    ExecutorRuntimeState.CLEANUP_REQUIRED: frozenset({ExecutorRuntimeState.CLEANED_UP}),
    ExecutorRuntimeState.CLEANED_UP: frozenset(),
}


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


def _validate_no_secret_text(value: str | None) -> str | None:
    if value is not None and _SECRET_TEXT_PATTERN.search(value):
        raise ValueError("text must not contain suspected secret material")
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


def _is_sensitive_path_hint(value: str) -> bool:
    return (
        value.startswith("/")
        or value.startswith("~")
        or value.startswith("\\\\")
        or _WINDOWS_DRIVE_PATH_PATTERN.match(value) is not None
    )


class ExecutorRuntimeProcessSnapshot(DomainModel):
    process_id: int | None = None
    exit_code: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_activity_at: datetime | None = None
    heartbeat_at: datetime | None = None

    @field_validator("process_id")
    @classmethod
    def validate_process_id(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("process_id must be a positive integer when provided")
        return value

    @field_validator(
        "started_at",
        "finished_at",
        "last_activity_at",
        "heartbeat_at",
    )
    @classmethod
    def normalize_process_datetime(cls, value: datetime | None) -> datetime | None:
        return _normalize_optional_datetime(value)

    @model_validator(mode="after")
    def validate_process_timestamps(self) -> "ExecutorRuntimeProcessSnapshot":
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("finished_at must not be earlier than started_at")
        return self


class ExecutorRuntimeUsageSnapshot(DomainModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: Decimal | None = None
    cost_currency: str | None = None

    @field_validator("prompt_tokens", "completion_tokens", "total_tokens")
    @classmethod
    def validate_non_negative_tokens(cls, value: int) -> int:
        if value < 0:
            raise ValueError("token counts must be greater than or equal to 0")
        return value

    @field_validator("estimated_cost")
    @classmethod
    def validate_estimated_cost(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("estimated_cost must be greater than or equal to 0")
        return value

    @field_validator("cost_currency", mode="before")
    @classmethod
    def trim_cost_currency(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @model_validator(mode="after")
    def validate_total_tokens(self) -> "ExecutorRuntimeUsageSnapshot":
        minimum_total = self.prompt_tokens + self.completion_tokens
        if self.total_tokens < minimum_total:
            raise ValueError("total_tokens must not be less than prompt + completion tokens")
        return self


class ExecutorRuntimeWorkspaceBinding(DomainModel):
    workspace_id: str | None = None
    workspace_path_hint: str | None = None
    repository_id: str | None = None
    branch_name: str | None = None
    worktree_id: str | None = None
    workspace_bound: bool = False

    @field_validator(
        "workspace_id",
        "workspace_path_hint",
        "repository_id",
        "branch_name",
        "worktree_id",
        mode="before",
    )
    @classmethod
    def trim_workspace_strings(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("workspace_path_hint")
    @classmethod
    def sanitize_workspace_path_hint(cls, value: str | None) -> str | None:
        if value is not None and _is_sensitive_path_hint(value):
            return "workspace hint provided"
        return value


class ExecutorRuntimeSession(DomainModel):
    session_id: str
    executor_id: str
    launch_preview_id: str | None = None
    project_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    state: ExecutorRuntimeState = ExecutorRuntimeState.PENDING
    source: ExecutorRuntimeSource = ExecutorRuntimeSource.FAKE_ADAPTER
    workspace: ExecutorRuntimeWorkspaceBinding = Field(
        default_factory=ExecutorRuntimeWorkspaceBinding,
    )
    process: ExecutorRuntimeProcessSnapshot = Field(
        default_factory=ExecutorRuntimeProcessSnapshot,
    )
    usage: ExecutorRuntimeUsageSnapshot = Field(
        default_factory=ExecutorRuntimeUsageSnapshot,
    )
    exit_reason: ExecutorRuntimeExitReason | None = None
    result_summary: str | None = None
    error_summary: str | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @field_validator("session_id", "executor_id", mode="before")
    @classmethod
    def trim_required_session_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator(
        "launch_preview_id",
        "project_id",
        "task_id",
        "run_id",
        "result_summary",
        "error_summary",
        "created_by",
        mode="before",
    )
    @classmethod
    def trim_optional_session_strings(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("session_id", "executor_id")
    @classmethod
    def require_non_empty_session_strings(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("result_summary", "error_summary")
    @classmethod
    def reject_secret_summaries(cls, value: str | None) -> str | None:
        return _validate_no_secret_text(value)

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

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_required_session_datetime(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)

    @field_validator("started_at", "finished_at")
    @classmethod
    def normalize_optional_session_datetime(cls, value: datetime | None) -> datetime | None:
        return _normalize_optional_datetime(value)

    @model_validator(mode="after")
    def validate_session_timestamps(self) -> "ExecutorRuntimeSession":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be earlier than created_at")
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("finished_at must not be earlier than started_at")
        if self.state in {
            ExecutorRuntimeState.RUNNING,
            ExecutorRuntimeState.LAUNCHING,
        } and self.finished_at is not None:
            raise ValueError("running or launching sessions must not have finished_at")
        return self

    def is_terminal(self) -> bool:
        return self.state in TERMINAL_RUNTIME_STATES

    def requires_cleanup(self) -> bool:
        return (
            self.state == ExecutorRuntimeState.CLEANUP_REQUIRED
            or self.state in UNCLEAN_TERMINAL_RUNTIME_STATES
        )

    def can_transition_to(self, next_state: ExecutorRuntimeState) -> bool:
        return next_state in RUNTIME_STATE_TRANSITIONS[self.state]


class RuntimeEventPayload(DomainModel):
    message: str | None = None
    reason_code: str | None = None
    state: ExecutorRuntimeState | None = None
    metadata_count: int = 0

    @field_validator("message", "reason_code", mode="before")
    @classmethod
    def trim_payload_strings(cls, value: Any) -> Any:
        return _trim_optional_string(value)

    @field_validator("message")
    @classmethod
    def reject_secret_message(cls, value: str | None) -> str | None:
        return _validate_no_secret_text(value)

    @field_validator("metadata_count")
    @classmethod
    def validate_metadata_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("metadata_count must be greater than or equal to 0")
        return value


class RuntimeEvent(DomainModel):
    event_id: str
    session_id: str
    event_type: ExecutorRuntimeEventType
    timestamp: datetime = Field(default_factory=utc_now)
    payload: RuntimeEventPayload = Field(default_factory=RuntimeEventPayload)
    append_only: bool = True

    @field_validator("event_id", "session_id", mode="before")
    @classmethod
    def trim_event_required_strings(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("event_id", "session_id")
    @classmethod
    def require_event_required_strings(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("timestamp")
    @classmethod
    def normalize_event_timestamp(cls, value: datetime) -> datetime:
        return _normalize_required_datetime(value)


class RuntimeEventStreamSnapshot(DomainModel):
    session_id: str
    events: list[RuntimeEvent] = Field(default_factory=list)
    total: int | None = None

    @field_validator("session_id", mode="before")
    @classmethod
    def trim_stream_session_id(cls, value: Any) -> Any:
        return _trim_required_string(value)

    @field_validator("session_id")
    @classmethod
    def require_stream_session_id(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_event_stream(self) -> "RuntimeEventStreamSnapshot":
        if self.total is None:
            self.total = len(self.events)
        if self.total != len(self.events):
            raise ValueError("total must equal the number of events")

        previous_timestamp: datetime | None = None
        for event in self.events:
            if event.session_id != self.session_id:
                raise ValueError("all events must belong to the stream session_id")
            if previous_timestamp is not None and event.timestamp < previous_timestamp:
                raise ValueError("events must be sorted by non-decreasing timestamp")
            previous_timestamp = event.timestamp

        return self

    def latest_event(self) -> RuntimeEvent | None:
        if not self.events:
            return None
        return self.events[-1]
