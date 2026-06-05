"""Runtime lifecycle event schema and pure builders for P3-D2.

This module is deliberately side-effect free.  It does not import repositories,
write AgentMessage rows, call worker runtime adapters, launch fake/real
runtimes, probe processes, kill runtimes, run commands, or touch git.  It only
normalizes runtime lifecycle evidence into the JSON contract designed in P3-D.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


RUNTIME_EVENT_SCHEMA_VERSION = "1.0"
RUNTIME_EVENT_CONTENT_DETAIL_MAX_LENGTH = 4_000


class RuntimeEventType(StrEnum):
    """P3-D runtime lifecycle event types."""

    LAUNCH_GATE_EVALUATED = "runtime_launch_gate_evaluated"
    LAUNCH_GATE_BLOCKED = "runtime_launch_gate_blocked"
    LAUNCH_REQUESTED = "runtime_launch_requested"
    SPAWNING = "runtime_spawning"
    HANDLE_BOUND = "runtime_handle_bound"
    ALIVE_OBSERVED = "runtime_alive_observed"
    EXITED = "runtime_exited"
    MISSING = "runtime_missing"
    PROBE_FAILED = "runtime_probe_failed"
    KILL_REQUESTED = "runtime_kill_requested"
    KILLED = "runtime_killed"
    CLEANUP_STARTED = "runtime_cleanup_started"
    CLEANUP_FAILED = "runtime_cleanup_failed"
    CLEANUP_SUCCEEDED = "runtime_cleanup_succeeded"


class RuntimeEventState(StrEnum):
    """Runtime-axis states used by P3-D event content."""

    UNKNOWN = "unknown"
    SPAWNING = "spawning"
    ALIVE = "alive"
    EXITED = "exited"
    MISSING = "missing"
    PROBE_FAILED = "probe_failed"


class RuntimeEventSafetyFlags(DomainModel):
    """Safety switches embedded in every runtime event content_detail.

    P3-D2 defaults all real-execution indicators to ``False``.  Future phases
    may build events with explicit true values when those capabilities are
    genuinely implemented and audited.
    """

    execution_enabled: bool = False
    launches_ai_runtime: bool = False
    runs_real_command: bool = False
    runs_git: bool = False
    runs_write_git: bool = False
    changes_process_cwd: bool = False
    fake_launch_started: bool = False
    real_runtime_started: bool = False
    runtime_probe_started: bool = False


class RuntimeEventSchema(DomainModel):
    """Structured JSON contract for one runtime lifecycle event."""

    schema_version: str = RUNTIME_EVENT_SCHEMA_VERSION
    event_id: UUID = Field(default_factory=uuid4)
    event_type: RuntimeEventType
    session_id: UUID
    project_id: UUID
    task_id: UUID
    run_id: UUID
    runtime_handle_id: str | None = Field(default=None, max_length=200)
    runtime_type: str | None = Field(default=None, max_length=80)
    agent_type: str | None = Field(default=None, max_length=80)
    adapter_kind: str | None = Field(default=None, max_length=80)
    previous_runtime_state: RuntimeEventState
    next_runtime_state: RuntimeEventState
    reason_code: str | None = Field(default=None, max_length=200)
    summary_cn: str = Field(min_length=1, max_length=2_000)
    technical_detail: str | None = Field(default=None, max_length=2_000)
    safety_flags: RuntimeEventSafetyFlags = Field(default_factory=RuntimeEventSafetyFlags)
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "runtime_handle_id",
        "runtime_type",
        "agent_type",
        "adapter_kind",
        "reason_code",
        "summary_cn",
        "technical_detail",
        "created_by",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        """Trim text fields and collapse optional blank values."""

        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            return None
        return normalized_value

    @model_validator(mode="after")
    def validate_contract(self) -> "RuntimeEventSchema":
        """Keep schema version stable and timestamps UTC-aware."""

        if self.schema_version != RUNTIME_EVENT_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {RUNTIME_EVENT_SCHEMA_VERSION!r}"
            )
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        return self

    def to_content_detail_json(self) -> str:
        """Serialize for AgentMessage.content_detail without exceeding 4000 chars.

        P3-D2 does not write AgentMessage; this helper only returns the bounded
        JSON string a later writer can use.
        """

        payload = self.to_content_detail_dict()
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if len(content) <= RUNTIME_EVENT_CONTENT_DETAIL_MAX_LENGTH:
            return content

        compact_payload = dict(payload)
        compact_payload["technical_detail"] = _truncate_nullable_text(
            compact_payload.get("technical_detail"),
            max_length=500,
        )
        compact_payload["evidence"] = _compact_json_value(
            compact_payload.get("evidence", {}),
            max_length=1_200,
        )
        content = json.dumps(compact_payload, ensure_ascii=False, sort_keys=True)
        if len(content) <= RUNTIME_EVENT_CONTENT_DETAIL_MAX_LENGTH:
            return content

        minimal_payload = {
            "schema_version": payload["schema_version"],
            "event_id": payload["event_id"],
            "event_type": payload["event_type"],
            "session_id": payload["session_id"],
            "project_id": payload["project_id"],
            "task_id": payload["task_id"],
            "run_id": payload["run_id"],
            "runtime_handle_id": payload["runtime_handle_id"],
            "runtime_type": payload.get("runtime_type"),
            "agent_type": payload.get("agent_type"),
            "adapter_kind": payload.get("adapter_kind"),
            "previous_runtime_state": payload["previous_runtime_state"],
            "next_runtime_state": payload["next_runtime_state"],
            "reason_code": payload["reason_code"],
            "summary_cn": _truncate_nullable_text(payload["summary_cn"], max_length=500),
            "technical_detail": _truncate_nullable_text(
                payload.get("technical_detail"),
                max_length=200,
            ),
            "safety_flags": payload["safety_flags"],
            "evidence": {
                "truncated": True,
                "original_json_length": len(json.dumps(payload, ensure_ascii=False, sort_keys=True)),
            },
            "created_by": payload["created_by"],
        }
        content = json.dumps(minimal_payload, ensure_ascii=False, sort_keys=True)
        if len(content) <= RUNTIME_EVENT_CONTENT_DETAIL_MAX_LENGTH:
            return content

        minimal_payload["summary_cn"] = "运行时事件详情过长，已保留核心审计字段。"
        minimal_payload["technical_detail"] = None
        minimal_payload["evidence"] = {"truncated": True}
        return json.dumps(minimal_payload, ensure_ascii=False, sort_keys=True)

    def to_content_detail_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible P3-D content_detail payload."""

        return self.model_dump(mode="json", exclude={"created_at"})


