"""Persistence helpers for `Run` records."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.db_tables import RunTable
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.run import Run, RunStatus


class RunRepository:
    """Encapsulate run-related database operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_running_run(
        self,
        *,
        task_id: UUID,
        model_name: str | None = None,
    ) -> Run:
        """Create a new running `Run` placeholder for the worker cycle."""

        run = Run(
            task_id=task_id,
            status=RunStatus.RUNNING,
            model_name=model_name,
            started_at=utc_now(),
        )

        run_row = RunTable(
            id=run.id,
            task_id=run.task_id,
            status=run.status,
            model_name=run.model_name,
            started_at=run.started_at,
            finished_at=run.finished_at,
            result_summary=run.result_summary,
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            estimated_cost=run.estimated_cost,
            log_path=run.log_path,
            created_at=run.created_at,
        )

        self.session.add(run_row)
        self.session.flush()
        return self._to_domain(run_row)

    def set_log_path(self, run_id: UUID, log_path: str) -> Run:
        """Persist the relative log path for a run."""

        run_row = self.session.get(RunTable, run_id)
        if run_row is None:
            raise ValueError(f"Run not found: {run_id}")

        run_row.log_path = log_path
        self.session.flush()
        return self._to_domain(run_row)

    def finish_run(
        self,
        run_id: UUID,
        *,
        status: RunStatus,
        result_summary: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        estimated_cost: float = 0.0,
    ) -> Run:
        """Finalize a run with summary, token estimate and cost."""

        run_row = self.session.get(RunTable, run_id)
        if run_row is None:
            raise ValueError(f"Run not found: {run_id}")

        run_row.status = status
        run_row.result_summary = result_summary
        run_row.prompt_tokens = prompt_tokens
        run_row.completion_tokens = completion_tokens
        run_row.estimated_cost = estimated_cost
        run_row.finished_at = utc_now()
        self.session.flush()

        return self._to_domain(run_row)

    @staticmethod
    def _to_domain(run_row: RunTable) -> Run:
        """Convert an ORM row back into the domain model."""

        return Run(
            id=run_row.id,
            task_id=run_row.task_id,
            status=run_row.status,
            model_name=run_row.model_name,
            started_at=ensure_utc_datetime(run_row.started_at),
            finished_at=ensure_utc_datetime(run_row.finished_at),
            result_summary=run_row.result_summary,
            prompt_tokens=run_row.prompt_tokens,
            completion_tokens=run_row.completion_tokens,
            estimated_cost=run_row.estimated_cost,
            log_path=run_row.log_path,
            created_at=ensure_utc_datetime(run_row.created_at),
        )
