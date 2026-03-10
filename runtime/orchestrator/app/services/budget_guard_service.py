"""Budget guard helpers for Day 15."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.core.config import settings
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.run import RunFailureCategory
from app.repositories.run_repository import RunRepository


_SESSION_STARTED_AT = utc_now()


@dataclass(slots=True, frozen=True)
class RetryStatus:
    """Current retry allowance for one task."""

    execution_attempts: int
    max_task_retries: int
    retries_used: int
    retries_remaining: int
    retry_limit_reached: bool


@dataclass(slots=True, frozen=True)
class BudgetSnapshot:
    """Current Day 15 budget usage snapshot."""

    daily_budget_usd: float
    daily_cost_used: float
    daily_cost_remaining: float
    daily_budget_exceeded: bool
    daily_window_started_at: datetime
    session_budget_usd: float
    session_cost_used: float
    session_cost_remaining: float
    session_budget_exceeded: bool
    session_started_at: datetime
    max_task_retries: int


@dataclass(slots=True, frozen=True)
class BudgetGuardDecision:
    """Budget and retry decision before a worker starts execution."""

    allowed: bool
    summary: str | None
    failure_category: RunFailureCategory | None
    budget: BudgetSnapshot
    retry_status: RetryStatus


class BudgetGuardService:
    """Apply conservative budget and retry checks before execution starts."""

    def __init__(self, run_repository: RunRepository) -> None:
        self.run_repository = run_repository

    def evaluate_before_execution(self, task_id: UUID) -> BudgetGuardDecision:
        """Return whether one task is allowed to continue into execution."""

        retry_status = self.build_retry_status(task_id)
        budget_snapshot = self.build_budget_snapshot()

        if retry_status.retry_limit_reached:
            return BudgetGuardDecision(
                allowed=False,
                summary=(
                    "Budget guard blocked execution because the task exceeded the retry "
                    f"limit. Max retries: {retry_status.max_task_retries}; "
                    f"recorded execution attempts: {retry_status.execution_attempts}."
                ),
                failure_category=RunFailureCategory.RETRY_LIMIT_EXCEEDED,
                budget=budget_snapshot,
                retry_status=retry_status,
            )

        if budget_snapshot.daily_budget_exceeded:
            return BudgetGuardDecision(
                allowed=False,
                summary=(
                    "Budget guard blocked execution because the daily budget is exhausted. "
                    f"Used {budget_snapshot.daily_cost_used:.6f} / "
                    f"{budget_snapshot.daily_budget_usd:.6f} USD."
                ),
                failure_category=RunFailureCategory.DAILY_BUDGET_EXCEEDED,
                budget=budget_snapshot,
                retry_status=retry_status,
            )

        if budget_snapshot.session_budget_exceeded:
            return BudgetGuardDecision(
                allowed=False,
                summary=(
                    "Budget guard blocked execution because the session budget is exhausted. "
                    f"Used {budget_snapshot.session_cost_used:.6f} / "
                    f"{budget_snapshot.session_budget_usd:.6f} USD."
                ),
                failure_category=RunFailureCategory.SESSION_BUDGET_EXCEEDED,
                budget=budget_snapshot,
                retry_status=retry_status,
            )

        return BudgetGuardDecision(
            allowed=True,
            summary=None,
            failure_category=None,
            budget=budget_snapshot,
            retry_status=retry_status,
        )

    def build_budget_snapshot(self, now: datetime | None = None) -> BudgetSnapshot:
        """Return the current day/session budget usage."""

        current_time = ensure_utc_datetime(now) or utc_now()
        daily_window_started_at = current_time.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        daily_cost_used = _round_currency(
            self.run_repository.sum_estimated_cost_since(daily_window_started_at)
        )
        session_cost_used = _round_currency(self.run_repository.sum_estimated_cost_since(
            _SESSION_STARTED_AT
        ))

        daily_cost_remaining = _round_currency(
            max(settings.daily_budget_usd - daily_cost_used, 0.0)
        )
        session_cost_remaining = _round_currency(
            max(settings.session_budget_usd - session_cost_used, 0.0)
        )

        return BudgetSnapshot(
            daily_budget_usd=settings.daily_budget_usd,
            daily_cost_used=daily_cost_used,
            daily_cost_remaining=daily_cost_remaining,
            daily_budget_exceeded=daily_cost_used >= settings.daily_budget_usd,
            daily_window_started_at=daily_window_started_at,
            session_budget_usd=settings.session_budget_usd,
            session_cost_used=session_cost_used,
            session_cost_remaining=session_cost_remaining,
            session_budget_exceeded=session_cost_used >= settings.session_budget_usd,
            session_started_at=_SESSION_STARTED_AT,
            max_task_retries=settings.max_task_retries,
        )

    def build_retry_status(self, task_id: UUID) -> RetryStatus:
        """Return retry usage for one task."""

        execution_attempts = self.run_repository.count_execution_attempts_by_task_id(task_id)
        retries_used = max(execution_attempts - 1, 0)
        retries_remaining = max(settings.max_task_retries - retries_used, 0)

        return RetryStatus(
            execution_attempts=execution_attempts,
            max_task_retries=settings.max_task_retries,
            retries_used=retries_used,
            retries_remaining=retries_remaining,
            retry_limit_reached=execution_attempts > settings.max_task_retries,
        )


def _round_currency(value: float) -> float:
    """Keep UI-facing budget values aligned with persisted cost precision."""

    return round(value, 6)