class RuntimeEventBuilder:
    """Factory for standardized P3-D runtime lifecycle event payloads."""

    @staticmethod
    def from_gate_result(
        *,
        session_id: UUID,
        project_id: UUID,
        task_id: UUID,
        run_id: UUID,
        gate_result: Any,
        runtime_type: str | None = None,
        agent_type: str | None = None,
        adapter_kind: str | None = None,
        workspace_path: str | None = None,
        observed_pwd: str | None = None,
        launch_cwd_preview: str | None = None,
        created_by: str = "TaskWorker.run_once",
        event_id: UUID | None = None,
    ) -> RuntimeEventSchema:
        """Build a launch gate evaluated/blocked event from a gate result object.

        ``gate_result`` is intentionally typed as ``Any`` to avoid coupling this
        pure domain module to ``app.workers.runtime_adapter``.  It may be a
        dataclass, Pydantic model, or dict exposing the P3-B gate fields.
        """

        ready = bool(_value(gate_result, "ready", False))
        gates_passed = list(_value(gate_result, "gates_passed", []) or [])
        gates_failed = list(_value(gate_result, "gates_failed", []) or [])
        blocking_reason_code = _value(gate_result, "blocking_reason_code", None)
        blocking_summary = _value(gate_result, "blocking_summary", None)
        safety_flags = _safety_flags_from_source(gate_result)

        if ready:
            event_type = RuntimeEventType.LAUNCH_GATE_EVALUATED
            reason_code = "launch_gate_evaluated"
            summary_cn = (
                "运行时启动门禁已全部通过。共检查 5 道条件：工作区状态就绪、"
                "工作区上下文可用、运行时参数预览就绪、工作区路径验证通过、"
                "适配器能力可用。门禁通过只表示前置条件满足，运行时尚未启动。"
            )
            technical_detail = "All runtime launch gates passed; runtime was not started."
        else:
            event_type = RuntimeEventType.LAUNCH_GATE_BLOCKED
            reason_code = str(blocking_reason_code or "launch_gate_blocked")
            failed_gate_label = _failed_gate_label(gates_failed)
            reason_text = f"：{blocking_summary}" if blocking_summary else "。"
            summary_cn = (
                f"运行时启动门禁已阻断。{failed_gate_label}未通过{reason_text}"
                "门禁阻断是受控安全行为，不是系统崩溃。"
            )
            technical_detail = blocking_summary

        evidence = {
            "gates_passed": gates_passed,
            "gates_failed": gates_failed,
            "blocking_reason_code": blocking_reason_code,
            "blocking_summary": blocking_summary,
            "workspace_path": workspace_path,
            "observed_pwd": observed_pwd,
            "pwd_matches_workspace_path": _pwd_matches_workspace_path(
                workspace_path=workspace_path,
                observed_pwd=observed_pwd,
            ),
            "launch_cwd_preview": launch_cwd_preview,
        }

        return RuntimeEventSchema(
            event_id=event_id or uuid4(),
            event_type=event_type,
            session_id=session_id,
            project_id=project_id,
            task_id=task_id,
            run_id=run_id,
            runtime_handle_id=None,
            runtime_type=runtime_type,
            agent_type=agent_type,
            adapter_kind=adapter_kind,
            previous_runtime_state=RuntimeEventState.UNKNOWN,
            next_runtime_state=RuntimeEventState.UNKNOWN,
            reason_code=reason_code,
            summary_cn=summary_cn,
            technical_detail=technical_detail,
            safety_flags=safety_flags,
            evidence={key: value for key, value in evidence.items() if value is not None},
            created_by=created_by,
        )

    @staticmethod
    def build(
        *,
        event_type: RuntimeEventType | str,
        session_id: UUID,
        project_id: UUID,
        task_id: UUID,
        run_id: UUID,
        previous_runtime_state: RuntimeEventState | str | None = None,
        next_runtime_state: RuntimeEventState | str | None = None,
        reason_code: str | None = None,
        summary_cn: str | None = None,
        technical_detail: str | None = None,
        runtime_handle_id: str | None = None,
        runtime_type: str | None = None,
        agent_type: str | None = None,
        adapter_kind: str | None = None,
        safety_flags: RuntimeEventSafetyFlags | dict[str, bool] | None = None,
        evidence: dict[str, Any] | None = None,
        created_by: str = "RuntimeEventBuilder",
        event_id: UUID | None = None,
    ) -> RuntimeEventSchema:
        """Build any of the 14 P3-D event schemas without side effects."""

        normalized_event_type = RuntimeEventType(event_type)
        previous_state = _coerce_state(
            previous_runtime_state,
            _default_previous_state(normalized_event_type),
        )
        next_state = _coerce_state(
            next_runtime_state,
            _default_next_state(normalized_event_type),
        )
        normalized_safety_flags = _coerce_safety_flags(safety_flags)

        return RuntimeEventSchema(
            event_id=event_id or uuid4(),
            event_type=normalized_event_type,
            session_id=session_id,
            project_id=project_id,
            task_id=task_id,
            run_id=run_id,
            runtime_handle_id=runtime_handle_id,
            runtime_type=runtime_type,
            agent_type=agent_type,
            adapter_kind=adapter_kind,
            previous_runtime_state=previous_state,
            next_runtime_state=next_state,
            reason_code=reason_code or _default_reason_code(normalized_event_type),
            summary_cn=summary_cn or _default_summary_cn(normalized_event_type),
            technical_detail=technical_detail,
            safety_flags=normalized_safety_flags,
            evidence=evidence or {},
            created_by=created_by,
        )


