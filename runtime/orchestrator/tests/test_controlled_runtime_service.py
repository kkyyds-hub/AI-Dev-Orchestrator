from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.executor_runtime import (
    ExecutorRuntimeEventType,
    ExecutorRuntimeExitReason,
    ExecutorRuntimeState,
    RuntimeEvent,
    RuntimeEventPayload,
)
from app.domain.executor_runtime_safety import (
    REQUIRED_RUNTIME_SAFETY_GATES,
    ExecutorLaunchRequest,
    RuntimeFeatureFlagPolicy,
    RuntimeLaunchBlockReason,
    RuntimeLaunchRequestStatus,
    RuntimeSafetyEvaluationInput,
    RuntimeSafetyGateCheck,
    RuntimeSafetyGateName,
    RuntimeSafetyGateSnapshot,
    RuntimeSafetyGateStatus,
    RuntimeWorkspaceGateInput,
)
from app.services.controlled_runtime_service import (
    ControlledRuntimeBlockedError,
    ControlledRuntimeService,
    FakeExecutorAdapter,
    InMemoryRuntimeEventRecorder,
)


def _now() -> datetime:
    return datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)


def _passed_check(gate_name: RuntimeSafetyGateName) -> RuntimeSafetyGateCheck:
    return RuntimeSafetyGateCheck(
        gate_name=gate_name,
        status=RuntimeSafetyGateStatus.PASSED,
        passed=True,
    )


def _all_passed_snapshot() -> RuntimeSafetyGateSnapshot:
    return RuntimeSafetyGateSnapshot(
        gate_checks=[_passed_check(gate) for gate in REQUIRED_RUNTIME_SAFETY_GATES],
        evaluated_at=_now(),
    )


def _blocked_snapshot() -> RuntimeSafetyGateSnapshot:
    return RuntimeSafetyEvaluationInput(
        feature_flags=RuntimeFeatureFlagPolicy(executor_runtime_enabled=False),
        workspace=RuntimeWorkspaceGateInput(workspace_bound=False),
    ).evaluate()


def _approved_request(**overrides) -> ExecutorLaunchRequest:
    values = {
        "request_id": "request-1",
        "executor_id": "codex",
        "launch_preview_id": "preview-1",
        "project_id": "project-1",
        "task_id": "task-1",
        "run_id": "run-1",
        "requested_by": "user-1",
        "status": RuntimeLaunchRequestStatus.APPROVED,
        "safety_snapshot": _all_passed_snapshot(),
        "created_at": _now(),
        "approved_at": _now(),
    }
    values.update(overrides)
    return ExecutorLaunchRequest(**values)


def _draft_request(**overrides) -> ExecutorLaunchRequest:
    values = {
        "request_id": "request-1",
        "executor_id": "codex",
        "launch_preview_id": "preview-1",
        "status": RuntimeLaunchRequestStatus.DRAFT,
        "safety_snapshot": _all_passed_snapshot(),
        "created_at": _now(),
    }
    values.update(overrides)
    return ExecutorLaunchRequest(**values)


class RecordingAdapter(FakeExecutorAdapter):
    def __init__(self) -> None:
        super().__init__(clock=_now)
        self.launch_count = 0

    def launch(self, session):
        self.launch_count += 1
        return super().launch(session)


def test_service_default_adapter_is_fake_executor_adapter() -> None:
    service = ControlledRuntimeService(clock=_now)

    assert isinstance(service.adapter, FakeExecutorAdapter)


def test_launch_with_failed_safety_snapshot_returns_blocked_without_adapter_launch() -> None:
    adapter = RecordingAdapter()
    service = ControlledRuntimeService(adapter=adapter, clock=_now)
    request = _draft_request(safety_snapshot=_blocked_snapshot())

    session = service.launch(request)
    events = service.events_for_session(session.session_id)

    assert session.state == ExecutorRuntimeState.BLOCKED
    assert session.exit_reason == ExecutorRuntimeExitReason.SAFETY_GATE_BLOCKED
    assert RuntimeLaunchBlockReason.FEATURE_FLAG_DISABLED.value in session.blocking_reasons
    assert adapter.launch_count == 0
    assert [event.event_type for event in events.events] == [
        ExecutorRuntimeEventType.SESSION_SAFETY_GATE_BLOCKED,
        ExecutorRuntimeEventType.SESSION_BLOCKED,
    ]


def test_launch_request_status_must_be_approved() -> None:
    service = ControlledRuntimeService(clock=_now)

    with pytest.raises(ControlledRuntimeBlockedError):
        service.launch(_draft_request())


def test_expired_approved_launch_request_is_rejected() -> None:
    service = ControlledRuntimeService(clock=_now)
    request = _approved_request(expires_at=_now())

    with pytest.raises(ControlledRuntimeBlockedError):
        service.launch(request)


def test_approved_request_with_all_gates_passed_launches_fake_running_session() -> None:
    service = ControlledRuntimeService(clock=_now)

    session = service.launch(_approved_request())

    assert session.state == ExecutorRuntimeState.RUNNING
    assert session.source.value == "fake_adapter"
    assert session.process.process_id == 1
    assert session.process.started_at == _now()
    assert session.process.last_activity_at == _now()
    assert session.executor_id == "codex"
    assert session.project_id == "project-1"
    assert session.task_id == "task-1"
    assert session.run_id == "run-1"
    assert session.launch_preview_id == "preview-1"
    assert service.get_session(session.session_id) == session


