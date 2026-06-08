from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.executor_runtime import (
    ExecutorRuntimeEventType,
    ExecutorRuntimeProcessSnapshot,
    ExecutorRuntimeSession,
    ExecutorRuntimeSource,
    ExecutorRuntimeState,
    ExecutorRuntimeUsageSnapshot,
    ExecutorRuntimeWorkspaceBinding,
    RuntimeEvent,
    RuntimeEventPayload,
    RuntimeEventStreamSnapshot,
)


def _now() -> datetime:
    return datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)


def _session(**overrides) -> ExecutorRuntimeSession:
    values = {
        "session_id": "session-1",
        "executor_id": "codex",
        "created_at": _now(),
        "updated_at": _now(),
    }
    values.update(overrides)
    return ExecutorRuntimeSession(**values)


def _event(
    *,
    event_id: str = "event-1",
    session_id: str = "session-1",
    timestamp: datetime | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id,
        session_id=session_id,
        event_type=ExecutorRuntimeEventType.SESSION_RUNNING,
        timestamp=timestamp or _now(),
    )


def test_session_default_source_is_fake_adapter_not_real_executor_pilot() -> None:
    session = _session()

    assert session.source == ExecutorRuntimeSource.FAKE_ADAPTER
    assert session.source != ExecutorRuntimeSource.REAL_EXECUTOR_PILOT


def test_session_ids_trim_and_empty_values_are_rejected() -> None:
    session = _session(session_id=" session-1 ", executor_id=" codex ")

    assert session.session_id == "session-1"
    assert session.executor_id == "codex"

    with pytest.raises(ValidationError):
        _session(session_id="   ")

    with pytest.raises(ValidationError):
        _session(executor_id="   ")


def test_finished_at_cannot_be_earlier_than_started_at() -> None:
    started_at = _now()

    with pytest.raises(ValidationError):
        _session(
            started_at=started_at,
            finished_at=started_at - timedelta(seconds=1),
        )


def test_updated_at_cannot_be_earlier_than_created_at() -> None:
    created_at = _now()

    with pytest.raises(ValidationError):
        _session(created_at=created_at, updated_at=created_at - timedelta(seconds=1))


@pytest.mark.parametrize(
    "state",
    [ExecutorRuntimeState.RUNNING, ExecutorRuntimeState.LAUNCHING],
)
def test_running_and_launching_states_do_not_allow_finished_at(
    state: ExecutorRuntimeState,
) -> None:
    with pytest.raises(ValidationError):
        _session(state=state, started_at=_now(), finished_at=_now())


@pytest.mark.parametrize(
    "state",
    [
        ExecutorRuntimeState.COMPLETED,
        ExecutorRuntimeState.FAILED,
        ExecutorRuntimeState.CANCELLED,
        ExecutorRuntimeState.TIMED_OUT,
        ExecutorRuntimeState.KILLED,
        ExecutorRuntimeState.CLEANED_UP,
    ],
)
def test_terminal_states_return_true(state: ExecutorRuntimeState) -> None:
    session = _session(state=state)

    assert session.is_terminal() is True


@pytest.mark.parametrize(
    "state",
    [
        ExecutorRuntimeState.CLEANUP_REQUIRED,
        ExecutorRuntimeState.COMPLETED,
        ExecutorRuntimeState.FAILED,
        ExecutorRuntimeState.CANCELLED,
        ExecutorRuntimeState.TIMED_OUT,
        ExecutorRuntimeState.KILLED,
    ],
)
def test_cleanup_required_and_unclean_terminal_states_require_cleanup(
    state: ExecutorRuntimeState,
) -> None:
    session = _session(state=state)

    assert session.requires_cleanup() is True


def test_can_transition_to_covers_legal_and_illegal_transitions() -> None:
    pending = _session(state=ExecutorRuntimeState.PENDING)
    running = _session(state=ExecutorRuntimeState.RUNNING)
    cleaned_up = _session(state=ExecutorRuntimeState.CLEANED_UP)

    assert pending.can_transition_to(ExecutorRuntimeState.LAUNCH_REQUESTED) is True
    assert pending.can_transition_to(ExecutorRuntimeState.RUNNING) is False
    assert running.can_transition_to(ExecutorRuntimeState.WAITING_INPUT) is True
    assert running.can_transition_to(ExecutorRuntimeState.LAUNCH_APPROVED) is False
    assert cleaned_up.can_transition_to(ExecutorRuntimeState.RUNNING) is False


def test_blocking_reasons_are_trimmed_and_deduplicated() -> None:
    session = _session(blocking_reasons=[" gate ", "gate", "", " budget "])

    assert session.blocking_reasons == ["gate", "budget"]