RUNTIME_EVENT_TYPES: tuple[RuntimeEventType, ...] = tuple(RuntimeEventType)


_EVENT_STATE_TRANSITIONS: dict[
    RuntimeEventType,
    tuple[RuntimeEventState, RuntimeEventState],
] = {
    RuntimeEventType.LAUNCH_GATE_EVALUATED: (
        RuntimeEventState.UNKNOWN,
        RuntimeEventState.UNKNOWN,
    ),
    RuntimeEventType.LAUNCH_GATE_BLOCKED: (
        RuntimeEventState.UNKNOWN,
        RuntimeEventState.UNKNOWN,
    ),
    RuntimeEventType.LAUNCH_REQUESTED: (
        RuntimeEventState.UNKNOWN,
        RuntimeEventState.UNKNOWN,
    ),
    RuntimeEventType.SPAWNING: (
        RuntimeEventState.UNKNOWN,
        RuntimeEventState.SPAWNING,
    ),
    RuntimeEventType.HANDLE_BOUND: (
        RuntimeEventState.SPAWNING,
        RuntimeEventState.SPAWNING,
    ),
    RuntimeEventType.ALIVE_OBSERVED: (
        RuntimeEventState.SPAWNING,
        RuntimeEventState.ALIVE,
    ),
    RuntimeEventType.EXITED: (
        RuntimeEventState.ALIVE,
        RuntimeEventState.EXITED,
    ),
    RuntimeEventType.MISSING: (
        RuntimeEventState.ALIVE,
        RuntimeEventState.MISSING,
    ),
    RuntimeEventType.PROBE_FAILED: (
        RuntimeEventState.ALIVE,
        RuntimeEventState.PROBE_FAILED,
    ),
    RuntimeEventType.KILL_REQUESTED: (
        RuntimeEventState.ALIVE,
        RuntimeEventState.ALIVE,
    ),
    RuntimeEventType.KILLED: (
        RuntimeEventState.ALIVE,
        RuntimeEventState.EXITED,
    ),
    RuntimeEventType.CLEANUP_STARTED: (
        RuntimeEventState.EXITED,
        RuntimeEventState.EXITED,
    ),
    RuntimeEventType.CLEANUP_FAILED: (
        RuntimeEventState.EXITED,
        RuntimeEventState.EXITED,
    ),
    RuntimeEventType.CLEANUP_SUCCEEDED: (
        RuntimeEventState.EXITED,
        RuntimeEventState.EXITED,
    ),
}