def test_launch_records_created_launching_and_running_events() -> None:
    service = ControlledRuntimeService(clock=_now)

    session = service.launch(_approved_request())
    events = service.events_for_session(session.session_id)

    assert events.total == 3
    assert [event.event_type for event in events.events] == [
        ExecutorRuntimeEventType.SESSION_CREATED,
        ExecutorRuntimeEventType.SESSION_LAUNCHING,
        ExecutorRuntimeEventType.SESSION_RUNNING,
    ]
    assert events.latest_event().event_type == ExecutorRuntimeEventType.SESSION_RUNNING


def test_poll_can_complete_running_session_and_record_event() -> None:
    service = ControlledRuntimeService(clock=_now)
    session = service.launch(_approved_request())

    completed = service.poll(session.session_id)

    assert completed is not None
    assert completed.state == ExecutorRuntimeState.COMPLETED
    assert completed.exit_reason == ExecutorRuntimeExitReason.COMPLETED
    assert completed.process.exit_code == 0
    assert service.events_for_session(session.session_id).latest_event().event_type == (
        ExecutorRuntimeEventType.SESSION_COMPLETED
    )


def test_poll_can_move_running_session_to_idle_with_configured_fake_adapter() -> None:
    service = ControlledRuntimeService(
        adapter=FakeExecutorAdapter(next_poll_state=ExecutorRuntimeState.IDLE, clock=_now),
        clock=_now,
    )
    session = service.launch(_approved_request())

    idle = service.poll(session.session_id)

    assert idle is not None
    assert idle.state == ExecutorRuntimeState.IDLE
    assert service.events_for_session(session.session_id).latest_event().event_type == (
        ExecutorRuntimeEventType.SESSION_IDLE
    )


def test_cancel_kill_and_cleanup_record_lifecycle_events() -> None:
    cancel_service = ControlledRuntimeService(clock=_now)
    cancelled = cancel_service.cancel(
        cancel_service.launch(_approved_request(request_id="request-cancel")).session_id,
    )

    assert cancelled is not None
    assert cancelled.state == ExecutorRuntimeState.CANCELLED
    assert cancelled.exit_reason == ExecutorRuntimeExitReason.CANCELLED_BY_USER
    assert cancel_service.events_for_session(cancelled.session_id).latest_event().event_type == (
        ExecutorRuntimeEventType.SESSION_CANCELLED
    )

    kill_service = ControlledRuntimeService(clock=_now)
    killed = kill_service.kill(
        kill_service.launch(_approved_request(request_id="request-kill")).session_id,
    )

    assert killed is not None
    assert killed.state == ExecutorRuntimeState.KILLED
    assert killed.exit_reason == ExecutorRuntimeExitReason.KILLED_BY_USER
    assert kill_service.events_for_session(killed.session_id).latest_event().event_type == (
        ExecutorRuntimeEventType.SESSION_KILLED
    )

    cleaned = kill_service.cleanup(killed.session_id)

    assert cleaned is not None
    assert cleaned.state == ExecutorRuntimeState.CLEANED_UP
    assert kill_service.events_for_session(killed.session_id).latest_event().event_type == (
        ExecutorRuntimeEventType.SESSION_CLEANED_UP
    )


def test_get_session_and_lifecycle_methods_return_none_for_missing_session() -> None:
    service = ControlledRuntimeService(clock=_now)

    assert service.get_session("missing") is None
    assert service.poll("missing") is None
    assert service.cancel("missing") is None
    assert service.kill("missing") is None
    assert service.cleanup("missing") is None


def test_in_memory_event_recorder_returns_append_only_copies() -> None:
    recorder = InMemoryRuntimeEventRecorder()
    event = RuntimeEvent(
        event_id="event-1",
        session_id="session-1",
        event_type=ExecutorRuntimeEventType.SESSION_CREATED,
        timestamp=_now(),
        payload=RuntimeEventPayload(message="session created"),
    )

    recorder.append(event)
    snapshot = recorder.events_for_session("session-1")
    snapshot.events.append(
        RuntimeEvent(
            event_id="event-2",
            session_id="session-1",
            event_type=ExecutorRuntimeEventType.SESSION_RUNNING,
            timestamp=_now() + timedelta(seconds=1),
        ),
    )

    stored_snapshot = recorder.events_for_session("session-1")

    assert stored_snapshot.total == 1
    assert stored_snapshot.latest_event().event_id == "event-1"
    assert stored_snapshot.latest_event().append_only is True


def test_event_payload_rejects_suspected_credential_material() -> None:
    with pytest.raises(ValidationError):
        RuntimeEventPayload(message="token leaked")


def test_service_file_does_not_import_forbidden_layers_or_process_helpers() -> None:
    source = Path("app/services/controlled_runtime_service.py").read_text()

    forbidden_snippets = {
        "import subprocess",
        "os.popen",
        "import pty",
        "import signal",
        "import shlex",
        "anyio.create_process",
        "asyncio.create_subprocess_exec",
        "asyncio.create_subprocess_shell",
        "app.api",
        "app.workers",
        "app.services.executor_service",
        "app.services.openai_provider_executor_service",
        "app.services.provider_config_service",
        "run_shell_command",
        "shell=True",
        "~/.codex",
        "~/.claude",
        "os.environ",
        "/Users/kk/project explore/agent-orchestrator",
        "project-explore-one",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source


def test_service_file_excludes_forbidden_runtime_fields() -> None:
    source = Path("app/services/controlled_runtime_service.py").read_text()
    forbidden_terms = {
        "command",
        "raw_command",
        "raw_args",
        "env_vars",
        "api_key",
        "token_value",
        "auth_token",
        "secret",
        "native_config_path",
        "cli_path",
        "process_handle",
        "log_path",
    }

    for term in forbidden_terms:
        assert f"{term}:" not in source
