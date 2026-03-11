"""Persistence helpers for `Task` records."""

import json
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.core.db_tables import RunTable, TaskTable
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.run import Run, RunRoutingScoreItem
from app.domain.task import Task, TaskEventReason, TaskHumanStatus, TaskStatus
from app.services.event_stream_service import event_stream_service


_UNCHANGED = object()


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
            acceptance_criteria=self._serialize_string_list(task.acceptance_criteria),
            depends_on_task_ids=self._serialize_uuid_list(task.depends_on_task_ids),
            risk_level=task.risk_level,
            human_status=task.human_status,
            paused_reason=task.paused_reason,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

        self.session.add(task_row)
        self.session.commit()
        self.session.refresh(task_row)
        task = self._to_domain(task_row)
        event_stream_service.publish_task_updated(
            task=task,
            reason=TaskEventReason.CREATED,
        )
        return task

    def list_all(self) -> list[Task]:
        """Return all tasks ordered by creation time descending."""

        statement = select(TaskTable).order_by(TaskTable.created_at.desc())
        task_rows = self.session.execute(statement).scalars().all()
        return [self._to_domain(task_row) for task_row in task_rows]

    def list_pending(self) -> list[Task]:
        """Return all pending tasks ordered from oldest to newest."""

        statement = (
            select(TaskTable)
            .where(TaskTable.status == TaskStatus.PENDING)
            .order_by(TaskTable.created_at.asc())
        )
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

    def get_existing_ids(self, task_ids: list[UUID]) -> set[UUID]:
        """Return the subset of task IDs that already exists."""

        if not task_ids:
            return set()

        statement = select(TaskTable.id).where(TaskTable.id.in_(task_ids))
        return set(self.session.execute(statement).scalars().all())

    def get_by_ids(self, task_ids: list[UUID]) -> dict[UUID, Task]:
        """Return existing tasks keyed by ID while preserving caller ordering outside."""

        if not task_ids:
            return {}

        statement = select(TaskTable).where(TaskTable.id.in_(task_ids))
        task_rows = self.session.execute(statement).scalars().all()
        return {task_row.id: self._to_domain(task_row) for task_row in task_rows}

    def claim_next_pending(self) -> Task | None:
        """Claim the earliest dependency-ready pending task and move it to `running`."""

        statement = (
            select(TaskTable)
            .where(TaskTable.status == TaskStatus.PENDING)
            .order_by(TaskTable.created_at.asc())
        )
        pending_task_rows = self.session.execute(statement).scalars().all()
        if not pending_task_rows:
            return None

        dependency_ids = {
            dependency_id
            for task_row in pending_task_rows
            for dependency_id in self._deserialize_uuid_list(task_row.depends_on_task_ids)
        }
        dependency_status_map = self._build_dependency_status_map(dependency_ids)

        task_row = next(
            (
                candidate
                for candidate in pending_task_rows
                if self._dependencies_completed(
                    self._deserialize_uuid_list(candidate.depends_on_task_ids),
                    dependency_status_map,
                )
            ),
            None,
        )
        if task_row is None:
            return None

        task_row.status = TaskStatus.RUNNING
        task_row.updated_at = utc_now()
        self.session.flush()
        return self._to_domain(task_row)

    def claim_pending_task(self, task_id: UUID) -> Task | None:
        """Claim one specific pending task if it is still claimable."""

        statement = (
            update(TaskTable)
            .where(
                TaskTable.id == task_id,
                TaskTable.status == TaskStatus.PENDING,
            )
            .values(
                status=TaskStatus.RUNNING,
                updated_at=utc_now(),
            )
        )
        result = self.session.execute(statement)
        if result.rowcount == 0:
            return None

        self.session.flush()
        task_row = self.session.get(TaskTable, task_id)
        return self._to_domain(task_row) if task_row is not None else None

    def set_status(self, task_id: UUID, status: TaskStatus) -> Task:
        """Update a task status and return the fresh domain model."""

        task_row = self.session.get(TaskTable, task_id)
        if task_row is None:
            raise ValueError(f"Task not found: {task_id}")

        task_row.status = status
        task_row.updated_at = utc_now()
        self.session.flush()
        return self._to_domain(task_row)

    def update_control_state(
        self,
        task_id: UUID,
        *,
        status: TaskStatus | None = None,
        human_status: TaskHumanStatus | None = None,
        paused_reason: str | None | object = _UNCHANGED,
    ) -> Task:
        """Update task control-state fields and return the fresh domain model."""

        task_row = self.session.get(TaskTable, task_id)
        if task_row is None:
            raise ValueError(f"Task not found: {task_id}")

        if status is not None:
            task_row.status = status
        if human_status is not None:
            task_row.human_status = human_status
        if paused_reason is not _UNCHANGED:
            task_row.paused_reason = paused_reason

        task_row.updated_at = utc_now()
        self.session.flush()
        return self._to_domain(task_row)

    def _to_domain(self, task_row: TaskTable) -> Task:
        """Convert an ORM task row back into the domain model."""

        return Task(
            id=task_row.id,
            title=task_row.title,
            status=task_row.status,
            priority=task_row.priority,
            input_summary=task_row.input_summary,
            acceptance_criteria=self._deserialize_string_list(
                task_row.acceptance_criteria
            ),
            depends_on_task_ids=self._deserialize_uuid_list(
                task_row.depends_on_task_ids
            ),
            risk_level=task_row.risk_level,
            human_status=task_row.human_status,
            paused_reason=task_row.paused_reason,
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
            route_reason=latest_run_row.route_reason,
            routing_score=latest_run_row.routing_score,
            routing_score_breakdown=TaskRepository._deserialize_routing_score_breakdown(
                latest_run_row.routing_score_breakdown
            ),
            started_at=ensure_utc_datetime(latest_run_row.started_at),
            finished_at=ensure_utc_datetime(latest_run_row.finished_at),
            result_summary=latest_run_row.result_summary,
            prompt_tokens=latest_run_row.prompt_tokens,
            completion_tokens=latest_run_row.completion_tokens,
            estimated_cost=latest_run_row.estimated_cost,
            log_path=latest_run_row.log_path,
            verification_mode=latest_run_row.verification_mode,
            verification_template=latest_run_row.verification_template,
            verification_command=latest_run_row.verification_command,
            verification_summary=latest_run_row.verification_summary,
            failure_category=latest_run_row.failure_category,
            quality_gate_passed=latest_run_row.quality_gate_passed,
            created_at=ensure_utc_datetime(latest_run_row.created_at),
        )

    def _build_dependency_status_map(
        self,
        dependency_ids: set[UUID],
    ) -> dict[UUID, TaskStatus]:
        """Load one status snapshot for all dependency task IDs."""

        if not dependency_ids:
            return {}

        statement = select(TaskTable.id, TaskTable.status).where(
            TaskTable.id.in_(dependency_ids)
        )
        rows = self.session.execute(statement).all()
        return {task_id: task_status for task_id, task_status in rows}

    @staticmethod
    def _dependencies_completed(
        dependency_ids: list[UUID],
        dependency_status_map: dict[UUID, TaskStatus],
    ) -> bool:
        """Return whether all referenced dependencies have completed."""

        return all(
            dependency_status_map.get(dependency_id) == TaskStatus.COMPLETED
            for dependency_id in dependency_ids
        )

    @staticmethod
    def _serialize_string_list(values: list[str]) -> str:
        """Store one string list as JSON text in SQLite."""

        return json.dumps(values, ensure_ascii=False)

    @staticmethod
    def _deserialize_string_list(raw_value: str | None) -> list[str]:
        """Read one JSON-encoded string list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        return [str(item).strip() for item in decoded_value if str(item).strip()]

    @staticmethod
    def _serialize_uuid_list(values: list[UUID]) -> str:
        """Store one UUID list as JSON text in SQLite."""

        return json.dumps([str(value) for value in values], ensure_ascii=False)

    @staticmethod
    def _deserialize_uuid_list(raw_value: str | None) -> list[UUID]:
        """Read one JSON-encoded UUID list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_ids: list[UUID] = []
        for item in decoded_value:
            try:
                normalized_ids.append(UUID(str(item)))
            except ValueError:
                continue

        return normalized_ids

    @staticmethod
    def _deserialize_routing_score_breakdown(
        raw_value: str | None,
    ) -> list[RunRoutingScoreItem]:
        """Read one JSON-encoded routing-score breakdown list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded, list):
            return []

        normalized_items: list[RunRoutingScoreItem] = []
        for item in decoded:
            if not isinstance(item, dict):
                continue
            try:
                normalized_items.append(RunRoutingScoreItem.model_validate(item))
            except ValueError:
                continue

        return normalized_items
