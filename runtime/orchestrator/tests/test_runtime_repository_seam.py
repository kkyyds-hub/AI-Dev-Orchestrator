from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.domain.executor_runtime import (
    ExecutorRuntimeEventType,
    ExecutorRuntimeSession,
    ExecutorRuntimeState,
    RuntimeEvent,
    RuntimeEventPayload,
)
from app.repositories.runtime_session_repository import (
    InMemoryRuntimeEventRepository,
    InMemoryRuntimeSessionRepository,
)
from app.services.controlled_runtime_service import ControlledRuntimeService


def _now() -> datetime:
    return datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


def _session(**overrides) -> ExecutorRuntimeSession:
    values = {
        "session_id": "session-1",
        "executor_id": "codex",
        "state": ExecutorRuntimeState.RUNNING,
        "created_at": _now(),
        "updated_at": _now(),
    }
    values.update(overrides)
    return ExecutorRuntimeSession(**values)


def _event(
    event_id: str,
    event_type: ExecutorRuntimeEventType,
    *,
    timestamp: datetime | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id,
        session_id="session-1",
        event_type=event_type,
        timestamp=timestamp or _now(),
        payload=RuntimeEventPayload(message=event_type.value),
    )


def test_in_memory_runtime_session_repository_saves_and_gets_session() -> None:
    repository = InMemoryRuntimeSessionRepository()
    session = _session()

    saved = repository.save(session)
    fetched = repository.get(" session-1 ")

    assert saved == session
    assert fetched == session


def test_in_memory_runtime_session_repository_returns_deep_copies() -> None:
    repository = InMemoryRuntimeSessionRepository()
    repository.save(_session(blocking_reasons=["first"]))

    fetched = repository.get("session-1")
    assert fetched is not None
    fetched.blocking_reasons.append("mutated")

    stored = repository.get("session-1")

    assert stored is not None
    assert stored.blocking_reasons == ["first"]


def test_in_memory_runtime_event_repository_appends_and_returns_stream_total() -> None:
    repository = InMemoryRuntimeEventRepository()

    repository.append(_event("event-1", ExecutorRuntimeEventType.SESSION_CREATED))
    repository.append(
        _event(
            "event-2",
            ExecutorRuntimeEventType.SESSION_RUNNING,
            timestamp=_now() + timedelta(seconds=1),
        ),
    )

    stream = repository.events_for_session(" session-1 ")

    assert [event.event_id for event in stream.events] == ["event-1", "event-2"]
    assert stream.total == 2
    assert stream.latest_event().event_type == ExecutorRuntimeEventType.SESSION_RUNNING


def test_in_memory_runtime_event_repository_returns_deep_copies() -> None:
    repository = InMemoryRuntimeEventRepository()
    repository.append(_event("event-1", ExecutorRuntimeEventType.SESSION_CREATED))

    stream = repository.events_for_session("session-1")
    stream.events[0].payload.message = "mutated"

    stored = repository.events_for_session("session-1")

    assert stored.latest_event().payload.message == "session.created"


def test_controlled_runtime_service_defaults_to_in_memory_repositories() -> None:
    service = ControlledRuntimeService(clock=_now)

    assert isinstance(service._session_repository, InMemoryRuntimeSessionRepository)
    assert isinstance(service._event_repository, InMemoryRuntimeEventRepository)


def test_controlled_runtime_service_no_longer_owns_bare_session_dict() -> None:
    source = Path("app/services/controlled_runtime_service.py").read_text()

    assert "_sessions" not in source


def test_repository_seam_does_not_import_api_workers_or_runtime_process_helpers() -> None:
    source = Path("app/repositories/runtime_session_repository.py").read_text()

    forbidden_snippets = {
        "app.api",
        "app.workers",
        "import subprocess",
        "from subprocess",
        "import os",
        "from os",
        "os.popen",
        "import pathlib",
        "from pathlib",
        "import sqlite",
        "from sqlite",
        "import sqlalchemy",
        "from sqlalchemy",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source


def test_repository_seam_excludes_git_write_and_sensitive_field_strings() -> None:
    source = Path("app/repositories/runtime_session_repository.py").read_text()

    forbidden_snippets = {
        "git add",
        "git commit",
        "git push",
        "pull request",
        "merge",
        "api_key",
        "token_value",
        "auth_token",
        "secret",
    }

    for snippet in forbidden_snippets:
        assert snippet not in source
