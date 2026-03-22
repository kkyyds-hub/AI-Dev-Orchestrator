"""Budget guard helpers for Day 15."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.core.config import settings
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.run import (
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunFailureCategory,
)
from app.domain.task import TaskRiskLevel
from app.repositories.run_repository import RunRepository


_SESSION_STARTED_AT = utc_now()
_WARNING_USAGE_RATIO = 0.6
_CRITICAL_USAGE_RATIO = 0.85


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
    daily_usage_ratio: float
    daily_budget_exceeded: bool
    daily_window_started_at: datetime
    session_budget_usd: float
    session_cost_used: float
    session_cost_remaining: float
    session_usage_ratio: float
    session_budget_exceeded: bool
    session_started_at: datetime
    max_task_retries: int
    pressure_level: RunBudgetPressureLevel
    suggested_action: RunBudgetStrategyAction
    strategy_code: str
    strategy_label: str
    strategy_summary: str
    preferred_model_tier: str
    budget_blocked_runs_daily: int
    budget_blocked_runs_session: int


@dataclass(slots=True, frozen=True)
class BudgetRoutingDirective:
    """Router-facing adjustment generated from the current budget pressure."""

    pressure_level: RunBudgetPressureLevel
    suggested_action: RunBudgetStrategyAction
    strategy_code: str
    preferred_model_tier: str
    score_adjustment: float
    detail: str


@dataclass(slots=True, frozen=True)
class BudgetGuardDecision:
    """Budget and retry decision before a worker starts execution."""

    allowed: bool
    summary: str | None
    failure_category: RunFailureCategory | None
    pressure_level: RunBudgetPressureLevel
    suggested_action: RunBudgetStrategyAction
    strategy_code: str
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
                pressure_level=budget_snapshot.pressure_level,
                suggested_action=RunBudgetStrategyAction.BLOCK,
                strategy_code="bg-retry-limit",
                budget=budget_snapshot,
                retry_status=retry_status,
            )

        if budget_snapshot.pressure_level == RunBudgetPressureLevel.BLOCKED:
            failure_category = (
                RunFailureCategory.DAILY_BUDGET_EXCEEDED
                if budget_snapshot.daily_budget_exceeded
                else RunFailureCategory.SESSION_BUDGET_EXCEEDED
            )
            return BudgetGuardDecision(
                allowed=False,
                summary=(
                    "Budget guard blocked execution because budget pressure reached "
                    f"'{budget_snapshot.pressure_level.value}'. "
                    f"{budget_snapshot.strategy_summary}"
                ),
                failure_category=failure_category,
                pressure_level=budget_snapshot.pressure_level,
                suggested_action=budget_snapshot.suggested_action,
                strategy_code=budget_snapshot.strategy_code,
                budget=budget_snapshot,
                retry_status=retry_status,
            )

        summary = None
        if budget_snapshot.suggested_action != RunBudgetStrategyAction.FULL_SPEED:
            summary = (
                "Budget guard allowed execution under conservative mode. "
                f"{budget_snapshot.strategy_summary}"
            )

        return BudgetGuardDecision(
            allowed=True,
            summary=summary,
            failure_category=None,
            pressure_level=budget_snapshot.pressure_level,
            suggested_action=budget_snapshot.suggested_action,
            strategy_code=budget_snapshot.strategy_code,
            budget=budget_snapshot,
            retry_status=retry_status,
        )

    def build_routing_directive(
        self,
        *,
        risk_level: TaskRiskLevel,
        execution_attempts: int,
        recent_failure_count: int,
        snapshot: BudgetSnapshot | None = None,
    ) -> BudgetRoutingDirective:
        """Return one router-facing budget adjustment directive."""

        budget_snapshot = snapshot or self.build_budget_snapshot()
        pressure_level = budget_snapshot.pressure_level

        if pressure_level == RunBudgetPressureLevel.NORMAL:
            return BudgetRoutingDirective(
                pressure_level=pressure_level,
                suggested_action=budget_snapshot.suggested_action,
                strategy_code=budget_snapshot.strategy_code,
                preferred_model_tier=budget_snapshot.preferred_model_tier,
                score_adjustment=0.0,
                detail=(
                    "budget pressure is normal; no additional routing penalty applied."
                ),
            )

        if pressure_level == RunBudgetPressureLevel.WARNING:
            risk_penalty = {
                TaskRiskLevel.LOW: 0.0,
                TaskRiskLevel.NORMAL: -10.0,
                TaskRiskLevel.HIGH: -25.0,
            }[risk_level]
            retry_penalty = -5.0 * execution_attempts
            total_adjustment = risk_penalty + retry_penalty
            return BudgetRoutingDirective(
                pressure_level=pressure_level,
                suggested_action=budget_snapshot.suggested_action,
                strategy_code=budget_snapshot.strategy_code,
                preferred_model_tier=budget_snapshot.preferred_model_tier,
                score_adjustment=total_adjustment,
                detail=(
                    "budget warning active; "
                    f"risk_penalty={risk_penalty:+.1f}, "
                    f"retry_penalty={retry_penalty:+.1f}, "
                    f"total={total_adjustment:+.1f}"
                ),
            )

        if pressure_level == RunBudgetPressureLevel.CRITICAL:
            risk_penalty = {
                TaskRiskLevel.LOW: -5.0,
                TaskRiskLevel.NORMAL: -20.0,
                TaskRiskLevel.HIGH: -60.0,
            }[risk_level]
            retry_penalty = -10.0 * execution_attempts
            failure_penalty = -10.0 * recent_failure_count
            total_adjustment = risk_penalty + retry_penalty + failure_penalty
            return BudgetRoutingDirective(
                pressure_level=pressure_level,
                suggested_action=budget_snapshot.suggested_action,
                strategy_code=budget_snapshot.strategy_code,
                preferred_model_tier=budget_snapshot.preferred_model_tier,
                score_adjustment=total_adjustment,
                detail=(
                    "budget critical mode; "
                    f"risk_penalty={risk_penalty:+.1f}, "
                    f"retry_penalty={retry_penalty:+.1f}, "
                    f"recent_failure_penalty={failure_penalty:+.1f}, "
                    f"total={total_adjustment:+.1f}"
                ),
            )

        return BudgetRoutingDirective(
            pressure_level=pressure_level,
            suggested_action=budget_snapshot.suggested_action,
            strategy_code=budget_snapshot.strategy_code,
            preferred_model_tier=budget_snapshot.preferred_model_tier,
            score_adjustment=-500.0,
            detail=(
                "budget blocked mode; hard routing penalty applied. "
                "execution is expected to be blocked by the guard."
            ),
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
        session_cost_used = _round_currency(
            self.run_repository.sum_estimated_cost_since(_SESSION_STARTED_AT)
        )

        daily_cost_remaining = _round_currency(
            max(settings.daily_budget_usd - daily_cost_used, 0.0)
        )
        session_cost_remaining = _round_currency(
            max(settings.session_budget_usd - session_cost_used, 0.0)
        )
        daily_usage_ratio = _calculate_usage_ratio(
            used=daily_cost_used,
            budget=settings.daily_budget_usd,
        )
        session_usage_ratio = _calculate_usage_ratio(
            used=session_cost_used,
            budget=settings.session_budget_usd,
        )
        daily_budget_exceeded = daily_cost_used >= settings.daily_budget_usd
        session_budget_exceeded = session_cost_used >= settings.session_budget_usd
        pressure_level = _determine_pressure_level(
            daily_budget_exceeded=daily_budget_exceeded,
            session_budget_exceeded=session_budget_exceeded,
            daily_usage_ratio=daily_usage_ratio,
            session_usage_ratio=session_usage_ratio,
        )
        strategy = _strategy_by_pressure_level(pressure_level)
        budget_blocked_runs_daily = self.run_repository.count_budget_blocked_runs_since(
            daily_window_started_at
        )
        budget_blocked_runs_session = self.run_repository.count_budget_blocked_runs_since(
            _SESSION_STARTED_AT
        )

        return BudgetSnapshot(
            daily_budget_usd=settings.daily_budget_usd,
            daily_cost_used=daily_cost_used,
            daily_cost_remaining=daily_cost_remaining,
            daily_usage_ratio=daily_usage_ratio,
            daily_budget_exceeded=daily_budget_exceeded,
            daily_window_started_at=daily_window_started_at,
            session_budget_usd=settings.session_budget_usd,
            session_cost_used=session_cost_used,
            session_cost_remaining=session_cost_remaining,
            session_usage_ratio=session_usage_ratio,
            session_budget_exceeded=session_budget_exceeded,
            session_started_at=_SESSION_STARTED_AT,
            max_task_retries=settings.max_task_retries,
            pressure_level=pressure_level,
            suggested_action=strategy.action,
            strategy_code=strategy.code,
            strategy_label=strategy.label,
            strategy_summary=strategy.summary,
            preferred_model_tier=_preferred_model_tier_by_pressure_level(pressure_level),
            budget_blocked_runs_daily=budget_blocked_runs_daily,
            budget_blocked_runs_session=budget_blocked_runs_session,
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


def _calculate_usage_ratio(*, used: float, budget: float) -> float:
    """Return a stable usage ratio in [0, +inf), rounded for UI display."""

    if budget <= 0:
        return 1.0

    return round(max(used / budget, 0.0), 4)


def _determine_pressure_level(
    *,
    daily_budget_exceeded: bool,
    session_budget_exceeded: bool,
    daily_usage_ratio: float,
    session_usage_ratio: float,
) -> RunBudgetPressureLevel:
    """Normalize budget usage into one of the four V2-B pressure levels."""

    if daily_budget_exceeded or session_budget_exceeded:
        return RunBudgetPressureLevel.BLOCKED

    max_usage_ratio = max(daily_usage_ratio, session_usage_ratio)
    if max_usage_ratio >= _CRITICAL_USAGE_RATIO:
        return RunBudgetPressureLevel.CRITICAL
    if max_usage_ratio >= _WARNING_USAGE_RATIO:
        return RunBudgetPressureLevel.WARNING

    return RunBudgetPressureLevel.NORMAL


@dataclass(slots=True, frozen=True)
class _BudgetStrategy:
    """Static strategy metadata derived from one pressure level."""

    code: str
    label: str
    action: RunBudgetStrategyAction
    summary: str


def _strategy_by_pressure_level(pressure_level: RunBudgetPressureLevel) -> _BudgetStrategy:
    """Return one explainable strategy descriptor for the current pressure level."""

    if pressure_level == RunBudgetPressureLevel.WARNING:
        return _BudgetStrategy(
            code="bg-warning-conservative",
            label="预警保守",
            action=RunBudgetStrategyAction.CONSERVATIVE,
            summary=(
                "预算进入预警区间（>=60%）：路由将降低高风险与高重试任务优先级。"
            ),
        )

    if pressure_level == RunBudgetPressureLevel.CRITICAL:
        return _BudgetStrategy(
            code="bg-critical-degraded",
            label="临界降级",
            action=RunBudgetStrategyAction.DEGRADED,
            summary=(
                "预算进入临界区间（>=85%）：路由强烈偏向低风险任务，并加重失败与重试惩罚。"
            ),
        )

    if pressure_level == RunBudgetPressureLevel.BLOCKED:
        return _BudgetStrategy(
            code="bg-blocked-stop",
            label="超限阻断",
            action=RunBudgetStrategyAction.BLOCK,
            summary=(
                "预算已超限：Worker 会阻断新执行并写入明确失败原因。"
            ),
        )

    return _BudgetStrategy(
        code="bg-normal-full-speed",
        label="正常执行",
        action=RunBudgetStrategyAction.FULL_SPEED,
        summary=(
            "预算健康：系统按常规路由与执行策略运行。"
        ),
    )


def _preferred_model_tier_by_pressure_level(
    pressure_level: RunBudgetPressureLevel,
) -> str:
    """Return the baseline model tier implied by the current budget pressure."""

    if pressure_level in {
        RunBudgetPressureLevel.CRITICAL,
        RunBudgetPressureLevel.BLOCKED,
    }:
        return "economy"

    return "balanced"
