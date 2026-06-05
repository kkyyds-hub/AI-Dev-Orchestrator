"""Targeted tests for P3-D2 runtime event builder."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.domain.runtime_event import (
    RUNTIME_EVENT_CONTENT_DETAIL_MAX_LENGTH,
    RUNTIME_EVENT_SCHEMA_VERSION,
    RUNTIME_EVENT_TYPES,
    P3D2_BUILDABLE_RUNTIME_EVENT_TYPES,
    RuntimeEventBuilder,
    RuntimeEventSchema,
    RuntimeEventState,
    RuntimeEventType,
)
from app.workers.runtime_adapter import RuntimeLaunchGateResult


def _ids():
    return {
        "session_id": uuid4(),
        "project_id": uuid4(),
        "task_id": uuid4(),
        "run_id": uuid4(),
    }


def test_runtime_event_builder_exposes_all_p3d_event_types():
    assert [event.value for event in RUNTIME_EVENT_TYPES] == [
        "runtime_launch_gate_evaluated",
        "runtime_launch_gate_blocked",
        "runtime_launch_requested",
        "runtime_spawning",
        "runtime_handle_bound",
        "runtime_alive_observed",
        "runtime_exited",
        "runtime_missing",
        "runtime_probe_failed",
        "runtime_kill_requested",
        "runtime_killed",
        "runtime_cleanup_started",
        "runtime_cleanup_failed",
        "runtime_cleanup_succeeded",
    ]


def test_build_gate_evaluated_event_from_ready_gate_result():
    ids = _ids()
    gate = RuntimeLaunchGateResult(
        ready=True,
        gates_passed=[
            "workspace_validation",
            "workspace_context",
            "runtime_dry_run",
            "safe_command_proof",
            "adapter_capability",
        ],
    )

    event = RuntimeEventBuilder.from_gate_result(
        **ids,
        gate_result=gate,
        runtime_type="subprocess",
        agent_type="openai_provider",
        adapter_kind="fake",
        workspace_path="/tmp/aido-worktree",
        observed_pwd="/tmp/aido-worktree",
        launch_cwd_preview="/tmp/aido-worktree",
    )

    assert event.event_type == RuntimeEventType.LAUNCH_GATE_EVALUATED
    assert event.previous_runtime_state == RuntimeEventState.UNKNOWN
    assert event.next_runtime_state == RuntimeEventState.UNKNOWN
    assert event.runtime_handle_id is None
    assert event.reason_code == "launch_gate_evaluated"
    assert "运行时尚未启动" in event.summary_cn
    assert event.evidence["gates_passed"] == gate.gates_passed
    assert event.evidence["gates_failed"] == []
    assert event.evidence["pwd_matches_workspace_path"] is True
    assert event.safety_flags.model_dump() == {
        "execution_enabled": False,
        "launches_ai_runtime": False,
        "runs_real_command": False,
        "runs_git": False,
        "runs_write_git": False,
        "changes_process_cwd": False,
        "fake_launch_started": False,
        "real_runtime_started": False,
        "runtime_probe_started": False,
    }

    detail = json.loads(event.to_content_detail_json())
    assert detail["schema_version"] == RUNTIME_EVENT_SCHEMA_VERSION
    assert detail["event_type"] == "runtime_launch_gate_evaluated"
    assert detail["session_id"] == str(ids["session_id"])
    assert detail["next_runtime_state"] == "unknown"
    assert detail["safety_flags"]["real_runtime_started"] is False


def test_build_gate_blocked_event_from_failed_gate_result():
    ids = _ids()
    gate = RuntimeLaunchGateResult(
        ready=False,
        gates_passed=["workspace_validation", "workspace_context", "runtime_dry_run"],
        gates_failed=["safe_command_proof"],
        blocking_reason_code="pwd_mismatch_workspace_path",
        blocking_summary="pwd output does not match the AgentSession workspace path.",
    )

    event = RuntimeEventBuilder.from_gate_result(
        **ids,
        gate_result=gate,
        runtime_type="subprocess",
        agent_type="openai_provider",
        adapter_kind="fake",
        workspace_path="/tmp/aido-worktree",
        observed_pwd="/unexpected/path",
    )

    assert event.event_type == RuntimeEventType.LAUNCH_GATE_BLOCKED
    assert event.previous_runtime_state == RuntimeEventState.UNKNOWN
    assert event.next_runtime_state == RuntimeEventState.UNKNOWN
    assert event.reason_code == "pwd_mismatch_workspace_path"
    assert "第 4 道条件（工作区安全命令证明）" in event.summary_cn
    assert "不是系统崩溃" in event.summary_cn
    assert event.evidence == {
        "gates_passed": [
            "workspace_validation",
            "workspace_context",
            "runtime_dry_run",
        ],
        "gates_failed": ["safe_command_proof"],
        "blocking_reason_code": "pwd_mismatch_workspace_path",
        "blocking_summary": "pwd output does not match the AgentSession workspace path.",
        "workspace_path": "/tmp/aido-worktree",
        "observed_pwd": "/unexpected/path",
        "pwd_matches_workspace_path": False,
    }

    detail = json.loads(event.to_content_detail_json())
    assert detail["event_type"] == "runtime_launch_gate_blocked"
    assert detail["runtime_handle_id"] is None
    assert detail["evidence"]["gates_failed"] == ["safe_command_proof"]
    assert detail["safety_flags"]["fake_launch_started"] is False
    assert len(event.to_content_detail_json()) <= RUNTIME_EVENT_CONTENT_DETAIL_MAX_LENGTH


def test_build_only_supports_p3d2_launch_gate_event_types():
    ids = _ids()

    events = [
        RuntimeEventBuilder.build(**ids, event_type=event_type)
        for event_type in P3D2_BUILDABLE_RUNTIME_EVENT_TYPES
    ]

    assert [event.event_type for event in events] == [
        RuntimeEventType.LAUNCH_GATE_EVALUATED,
        RuntimeEventType.LAUNCH_GATE_BLOCKED,
    ]
    assert all(event.previous_runtime_state == RuntimeEventState.UNKNOWN for event in events)
    assert all(event.next_runtime_state == RuntimeEventState.UNKNOWN for event in events)
    assert all(event.runtime_handle_id is None for event in events)
    assert all(event.safety_flags.execution_enabled is False for event in events)
    assert all(event.safety_flags.fake_launch_started is False for event in events)
    assert all(event.safety_flags.real_runtime_started is False for event in events)
    assert all(event.safety_flags.runtime_probe_started is False for event in events)


def test_build_rejects_future_not_started_runtime_events():
    ids = _ids()
    future_event_types = [
        event_type
        for event_type in RUNTIME_EVENT_TYPES
        if event_type not in P3D2_BUILDABLE_RUNTIME_EVENT_TYPES
    ]

    assert len(future_event_types) == 12
    for event_type in future_event_types:
        with pytest.raises(ValueError) as exc_info:
            RuntimeEventBuilder.build(**ids, event_type=event_type)
        assert event_type.value in str(exc_info.value)
        assert "Not started" in str(exc_info.value)


def test_content_detail_json_is_bounded_for_agent_message_field_contract():
    ids = _ids()
    event = RuntimeEventBuilder.build(
        **ids,
        event_type=RuntimeEventType.LAUNCH_GATE_BLOCKED,
        technical_detail="x" * 2_000,
        evidence={"large_gate_output": "y" * 10_000},
    )

    content_detail = event.to_content_detail_json()
    payload = json.loads(content_detail)

    assert len(content_detail) <= RUNTIME_EVENT_CONTENT_DETAIL_MAX_LENGTH
    assert payload["event_type"] == "runtime_launch_gate_blocked"
    assert payload["evidence"]["truncated"] is True
    assert payload["safety_flags"]["runtime_probe_started"] is False


def test_runtime_event_schema_rejects_unknown_event_type_and_schema_version():
    ids = _ids()

    with pytest.raises(ValueError) as exc_info:
        RuntimeEventBuilder.build(**ids, event_type="runtime_not_a_real_event")
    assert "runtime_not_a_real_event" in str(exc_info.value)

    event = RuntimeEventBuilder.build(
        **ids,
        event_type=RuntimeEventType.LAUNCH_GATE_EVALUATED,
    )
    payload = event.model_dump()
    payload["schema_version"] = "2.0"
    with pytest.raises(ValueError):
        RuntimeEventSchema(**payload)
