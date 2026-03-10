"""Persistence helpers for `Task` records."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db_tables import RunTable, TaskTable
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.run import Run
from app.domain.task import Task, TaskStatus


class TaskRepository:
    """Encapsulate task-related database operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, task: Task) -> Task:
        """Persist a new task and return the stored domain model."""

        task_row = TaskTable(
            id=task.id,
            title=task.title,
            status=task.status,
            priority=task.priority,
            input_summary=task.input_summary,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

        self.session.add(task_row)
        self.session.commit()
        self.session.refresh(task_row)
        return self._to_domain(task_row)

    def list_all(self) -> list[Task]:
        """Return all tasks ordered by creation time descending."""

        statement = select(TaskTable).order_by(TaskTable.created_at.desc())
        task_rows = self.session.execute(statement).scalars().all()
        return [self._to_domain(task_row) for task_row in task_rows]

    def list_with_latest_run(self) -> list[tuple[Task, Run | None]]:
        """Return tasks together with their latest persisted run, if any."""

        statement = (
            select(TaskTable)
            .options(selectinload(TaskTable.runs))
            .order_by(TaskTable.created_at.desc())
        )
        task_rows = self.session.execute(statement).scalars().all()
        return [
            (self._to_domain(task_row), self._latest_run_to_domain(task_row.runs))
            for task_row in task_rows
        ]

    def get_by_id(self, task_id: UUID) -> Task | None:
        """Return a task by ID, if it exists."""

        task_row = self.session.get(TaskTable, task_id)
        if task_row is None:
            return None

        return self._to_domain(task_row)

    def claim_next_pending(self) -> Task | None:
        """Claim the earliest pending task and move it to `running`."""

        statement = (
            select(TaskTable)
            .where(TaskTable.status == TaskStatus.PENDING)
            .order_by(TaskTable.created_at.asc())
            .limit(1)
        )
        task_row = self.session.execute(statement).scalars().first()
        if task_row is None:
            return None

        task_row.status = TaskStatus.RUNNING
        task_row.updated_at = utc_now()
        self.session.flush()
        return self._to_domain(task_row)

    def set_status(self, task_id: UUID, status: TaskStatus) -> Task:
        """Update a task status and return the fresh domain model."""

        task_row = self.session.get(TaskTable, task_id)
        if task_row is None:
            raise ValueError(f"Task not found: {task_id}")

        task_row.status = status
        task_row.updated_at = utc_now()
        self.session.flush()
        return self._to_domain(task_row)

    @staticmethod
    def _to_domain(task_row: TaskTable) -> Task:
        """Convert an ORM task row back into the domain model."""

        return Task(
            id=task_row.id,
            title=task_row.title,
            status=task_row.status,
            priority=task_row.priority,
            input_summary=task_row.input_summary,
            created_at=ensure_utc_datetime(task_row.created_at),
            updated_at=ensure_utc_datetime(task_row.updated_at),
        )

    @staticmethod
    def _latest_run_to_domain(run_rows: list[RunTable]) -> Run | None:
        """Convert the latest ORM run row into the domain model."""

        if not run_rows:
            return None

        latest_run_row = max(run_rows, key=lambda run_row: run_row.created_at)
        return Run(
            id=latest_run_row.id,
            task_id=latest_run_row.task_id,
            status=latest_run_row.status,
            model_name=latest_run_row.model_name,
            started_at=ensure_utc_datetime(latest_run_row.started_at),
            finished_at=ensure_utc_datetime(latest_run_row.finished_at),
            result_summary=latest_run_row.result_summary,
            prompt_tokens=latest_run_row.prompt_tokens,
            completion_tokens=latest_run_row.completion_tokens,
            estimated_cost=latest_run_row.estimated_cost,
            log_path=latest_run_row.log_path,
            created_at=ensure_utc_datetime(latest_run_row.created_at),
        )
