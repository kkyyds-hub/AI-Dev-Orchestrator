"""Fixed-capacity worker pool for V2-C limited parallel execution."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from time import monotonic

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.domain.task import TaskStatus
from app.services.run_logging_service import RunLoggingService
from app.services.worker_slot_service import WorkerSlotSnapshot, worker_slot_service
from app.workers.task_worker import WorkerRunResult, build_task_worker


@dataclass(slots=True, frozen=True)
class WorkerPoolRunResult:
    """Summary of one local worker-pool cycle."""

    requested_workers: int
    launched_workers: int
    claimed_runs: int
    idle_workers: int
    results: list[WorkerRunResult]
    slot_snapshot: WorkerSlotSnapshot


class WorkerPool:
    """Run several conservative worker cycles with fixed slot capacity."""

    def __init__(self, *, max_concurrent_workers: int) -> None:
        self.max_concurrent_workers = max_concurrent_workers
        self.run_logging_service = RunLoggingService()

    def run_once(self, *, requested_workers: int | None = None) -> WorkerPoolRunResult:
        """Launch up to the configured number of worker cycles in parallel."""

        desired_workers = requested_workers or self.max_concurrent_workers
        worker_count = max(1, min(desired_workers, self.max_concurrent_workers))
        leases = []
        for index in range(worker_count):
            lease = worker_slot_service.acquire(worker_name=f"worker-{index + 1}")
            if lease is None:
                break

            leases.append(lease)

        if not leases:
            return WorkerPoolRunResult(
                requested_workers=worker_count,
                launched_workers=0,
                claimed_runs=0,
                idle_workers=worker_count,
                results=[],
                slot_snapshot=worker_slot_service.snapshot(),
            )

        with ThreadPoolExecutor(max_workers=len(leases), thread_name_prefix="worker-slot") as pool:
            futures = [pool.submit(self._run_slot, lease) for lease in leases]
            results = [future.result() for future in futures]

        claimed_runs = sum(1 for result in results if result.claimed)
        return WorkerPoolRunResult(
            requested_workers=worker_count,
            launched_workers=len(results),
            claimed_runs=claimed_runs,
            idle_workers=len(results) - claimed_runs,
            results=results,
            slot_snapshot=worker_slot_service.snapshot(),
        )

    def _run_slot(self, lease) -> WorkerRunResult:
        """Execute one worker cycle inside one slot lease."""

        session: Session = SessionLocal()
        started_at = monotonic()
        try:
            worker = build_task_worker(session=session)
            result = worker.run_once()
            if result.task is not None or result.run is not None:
                worker_slot_service.bind_run(
                    lease=lease,
                    task_id=str(result.task.id) if result.task is not None else None,
                    task_title=result.task.title if result.task is not None else None,
                    run_id=str(result.run.id) if result.run is not None else None,
                )

            if result.run is not None and result.run.log_path is not None:
                self.run_logging_service.append_event(
                    log_path=result.run.log_path,
                    event="worker_slot_assigned",
                    message="Worker pool recorded which fixed slot handled this run.",
                    data={
                        "slot_id": lease.slot_id,
                        "worker_name": lease.worker_name,
                        "claimed": result.claimed,
                        "task_status": result.task.status if result.task is not None else None,
                        "run_status": result.run.status,
                    },
                )
            return result
        finally:
            snapshot_before_release = worker_slot_service.snapshot()
            bound_slot = next(
                (slot for slot in snapshot_before_release.slots if slot.slot_id == lease.slot_id),
                None,
            )
            if bound_slot is not None and bound_slot.run_id is not None:
                run_log_path = self._resolve_run_log_path(session=session, run_id=bound_slot.run_id)
                if run_log_path is not None:
                    self.run_logging_service.append_event(
                        log_path=run_log_path,
                        event="worker_slot_released",
                        message="Worker slot finished processing and returned to the idle pool.",
                        data={
                            "slot_id": lease.slot_id,
                            "worker_name": lease.worker_name,
                            "duration_seconds": round(monotonic() - started_at, 3),
                        },
                    )

            worker_slot_service.release(lease=lease)
            session.close()

    @staticmethod
    def _resolve_run_log_path(*, session: Session, run_id: str) -> str | None:
        """Fetch the persisted log path for one run after the slot finished."""

        from uuid import UUID

        from app.repositories.run_repository import RunRepository

        run = RunRepository(session).get_by_id(UUID(run_id))
        return run.log_path if run is not None else None


worker_pool = WorkerPool(
    max_concurrent_workers=settings.max_concurrent_workers,
)
