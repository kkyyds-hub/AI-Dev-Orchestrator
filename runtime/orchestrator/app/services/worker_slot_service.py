"""In-process worker slot tracking for V2-C limited parallel execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import Lock
from uuid import uuid4

from app.core.config import settings
from app.domain._base import ensure_utc_datetime, utc_now
from app.services.event_stream_service import event_stream_service


class WorkerSlotState(StrEnum):
    """Visible state of one worker slot."""

    IDLE = "idle"
    RUNNING = "running"


@dataclass(slots=True, frozen=True)
class WorkerSlotLease:
    """Opaque lease returned when a caller acquires one slot."""

    lease_id: str
    slot_id: int
    worker_name: str
    acquired_at: datetime


@dataclass(slots=True, frozen=True)
class WorkerSlotStatus:
    """Visible state snapshot for one worker slot."""

    slot_id: int
    state: WorkerSlotState
    worker_name: str | None
    task_id: str | None
    task_title: str | None
    run_id: str | None
    acquired_at: datetime | None
    last_task_id: str | None
    last_task_title: str | None
    last_run_id: str | None
    last_released_at: datetime | None


@dataclass(slots=True, frozen=True)
class WorkerSlotSnapshot:
    """Cluster-wide view of all local worker slots."""

    max_concurrent_workers: int
    running_slots: int
    idle_slots: int
    slots: list[WorkerSlotStatus]


@dataclass(slots=True)
class _WorkerSlotRecord:
    """Mutable record held under the service lock."""

    slot_id: int
    state: WorkerSlotState = WorkerSlotState.IDLE
    lease_id: str | None = None
    worker_name: str | None = None
    task_id: str | None = None
    task_title: str | None = None
    run_id: str | None = None
    acquired_at: datetime | None = None
    last_task_id: str | None = None
    last_task_title: str | None = None
    last_run_id: str | None = None
    last_released_at: datetime | None = None


class WorkerSlotService:
    """Track fixed-capacity worker slots inside one FastAPI process."""

    def __init__(self, *, max_slots: int) -> None:
        self._max_slots = max_slots
        self._lock = Lock()
        self._slots = {
            slot_id: _WorkerSlotRecord(slot_id=slot_id)
            for slot_id in range(1, max_slots + 1)
        }

    def acquire(self, *, worker_name: str) -> WorkerSlotLease | None:
        """Claim one idle slot or return `None` if all slots are busy."""

        with self._lock:
            idle_slot = next(
                (slot for slot in self._slots.values() if slot.state == WorkerSlotState.IDLE),
                None,
            )
            if idle_slot is None:
                return None

            acquired_at = utc_now()
            lease = WorkerSlotLease(
                lease_id=str(uuid4()),
                slot_id=idle_slot.slot_id,
                worker_name=worker_name,
                acquired_at=acquired_at,
            )
            idle_slot.state = WorkerSlotState.RUNNING
            idle_slot.lease_id = lease.lease_id
            idle_slot.worker_name = worker_name
            idle_slot.task_id = None
            idle_slot.task_title = None
            idle_slot.run_id = None
            idle_slot.acquired_at = acquired_at

            status = self._to_status(idle_slot)

        self._publish(reason="acquired", slot=status)
        return lease

    def bind_run(
        self,
        *,
        lease: WorkerSlotLease,
        task_id: str | None,
        task_title: str | None,
        run_id: str | None,
    ) -> None:
        """Attach the current task/run identity to one acquired slot."""

        with self._lock:
            slot = self._get_active_slot(lease)
            if slot is None:
                return

            slot.task_id = task_id
            slot.task_title = task_title
            slot.run_id = run_id
            status = self._to_status(slot)

        self._publish(reason="bound", slot=status)

    def release(self, *, lease: WorkerSlotLease) -> None:
        """Release one acquired slot."""

        with self._lock:
            slot = self._get_active_slot(lease)
            if slot is None:
                return

            slot.state = WorkerSlotState.IDLE
            slot.lease_id = None
            slot.last_task_id = slot.task_id
            slot.last_task_title = slot.task_title
            slot.last_run_id = slot.run_id
            slot.last_released_at = utc_now()
            slot.worker_name = None
            slot.task_id = None
            slot.task_title = None
            slot.run_id = None
            slot.acquired_at = None
            status = self._to_status(slot)

        self._publish(reason="released", slot=status)

    def snapshot(self) -> WorkerSlotSnapshot:
        """Return a consistent snapshot of all slot states."""

        with self._lock:
            statuses = [self._to_status(slot) for slot in self._slots.values()]

        running_slots = sum(1 for slot in statuses if slot.state == WorkerSlotState.RUNNING)
        return WorkerSlotSnapshot(
            max_concurrent_workers=self._max_slots,
            running_slots=running_slots,
            idle_slots=self._max_slots - running_slots,
            slots=statuses,
        )

    def _get_active_slot(self, lease: WorkerSlotLease) -> _WorkerSlotRecord | None:
        """Return one slot only if the caller still owns the active lease."""

        slot = self._slots.get(lease.slot_id)
        if slot is None or slot.lease_id != lease.lease_id:
            return None

        return slot

    @staticmethod
    def _to_status(slot: _WorkerSlotRecord) -> WorkerSlotStatus:
        """Convert one mutable slot record into an immutable snapshot."""

        return WorkerSlotStatus(
            slot_id=slot.slot_id,
            state=slot.state,
            worker_name=slot.worker_name,
            task_id=slot.task_id,
            task_title=slot.task_title,
            run_id=slot.run_id,
            acquired_at=ensure_utc_datetime(slot.acquired_at),
            last_task_id=slot.last_task_id,
            last_task_title=slot.last_task_title,
            last_run_id=slot.last_run_id,
            last_released_at=ensure_utc_datetime(slot.last_released_at),
        )

    @staticmethod
    def _publish(*, reason: str, slot: WorkerSlotStatus) -> None:
        """Publish one best-effort SSE update for the slot panel."""

        event_stream_service.publish(
            "worker_slot_updated",
            {
                "reason": reason,
                "slot": {
                    "slot_id": slot.slot_id,
                    "state": slot.state.value,
                    "worker_name": slot.worker_name,
                    "task_id": slot.task_id,
                    "task_title": slot.task_title,
                    "run_id": slot.run_id,
                    "acquired_at": (
                        slot.acquired_at.isoformat() if slot.acquired_at is not None else None
                    ),
                    "last_task_id": slot.last_task_id,
                    "last_task_title": slot.last_task_title,
                    "last_run_id": slot.last_run_id,
                    "last_released_at": (
                        slot.last_released_at.isoformat()
                        if slot.last_released_at is not None
                        else None
                    ),
                },
            },
        )


worker_slot_service = WorkerSlotService(
    max_slots=settings.max_concurrent_workers,
)
