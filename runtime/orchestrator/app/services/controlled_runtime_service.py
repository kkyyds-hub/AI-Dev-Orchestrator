"""P9-D in-memory controlled runtime service with a fake adapter only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Protocol
from uuid import uuid4

from app.domain.executor_runtime import (
    ExecutorRuntimeEventType,
    ExecutorRuntimeExitReason,
    ExecutorRuntimeProcessSnapshot,
    ExecutorRuntimeSession,
    ExecutorRuntimeSource,
    ExecutorRuntimeState,
    ExecutorRuntimeWorkspaceBinding,
    RuntimeEvent,
    RuntimeEventPayload,
    RuntimeEventStreamSnapshot,
)
from app.domain.executor_runtime_safety import (
    ExecutorLaunchRequest,
    RuntimeLaunchRequestStatus,
)
from app.repositories.runtime_session_repository import (
    InMemoryRuntimeEventRepository,
    InMemoryRuntimeSessionRepository,
    RuntimeEventRepository,
    RuntimeSessionRepository,
)

Clock = Callable[[], datetime]


class ControlledRuntimeError(Exception):
    """Base error for controlled runtime orchestration failures."""


class ControlledRuntimeBlockedError(ControlledRuntimeError):
    """Raised when a launch request is blocked before runtime handoff."""


class ControlledRuntimeNotFoundError(ControlledRuntimeError):
    """Raised when a runtime session cannot be found."""


class ControlledRuntimeInvalidTransitionError(ControlledRuntimeError):
    """Raised when a requested lifecycle transition is not allowed."""


class ExecutorRuntimeAdapter(Protocol):
    def launch(self, session: ExecutorRuntimeSession) -> ExecutorRuntimeSession:
        """Move an approved fake session into running state."""

    def poll(self, session: ExecutorRuntimeSession) -> ExecutorRuntimeSession:
        """Advance a fake session after an observation tick."""

    def cancel(self, session: ExecutorRuntimeSession) -> ExecutorRuntimeSession:
        """Cancel a fake session."""

    def kill(self, session: ExecutorRuntimeSession) -> ExecutorRuntimeSession:
        """Kill a fake session."""

    def cleanup(self, session: ExecutorRuntimeSession) -> ExecutorRuntimeSession:
        """Clean up a fake session."""


class FakeExecutorAdapter:
    """Adapter that updates domain snapshots without starting external programs."""

    def __init__(
        self,
        *,
        next_poll_state: ExecutorRuntimeState = ExecutorRuntimeState.COMPLETED,
        clock: Clock | None = None,
    ) -> None:
        if next_poll_state not in {
            ExecutorRuntimeState.IDLE,
            ExecutorRuntimeState.COMPLETED,
        }:
            raise ControlledRuntimeInvalidTransitionError("poll target state is not allowed")
        self._next_poll_state = next_poll_state
        self._clock = clock or _utc_now

    def launch(self, session: ExecutorRuntimeSession) -> ExecutorRuntimeSession:
        if session.state not in {
            ExecutorRuntimeState.LAUNCH_APPROVED,
            ExecutorRuntimeState.LAUNCHING,
        }:
            raise ControlledRuntimeInvalidTransitionError("session is not launchable")

        now = self._clock()
        return session.model_copy(
            update={
                "state": ExecutorRuntimeState.RUNNING,
                "source": ExecutorRuntimeSource.FAKE_ADAPTER,
                "process": ExecutorRuntimeProcessSnapshot(
                    process_id=1,
                    started_at=now,
                    last_activity_at=now,
                    heartbeat_at=now,
                ),
                "started_at": now,
                "updated_at": now,
            },
            deep=True,
        )

    def poll(self, session: ExecutorRuntimeSession) -> ExecutorRuntimeSession:
        if session.is_terminal():
            return session

        next_state = self._next_poll_state
        if not session.can_transition_to(next_state):
            raise ControlledRuntimeInvalidTransitionError("poll transition is not allowed")

        now = self._clock()
        update: dict[str, object] = {
            "state": next_state,
            "updated_at": now,
            "process": session.process.model_copy(
                update={"last_activity_at": now, "heartbeat_at": now},
                deep=True,
            ),
        }
        if next_state == ExecutorRuntimeState.COMPLETED:
            update["exit_reason"] = ExecutorRuntimeExitReason.COMPLETED
            update["finished_at"] = now
            update["process"] = session.process.model_copy(
                update={
                    "exit_code": 0,
                    "finished_at": now,
                    "last_activity_at": now,
                    "heartbeat_at": now,
                },
                deep=True,
            )
        return session.model_copy(update=update, deep=True)

    def cancel(self, session: ExecutorRuntimeSession) -> ExecutorRuntimeSession:
        if not session.can_transition_to(ExecutorRuntimeState.CANCELLED):
            raise ControlledRuntimeInvalidTransitionError("cancel transition is not allowed")
        now = self._clock()
        return session.model_copy(
            update={
                "state": ExecutorRuntimeState.CANCELLED,
                "exit_reason": ExecutorRuntimeExitReason.CANCELLED_BY_USER,
                "finished_at": now,
                "updated_at": now,
                "process": session.process.model_copy(
                    update={"finished_at": now, "last_activity_at": now},
                    deep=True,
                ),
            },
            deep=True,
        )

    def kill(self, session: ExecutorRuntimeSession) -> ExecutorRuntimeSession:
        if not session.can_transition_to(ExecutorRuntimeState.KILLED):
            raise ControlledRuntimeInvalidTransitionError("kill transition is not allowed")
        now = self._clock()
        return session.model_copy(
            update={
                "state": ExecutorRuntimeState.KILLED,
                "exit_reason": ExecutorRuntimeExitReason.KILLED_BY_USER,
                "finished_at": now,
                "updated_at": now,
                "process": session.process.model_copy(
                    update={"finished_at": now, "last_activity_at": now},
                    deep=True,
                ),
            },
            deep=True,
        )

    def cleanup(self, session: ExecutorRuntimeSession) -> ExecutorRuntimeSession:
        if not session.can_transition_to(ExecutorRuntimeState.CLEANED_UP):
            raise ControlledRuntimeInvalidTransitionError("cleanup transition is not allowed")
        now = self._clock()
        return session.model_copy(
            update={
                "state": ExecutorRuntimeState.CLEANED_UP,
                "updated_at": now,
            },
            deep=True,
        )


class ControlledRuntimeService:
    def __init__(
        self,
        *,
        adapter: ExecutorRuntimeAdapter | None = None,
        session_repository: RuntimeSessionRepository | None = None,
        event_repository: RuntimeEventRepository | None = None,
        event_recorder: RuntimeEventRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._clock = clock or _utc_now
        self._adapter = adapter or FakeExecutorAdapter(clock=self._clock)
        self._session_repository = session_repository or InMemoryRuntimeSessionRepository()
        self._event_repository = (
            event_repository
            or event_recorder
            or InMemoryRuntimeEventRepository()
        )

    @property
    def adapter(self) -> ExecutorRuntimeAdapter:
        return self._adapter

    def launch(self, request: ExecutorLaunchRequest) -> ExecutorRuntimeSession:
        if not request.safety_snapshot.all_passed:
            session = self._build_blocked_session(request)
            self._store(session)
            self._record(
                session,
                ExecutorRuntimeEventType.SESSION_SAFETY_GATE_BLOCKED,
                "safety gate blocked",
            )
            self._record(session, ExecutorRuntimeEventType.SESSION_BLOCKED, "session blocked")
            return session

        if request.status != RuntimeLaunchRequestStatus.APPROVED:
            raise ControlledRuntimeBlockedError("launch request is not approved")
        if request.status in {
            RuntimeLaunchRequestStatus.CONSUMED,
            RuntimeLaunchRequestStatus.CANCELLED,
            RuntimeLaunchRequestStatus.EXPIRED,
            RuntimeLaunchRequestStatus.REJECTED,
        }:
            raise ControlledRuntimeBlockedError("launch request is not launchable")
        if request.expires_at is not None and request.expires_at <= self._clock():
            raise ControlledRuntimeBlockedError("launch request is no longer active")

        now = self._clock()
        session = ExecutorRuntimeSession(
            session_id=_new_id("runtime-session"),
            executor_id=request.executor_id,
            launch_preview_id=request.launch_preview_id,
            project_id=request.project_id,
            task_id=request.task_id,
            run_id=request.run_id,
            state=ExecutorRuntimeState.LAUNCHING,
            source=ExecutorRuntimeSource.FAKE_ADAPTER,
            workspace=ExecutorRuntimeWorkspaceBinding(workspace_bound=True),
            created_by=request.requested_by,
            created_at=now,
            updated_at=now,
        )
        self._store(session)
        self._record(session, ExecutorRuntimeEventType.SESSION_CREATED, "session created")
        self._record(session, ExecutorRuntimeEventType.SESSION_LAUNCHING, "session launching")

        launched = self._adapter.launch(session)
        self._store(launched)
        self._record(launched, ExecutorRuntimeEventType.SESSION_RUNNING, "session running")
        return launched

    def get_session(self, session_id: str) -> ExecutorRuntimeSession | None:
        return self._session_repository.get(session_id)

    def poll(self, session_id: str) -> ExecutorRuntimeSession | None:
        session = self.get_session(session_id)
        if session is None:
            return None
        updated = self._adapter.poll(session)
        self._store(updated)
        if updated.state != session.state:
            self._record(updated, _event_type_for_state(updated.state), "session polled")
        return updated

    def cancel(self, session_id: str) -> ExecutorRuntimeSession | None:
        session = self.get_session(session_id)
        if session is None:
            return None
        updated = self._adapter.cancel(session)
        self._store(updated)
        self._record(updated, ExecutorRuntimeEventType.SESSION_CANCELLED, "session cancelled")
        return updated

    def kill(self, session_id: str) -> ExecutorRuntimeSession | None:
        session = self.get_session(session_id)
        if session is None:
            return None
        updated = self._adapter.kill(session)
        self._store(updated)
        self._record(updated, ExecutorRuntimeEventType.SESSION_KILLED, "session killed")
        return updated

    def cleanup(self, session_id: str) -> ExecutorRuntimeSession | None:
        session = self.get_session(session_id)
        if session is None:
            return None
        updated = self._adapter.cleanup(session)
        self._store(updated)
        self._record(updated, ExecutorRuntimeEventType.SESSION_CLEANED_UP, "session cleaned up")
        return updated

    def events_for_session(self, session_id: str) -> RuntimeEventStreamSnapshot:
        return self._event_repository.events_for_session(session_id)

    def _build_blocked_session(
        self,
        request: ExecutorLaunchRequest,
    ) -> ExecutorRuntimeSession:
        now = self._clock()
        return ExecutorRuntimeSession(
            session_id=_new_id("runtime-session"),
            executor_id=request.executor_id,
            launch_preview_id=request.launch_preview_id,
            project_id=request.project_id,
            task_id=request.task_id,
            run_id=request.run_id,
            state=ExecutorRuntimeState.BLOCKED,
            source=ExecutorRuntimeSource.FAKE_ADAPTER,
            exit_reason=ExecutorRuntimeExitReason.SAFETY_GATE_BLOCKED,
            blocking_reasons=[reason.value for reason in request.safety_snapshot.blocking_reasons],
            created_by=request.requested_by,
            created_at=now,
            updated_at=now,
        )

    def _store(self, session: ExecutorRuntimeSession) -> None:
        self._session_repository.save(session)

    def _record(
        self,
        session: ExecutorRuntimeSession,
        event_type: ExecutorRuntimeEventType,
        message: str,
    ) -> RuntimeEvent:
        return self._event_repository.append(
            RuntimeEvent(
                event_id=_new_id("runtime-event"),
                session_id=session.session_id,
                event_type=event_type,
                timestamp=self._clock(),
                payload=RuntimeEventPayload(message=message, state=session.state),
            ),
        )


def _event_type_for_state(state: ExecutorRuntimeState) -> ExecutorRuntimeEventType:
    event_map = {
        ExecutorRuntimeState.IDLE: ExecutorRuntimeEventType.SESSION_IDLE,
        ExecutorRuntimeState.COMPLETED: ExecutorRuntimeEventType.SESSION_COMPLETED,
        ExecutorRuntimeState.CANCELLED: ExecutorRuntimeEventType.SESSION_CANCELLED,
        ExecutorRuntimeState.KILLED: ExecutorRuntimeEventType.SESSION_KILLED,
        ExecutorRuntimeState.CLEANED_UP: ExecutorRuntimeEventType.SESSION_CLEANED_UP,
    }
    return event_map.get(state, ExecutorRuntimeEventType.SESSION_AUDIT_NOTE)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
