"""Repository seam for P9 controlled runtime sessions and events."""

from __future__ import annotations

from typing import Protocol

from app.domain.executor_runtime import (
    ExecutorRuntimeSession,
    RuntimeEvent,
    RuntimeEventStreamSnapshot,
)


class RuntimeSessionRepository(Protocol):
    def save(self, session: ExecutorRuntimeSession) -> ExecutorRuntimeSession:
        """Persist a runtime session snapshot and return a detached copy."""

    def get(self, session_id: str) -> ExecutorRuntimeSession | None:
        """Return a detached runtime session snapshot by id."""


class RuntimeEventRepository(Protocol):
    def append(self, event: RuntimeEvent) -> RuntimeEvent:
        """Append a runtime event and return a detached copy."""

    def events_for_session(self, session_id: str) -> RuntimeEventStreamSnapshot:
        """Return a detached event stream snapshot for one session."""

    def latest_event(self, session_id: str) -> RuntimeEvent | None:
        """Return the latest detached event for one session."""


class InMemoryRuntimeSessionRepository:
    def __init__(self) -> None:
        self._items_by_id: dict[str, ExecutorRuntimeSession] = {}

    def save(self, session: ExecutorRuntimeSession) -> ExecutorRuntimeSession:
        stored_session = session.model_copy(deep=True)
        self._items_by_id[stored_session.session_id] = stored_session
        return stored_session.model_copy(deep=True)

    def get(self, session_id: str) -> ExecutorRuntimeSession | None:
        session = self._items_by_id.get(session_id.strip())
        if session is None:
            return None
        return session.model_copy(deep=True)


class InMemoryRuntimeEventRepository:
    def __init__(self) -> None:
        self._items_by_session_id: dict[str, list[RuntimeEvent]] = {}

    def append(self, event: RuntimeEvent) -> RuntimeEvent:
        stored_event = event.model_copy(deep=True)
        self._items_by_session_id.setdefault(stored_event.session_id, []).append(stored_event)
        return stored_event.model_copy(deep=True)

    def events_for_session(self, session_id: str) -> RuntimeEventStreamSnapshot:
        normalized_session_id = session_id.strip()
        events = [
            event.model_copy(deep=True)
            for event in self._items_by_session_id.get(normalized_session_id, [])
        ]
        return RuntimeEventStreamSnapshot(session_id=normalized_session_id, events=events)

    def latest_event(self, session_id: str) -> RuntimeEvent | None:
        events = self._items_by_session_id.get(session_id.strip(), [])
        if not events:
            return None
        return events[-1].model_copy(deep=True)