_EVENT_REASON_CODES: dict[RuntimeEventType, str] = {
    RuntimeEventType.LAUNCH_GATE_EVALUATED: "launch_gate_evaluated",
    RuntimeEventType.LAUNCH_GATE_BLOCKED: "launch_gate_blocked",
    RuntimeEventType.LAUNCH_REQUESTED: "launch_requested",
    RuntimeEventType.SPAWNING: "launch_succeeded",
    RuntimeEventType.HANDLE_BOUND: "runtime_handle_bound",
    RuntimeEventType.ALIVE_OBSERVED: "probe_confirmed_alive",
    RuntimeEventType.EXITED: "process_exited",
    RuntimeEventType.MISSING: "handle_lost",
    RuntimeEventType.PROBE_FAILED: "probe_failed",
    RuntimeEventType.KILL_REQUESTED: "kill_requested",
    RuntimeEventType.KILLED: "process_killed",
    RuntimeEventType.CLEANUP_STARTED: "cleanup_started",
    RuntimeEventType.CLEANUP_FAILED: "cleanup_failed",
    RuntimeEventType.CLEANUP_SUCCEEDED: "cleanup_succeeded",
}

_EVENT_SUMMARIES_CN: dict[RuntimeEventType, str] = {
    RuntimeEventType.LAUNCH_GATE_EVALUATED: (
        "运行时启动门禁已全部通过。门禁通过只表示前置条件满足，运行时尚未启动。"
    ),
    RuntimeEventType.LAUNCH_GATE_BLOCKED: (
        "运行时启动门禁已阻断。门禁阻断是受控安全行为，不是系统崩溃。"
    ),
    RuntimeEventType.LAUNCH_REQUESTED: (
        "运行时启动已被请求。运行时尚未确认存活。"
    ),
    RuntimeEventType.SPAWNING: "运行时正在启动，正在等待首次检测结果。",
    RuntimeEventType.HANDLE_BOUND: "运行通道已绑定到会话记录。",
    RuntimeEventType.ALIVE_OBSERVED: "运行时进程已确认存活。",
    RuntimeEventType.EXITED: "运行时进程已退出。该进程已不在运行中。",
    RuntimeEventType.MISSING: "运行通道已丢失，当前无法确认运行时仍在运行。",
    RuntimeEventType.PROBE_FAILED: "运行时检测失败，当前无法确认进程状态。",
    RuntimeEventType.KILL_REQUESTED: "运行时终止已被请求。",
    RuntimeEventType.KILLED: "运行时已被终止。",
    RuntimeEventType.CLEANUP_STARTED: "运行时清理已开始。",
    RuntimeEventType.CLEANUP_FAILED: "运行时清理失败，审计线索已保留。",
    RuntimeEventType.CLEANUP_SUCCEEDED: "运行时清理已完成。",
}