@pytest.mark.parametrize(
    "path_hint",
    [
        "/Users/kk/project",
        "~/project",
        "C:\\Users\\kk\\project",
        "\\\\server\\share\\project",
    ],
)
def test_workspace_path_hint_sanitizes_absolute_home_windows_and_unc_paths(
    path_hint: str,
) -> None:
    binding = ExecutorRuntimeWorkspaceBinding(workspace_path_hint=path_hint)

    assert binding.workspace_path_hint == "workspace hint provided"


def test_process_id_must_be_positive_when_provided() -> None:
    with pytest.raises(ValidationError):
        ExecutorRuntimeProcessSnapshot(process_id=0)

    with pytest.raises(ValidationError):
        ExecutorRuntimeProcessSnapshot(process_id=-1)


def test_process_finished_at_cannot_be_earlier_than_started_at() -> None:
    with pytest.raises(ValidationError):
        ExecutorRuntimeProcessSnapshot(
            started_at=_now(),
            finished_at=_now() - timedelta(seconds=1),
        )


def test_usage_tokens_cannot_be_negative_and_total_must_cover_parts() -> None:
    with pytest.raises(ValidationError):
        ExecutorRuntimeUsageSnapshot(prompt_tokens=-1)

    with pytest.raises(ValidationError):
        ExecutorRuntimeUsageSnapshot(completion_tokens=-1)

    with pytest.raises(ValidationError):
        ExecutorRuntimeUsageSnapshot(prompt_tokens=2, completion_tokens=3, total_tokens=4)


def test_estimated_cost_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        ExecutorRuntimeUsageSnapshot(estimated_cost=Decimal("-0.01"))


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("result_summary", "contains api key value"),
        ("error_summary", "Bearer abc"),
    ],
)
def test_session_summaries_reject_suspected_secret_material(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        _session(**{field_name: value})


def test_event_payload_message_rejects_suspected_secret_material() -> None:
    with pytest.raises(ValidationError):
        RuntimeEventPayload(message="token leaked")


def test_runtime_event_rejects_empty_event_id_and_session_id() -> None:
    with pytest.raises(ValidationError):
        _event(event_id="   ")

    with pytest.raises(ValidationError):
        _event(session_id="   ")


def test_runtime_event_append_only_defaults_true() -> None:
    event = _event()

    assert event.append_only is True


def test_runtime_event_stream_rejects_mismatched_session_ids() -> None:
    with pytest.raises(ValidationError):
        RuntimeEventStreamSnapshot(
            session_id="session-1",
            events=[_event(session_id="session-2")],
        )


def test_runtime_event_stream_rejects_descending_timestamps() -> None:
    with pytest.raises(ValidationError):
        RuntimeEventStreamSnapshot(
            session_id="session-1",
            events=[
                _event(event_id="event-2", timestamp=_now() + timedelta(seconds=1)),
                _event(event_id="event-1", timestamp=_now()),
            ],
        )


def test_runtime_event_stream_total_matches_len_and_latest_event() -> None:
    first = _event(event_id="event-1", timestamp=_now())
    second = _event(event_id="event-2", timestamp=_now() + timedelta(seconds=1))
    snapshot = RuntimeEventStreamSnapshot(
        session_id="session-1",
        events=[first, second],
    )

    assert snapshot.total == 2
    assert snapshot.latest_event() == second

    with pytest.raises(ValidationError):
        RuntimeEventStreamSnapshot(session_id="session-1", events=[first], total=2)


def test_runtime_event_payload_rejects_arbitrary_dict_fields() -> None:
    with pytest.raises(ValidationError):
        RuntimeEventPayload(raw_env={"A": "B"})


def test_executor_runtime_domain_does_not_import_service_api_or_worker_layers() -> None:
    source = Path("app/domain/executor_runtime.py").read_text()

    assert "app.services" not in source
    assert "app.api" not in source
    assert "app.workers" not in source


def test_executor_runtime_domain_does_not_import_subprocess_shell_helpers() -> None:
    source = Path("app/domain/executor_runtime.py").read_text()

    assert "import subprocess" not in source
    assert "os.popen" not in source


def test_executor_runtime_domain_excludes_forbidden_runtime_fields() -> None:
    source = Path("app/domain/executor_runtime.py").read_text()
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


def test_reference_project_path_is_not_copied_into_executor_runtime_domain() -> None:
    source = Path("app/domain/executor_runtime.py").read_text()

    assert "/Users/kk/project explore/agent-orchestrator" not in source
    assert "project-explore-one" not in source
