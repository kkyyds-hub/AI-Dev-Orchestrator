"""Persistence helpers for `Run` records."""

from dataclasses import dataclass
import json
from uuid import UUID

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db_tables import RunTable
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.run import (
    Run,
    RunEventReason,
    RunFailureCategory,
    RunRoutingScoreItem,
    RunStatus,
)
from app.services.event_stream_service import event_stream_service


@dataclass(slots=True, frozen=True)
class RunMetricsAggregate:
    """One coarse aggregate snapshot over all persisted runs."""

    total_runs: int
    total_estimated_cost: float
    total_prompt_tokens: int
    total_completion_tokens: int
    avg_estimated_cost: float
    avg_prompt_tokens: float
    avg_completion_tokens: float
    latest_run_created_at: datetime | None


class RunRepository:
    """Encapsulate run-related database operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_running_run(
        self,
        *,
        task_id: UUID,
        model_name: str | None = None,
        route_reason: str | None = None,
        routing_score: float | None = None,
        routing_score_breakdown: list[RunRoutingScoreItem] | None = None,
    ) -> Run:
        """Create a new running `Run` placeholder for the worker cycle."""

        run = Run(
            task_id=task_id,
            status=RunStatus.RUNNING,
            model_name=model_name,
            route_reason=route_reason,
            routing_score=routing_score,
            routing_score_breakdown=routing_score_breakdown or [],
            started_at=utc_now(),
        )

        run_row = RunTable(
            id=run.id,
            task_id=run.task_id,
            status=run.status,
            model_name=run.model_name,
            route_reason=run.route_reason,
            routing_score=run.routing_score,
            routing_score_breakdown=self._serialize_routing_score_breakdown(
                run.routing_score_breakdown
            ),
            started_at=run.started_at,
            finished_at=run.finished_at,
            result_summary=run.result_summary,
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            estimated_cost=run.estimated_cost,
            log_path=run.log_path,
            verification_mode=run.verification_mode,
            verification_template=run.verification_template,
            verification_command=run.verification_command,
            verification_summary=run.verification_summary,
            failure_category=run.failure_category,
            quality_gate_passed=run.quality_gate_passed,
            created_at=run.created_at,
        )

        self.session.add(run_row)
        self.session.flush()
        persisted_run = self._to_domain(run_row)
        event_stream_service.publish_run_updated(
            run=persisted_run,
            reason=RunEventReason.CREATED,
        )
        return persisted_run

    def get_by_id(self, run_id: UUID) -> Run | None:
        """Return a run by ID, if it exists."""

        run_row = self.session.get(RunTable, run_id)
        if run_row is None:
            return None

        return self._to_domain(run_row)

    def list_by_task_id(self, task_id: UUID) -> list[Run]:
        """Return all runs for one task ordered from newest to oldest."""

        statement = (
            select(RunTable)
            .where(RunTable.task_id == task_id)
            .order_by(RunTable.created_at.desc())
        )
        run_rows = self.session.execute(statement).scalars().all()
        return [self._to_domain(run_row) for run_row in run_rows]

    def count_execution_attempts_by_task_id(self, task_id: UUID) -> int:
        """Return the number of non-cancelled runs recorded for one task."""

        statement = select(func.count()).select_from(RunTable).where(
            RunTable.task_id == task_id,
            RunTable.status != RunStatus.CANCELLED,
        )
        return int(self.session.execute(statement).scalar_one())

    def sum_estimated_cost(self) -> float:
        """Return the cumulative estimated cost across all runs."""

        statement = select(func.coalesce(func.sum(RunTable.estimated_cost), 0.0))
        return float(self.session.execute(statement).scalar_one())

    def get_metrics_aggregate(self) -> RunMetricsAggregate:
        """Return one aggregate snapshot used by console metrics endpoints."""

        statement = select(
            func.count(RunTable.id),
            func.coalesce(func.sum(RunTable.estimated_cost), 0.0),
            func.coalesce(func.sum(RunTable.prompt_tokens), 0),
            func.coalesce(func.sum(RunTable.completion_tokens), 0),
            func.coalesce(func.avg(RunTable.estimated_cost), 0.0),
            func.coalesce(func.avg(RunTable.prompt_tokens), 0.0),
            func.coalesce(func.avg(RunTable.completion_tokens), 0.0),
            func.max(RunTable.created_at),
        )
        (
            total_runs,
            total_estimated_cost,
            total_prompt_tokens,
            total_completion_tokens,
            avg_estimated_cost,
            avg_prompt_tokens,
            avg_completion_tokens,
            latest_run_created_at,
        ) = self.session.execute(statement).one()

        return RunMetricsAggregate(
            total_runs=int(total_runs),
            total_estimated_cost=float(total_estimated_cost),
            total_prompt_tokens=int(total_prompt_tokens),
            total_completion_tokens=int(total_completion_tokens),
            avg_estimated_cost=float(avg_estimated_cost),
            avg_prompt_tokens=float(avg_prompt_tokens),
            avg_completion_tokens=float(avg_completion_tokens),
            latest_run_created_at=ensure_utc_datetime(latest_run_created_at),
        )

    def count_runs_grouped_by_status(self) -> dict[RunStatus, int]:
        """Return run counts grouped by run status."""

        statement = (
            select(RunTable.status, func.count(RunTable.id))
            .group_by(RunTable.status)
        )
        rows = self.session.execute(statement).all()
        return {status: int(count) for status, count in rows}

    def count_failure_categories_for_failed_runs(
        self,
    ) -> dict[RunFailureCategory | None, int]:
        """Return failure-category counts for failed/cancelled runs."""

        statement = (
            select(RunTable.failure_category, func.count(RunTable.id))
            .where(RunTable.status.in_([RunStatus.FAILED, RunStatus.CANCELLED]))
            .group_by(RunTable.failure_category)
        )
        rows = self.session.execute(statement).all()
        return {failure_category: int(count) for failure_category, count in rows}

    def count_runs_grouped_by_route_reason(self) -> list[tuple[str, int]]:
        """Return run counts grouped by non-empty route reason text."""

        statement = (
            select(RunTable.route_reason, func.count(RunTable.id))
            .where(
                RunTable.route_reason.is_not(None),
                func.trim(RunTable.route_reason) != "",
            )
            .group_by(RunTable.route_reason)
            .order_by(func.count(RunTable.id).desc(), RunTable.route_reason.asc())
        )
        rows = self.session.execute(statement).all()
        return [(str(route_reason), int(count)) for route_reason, count in rows]

    def sum_estimated_cost_since(self, started_at: datetime) -> float:
        """Return the cumulative estimated cost since one UTC timestamp."""

        statement = (
            select(func.coalesce(func.sum(RunTable.estimated_cost), 0.0))
            .select_from(RunTable)
            .where(RunTable.created_at >= started_at)
        )
        return float(self.session.execute(statement).scalar_one())

    def count_budget_blocked_runs_since(self, started_at: datetime) -> int:
        """Return how many runs were blocked by daily/session budget since one timestamp."""

        statement = select(func.count()).select_from(RunTable).where(
            RunTable.created_at >= started_at,
            RunTable.failure_category.in_(
                [
                    RunFailureCategory.DAILY_BUDGET_EXCEEDED,
                    RunFailureCategory.SESSION_BUDGET_EXCEEDED,
                ]
            ),
        )
        return int(self.session.execute(statement).scalar_one())

    def set_log_path(self, run_id: UUID, log_path: str) -> Run:
        """Persist the relative log path for a run."""

        run_row = self.session.get(RunTable, run_id)
        if run_row is None:
            raise ValueError(f"Run not found: {run_id}")

        run_row.log_path = log_path
        self.session.flush()
        persisted_run = self._to_domain(run_row)
        event_stream_service.publish_run_updated(
            run=persisted_run,
            reason=RunEventReason.LOG_PATH_SET,
        )
        return persisted_run

    def finish_run(
        self,
        run_id: UUID,
        *,
        status: RunStatus,
        result_summary: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        estimated_cost: float = 0.0,
        verification_mode: str | None = None,
        verification_template: str | None = None,
        verification_command: str | None = None,
        verification_summary: str | None = None,
        failure_category: RunFailureCategory | None = None,
        quality_gate_passed: bool | None = None,
    ) -> Run:
        """Finalize a run with summary, token estimate, quality gate and cost."""

        run_row = self.session.get(RunTable, run_id)
        if run_row is None:
            raise ValueError(f"Run not found: {run_id}")

        run_row.status = status
        run_row.result_summary = result_summary
        run_row.prompt_tokens = prompt_tokens
        run_row.completion_tokens = completion_tokens
        run_row.estimated_cost = estimated_cost
        run_row.verification_mode = verification_mode
        run_row.verification_template = verification_template
        run_row.verification_command = verification_command
        run_row.verification_summary = verification_summary
        run_row.failure_category = failure_category
        run_row.quality_gate_passed = quality_gate_passed
        run_row.finished_at = utc_now()
        self.session.flush()

        persisted_run = self._to_domain(run_row)
        event_stream_service.publish_run_updated(
            run=persisted_run,
            reason=RunEventReason.FINISHED,
        )
        return persisted_run

    @staticmethod
    def _serialize_routing_score_breakdown(
        breakdown: list[RunRoutingScoreItem],
    ) -> str:
        """Store one routing-score breakdown list as JSON text."""

        return json.dumps(
            [item.model_dump() for item in breakdown],
            ensure_ascii=False,
        )

    @staticmethod
    def _deserialize_routing_score_breakdown(
        raw_value: str | None,
    ) -> list[RunRoutingScoreItem]:
        """Read one routing-score breakdown list from JSON text."""

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

    @staticmethod
    def _to_domain(run_row: RunTable) -> Run:
        """Convert an ORM row back into the domain model."""

        return Run(
            id=run_row.id,
            task_id=run_row.task_id,
            status=run_row.status,
            model_name=run_row.model_name,
            route_reason=run_row.route_reason,
            routing_score=run_row.routing_score,
            routing_score_breakdown=RunRepository._deserialize_routing_score_breakdown(
                run_row.routing_score_breakdown
            ),
            started_at=ensure_utc_datetime(run_row.started_at),
            finished_at=ensure_utc_datetime(run_row.finished_at),
            result_summary=run_row.result_summary,
            prompt_tokens=run_row.prompt_tokens,
            completion_tokens=run_row.completion_tokens,
            estimated_cost=run_row.estimated_cost,
            log_path=run_row.log_path,
            verification_mode=run_row.verification_mode,
            verification_template=run_row.verification_template,
            verification_command=run_row.verification_command,
            verification_summary=run_row.verification_summary,
            failure_category=run_row.failure_category,
            quality_gate_passed=run_row.quality_gate_passed,
            created_at=ensure_utc_datetime(run_row.created_at),
        )