_GATE_LABELS_CN = {
    "workspace_validation": "第 1 道条件（工作区状态校验）",
    "workspace_context": "第 2 道条件（工作区上下文）",
    "runtime_dry_run": "第 3 道条件（运行时参数预览）",
    "safe_command_proof": "第 4 道条件（工作区安全命令证明）",
    "adapter_capability": "第 5 道条件（适配器能力检查）",
}


def _default_previous_state(event_type: RuntimeEventType) -> RuntimeEventState:
    return _EVENT_STATE_TRANSITIONS[event_type][0]


def _default_next_state(event_type: RuntimeEventType) -> RuntimeEventState:
    return _EVENT_STATE_TRANSITIONS[event_type][1]


def _default_reason_code(event_type: RuntimeEventType) -> str:
    return _EVENT_REASON_CODES[event_type]


def _default_summary_cn(event_type: RuntimeEventType) -> str:
    return _EVENT_SUMMARIES_CN[event_type]


def _coerce_state(
    value: RuntimeEventState | str | None,
    default: RuntimeEventState,
) -> RuntimeEventState:
    if value is None:
        return default
    return RuntimeEventState(value)


def _coerce_safety_flags(
    value: RuntimeEventSafetyFlags | dict[str, bool] | None,
) -> RuntimeEventSafetyFlags:
    if value is None:
        return RuntimeEventSafetyFlags()
    if isinstance(value, RuntimeEventSafetyFlags):
        return value
    return RuntimeEventSafetyFlags(**value)


def _safety_flags_from_source(source: Any) -> RuntimeEventSafetyFlags:
    return RuntimeEventSafetyFlags(
        execution_enabled=bool(_value(source, "execution_enabled", False)),
        launches_ai_runtime=bool(_value(source, "launches_ai_runtime", False)),
        runs_real_command=bool(_value(source, "runs_real_command", False)),
        runs_git=bool(_value(source, "runs_git", False)),
        runs_write_git=bool(_value(source, "runs_write_git", False)),
        changes_process_cwd=bool(_value(source, "changes_process_cwd", False)),
        fake_launch_started=bool(_value(source, "fake_launch_started", False)),
        real_runtime_started=bool(_value(source, "real_runtime_started", False)),
        runtime_probe_started=bool(_value(source, "runtime_probe_started", False)),
    )


def _value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _failed_gate_label(gates_failed: list[str]) -> str:
    if not gates_failed:
        return "至少一道条件"
    return _GATE_LABELS_CN.get(gates_failed[0], f"条件 {gates_failed[0]}")


def _pwd_matches_workspace_path(
    *,
    workspace_path: str | None,
    observed_pwd: str | None,
) -> bool | None:
    if workspace_path is None or observed_pwd is None:
        return None
    return workspace_path == observed_pwd


def _truncate_nullable_text(value: Any, *, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def _compact_json_value(value: Any, *, max_length: int) -> dict[str, Any]:
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if len(content) <= max_length:
        return value if isinstance(value, dict) else {"value": value}
    return {
        "truncated": True,
        "original_json_length": len(content),
        "preview": content[: max_length - 1] + "…",
    }
