"""Budget guard helpers for Day 15."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import json as _json

from sqlalchemy.orm import Session

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

_BUDGET_POLICY_SOURCE_PROJECT = "project_team_control"
_BUDGET_POLICY_SOURCE_DEFAULT = "default_budget_guard"
_BUDGET_POLICY_SOURCE_NONE = "not_configured"


@dataclass(slots=True, frozen=True)
class _ProjectBudgetPolicy:
    """Minimal parsed project budget policy from Team Control Center."""

    hard_stop_enabled: bool
    daily_budget_usd: float
    per_run_budget_usd: float
    source: str  # project_team_control | default_budget_guard | not_configured


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
    budget_policy_source: str = _BUDGET_POLICY_SOURCE_DEFAULT


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
    budget_policy_source: str = _BUDGET_POLICY_SOURCE_DEFAULT


class BudgetGuardService:
    """Apply conservative budget and retry checks before execution starts.

    When a project has a Team Control budget_policy with hard_stop_enabled=true,
    the project-level daily_budget_usd and per_run_budget_usd override the default
    settings.  Without a project policy, the existing default behaviour is preserved.
    """

    def __init__(
        self,
        run_repository: RunRepository,
        db_session: Session | None = None,
    ) -> None:
        self.run_repository = run_repository
        self._db_session = db_session

    # -- Project policy helpers -----------------------------------------------

    def _load_project_budget_policy(
        self,
        project_id: UUID,
    ) -> _ProjectBudgetPolicy:
        """Load and parse the Team Control budget_policy for one project."""
        if self._db_session is None:
            return _ProjectBudgetPolicy(
                hard_stop_enabled=False,
                daily_budget_usd=0.0,
                per_run_budget_usd=0.0,
                source=_BUDGET_POLICY_SOURCE_NONE,
            )

        try:
            from app.core.db_tables import ProjectTable
        except Exception:
            return _ProjectBudgetPolicy(
                hard_stop_enabled=False,
                daily_budget_usd=0.0,
                per_run_budget_usd=0.0,
                source=_BUDGET_POLICY_SOURCE_NONE,
            )

        try:
            row = self._db_session.get(ProjectTable, project_id)
            if row is None:
                return _ProjectBudgetPolicy(
                    hard_stop_enabled=False,
                    daily_budget_usd=0.0,
                    per_run_budget_usd=0.0,
                    source=_BUDGET_POLICY_SOURCE_NONE,
                )

            raw_json = row.budget_policy_json
            if not raw_json or raw_json == "{}":
                return _ProjectBudgetPolicy(
                    hard_stop_enabled=False,
                    daily_budget_usd=0.0,
                    per_run_budget_usd=0.0,
                    source=_BUDGET_POLICY_SOURCE_NONE,
                )

            policy_dict = _json.loads(raw_json)
            if not isinstance(policy_dict, dict) or not policy_dict:
                return _ProjectBudgetPolicy(
                    hard_stop_enabled=False,
                    daily_budget_usd=0.0,
                    per_run_budget_usd=0.0,
                    source=_BUDGET_POLICY_SOURCE_NONE,
                )

            hard_stop = bool(policy_dict.get("hard_stop_enabled", False))
            daily_usd = float(policy_dict.get("daily_budget_usd", 0) or 0)
            per_run_usd = float(policy_dict.get("per_run_budget_usd", 0) or 0)
            source = (
                _BUDGET_POLICY_SOURCE_PROJECT if hard_stop or daily_usd > 0
                else _BUDGET_POLICY_SOURCE_DEFAULT
            )
            return _ProjectBudgetPolicy(
                hard_stop_enabled=hard_stop,
                daily_budget_usd=daily_usd,
                per_run_budget_usd=per_run_usd,
                source=source,
            )
        except Exception:
            return _ProjectBudgetPolicy(
                hard_stop_enabled=False,
                daily_budget_usd=0.0,
                per_run_budget_usd=0.0,
                source=_BUDGET_POLICY_SOURCE_NONE,
            )

    # -- Main guard entry -----------------------------------------------------

    def evaluate_before_execution(
        self,
        task_id: UUID,
        *,
        project_id: UUID | None = None,
    ) -> BudgetGuardDecision:
        """Return whether one task is allowed to continue into execution.

        Args:
            task_id: The task being evaluated.
            project_id: Optional project scope for reading Team Control budget_policy.
        """

        # Load project budget policy if available
        project_policy: _ProjectBudgetPolicy | None = None
        if project_id is not None:
            project_policy = self._load_project_budget_policy(project_id)

        policy_source = (
            project_policy.source if project_policy is not None
            else _BUDGET_POLICY_SOURCE_NONE
        )

        retry_status = self.build_retry_status(task_id)

        # Compute budget with project-level overrides when hard_stop is enabled.
        budget_snapshot = self.build_budget_snapshot(
            project_policy=project_policy if project_policy is not None and project_policy.hard_stop_enabled else None,
        )
        # Stamp the source regardless of hard_stop.
        budget_snapshot = BudgetSnapshot(
            daily_budget_usd=budget_snapshot.daily_budget_usd,
            daily_cost_used=budget_snapshot.daily_cost_used,
            daily_cost_remaining=budget_snapshot.daily_cost_remaining,
            daily_usage_ratio=budget_snapshot.daily_usage_ratio,
            daily_budget_exceeded=budget_snapshot.daily_budget_exceeded,
            daily_window_started_at=budget_snapshot.daily_window_started_at,
            session_budget_usd=budget_snapshot.session_budget_usd,
            session_cost_used=budget_snapshot.session_cost_used,
            session_cost_remaining=budget_snapshot.session_cost_remaining,
            session_usage_ratio=budget_snapshot.session_usage_ratio,
            session_budget_exceeded=budget_snapshot.session_budget_exceeded,
            session_started_at=budget_snapshot.session_started_at,
            max_task_retries=budget_snapshot.max_task_retries,
            pressure_level=budget_snapshot.pressure_level,
            suggested_action=budget_snapshot.suggested_action,
            strategy_code=budget_snapshot.strategy_code,
            strategy_label=budget_snapshot.strategy_label,
            strategy_summary=budget_snapshot.strategy_summary,
            preferred_model_tier=budget_snapshot.preferred_model_tier,
            budget_blocked_runs_daily=budget_snapshot.budget_blocked_runs_daily,
            budget_blocked_runs_session=budget_snapshot.budget_blocked_runs_session,
            budget_policy_source=policy_source,
        )

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
                budget_policy_source=policy_source,
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
                budget_policy_source=policy_source,
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
            budget_policy_source=policy_source,
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

    def build_budget_snapshot(
        self,
        now: datetime | None = None,
        *,
        project_policy: _ProjectBudgetPolicy | None = None,
    ) -> BudgetSnapshot:
        """Return the current day/session budget usage.

        When project_policy is provided and hard_stop_enabled=True, the project's
        daily_budget_usd overrides settings.daily_budget_usd.
        """

        # Determine effective budget limits
        effective_daily_budget = settings.daily_budget_usd
        effective_session_budget = settings.session_budget_usd
        if project_policy is not None and project_policy.hard_stop_enabled:
            if project_policy.daily_budget_usd > 0:
                effective_daily_budget = project_policy.daily_budget_usd
            # per_run_budget_usd is checked in evaluate_before_execution

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
            max(effective_daily_budget - daily_cost_used, 0.0)
        )
        session_cost_remaining = _round_currency(
            max(effective_session_budget - session_cost_used, 0.0)
        )
        daily_usage_ratio = _calculate_usage_ratio(
            used=daily_cost_used,
            budget=effective_daily_budget,
        )
        session_usage_ratio = _calculate_usage_ratio(
            used=session_cost_used,
            budget=effective_session_budget,
        )
        daily_budget_exceeded = daily_cost_used >= effective_daily_budget
        session_budget_exceeded = session_cost_used >= effective_session_budget
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
            daily_budget_usd=effective_daily_budget,
            daily_cost_used=daily_cost_used,
            daily_cost_remaining=daily_cost_remaining,
            daily_usage_ratio=daily_usage_ratio,
            daily_budget_exceeded=daily_budget_exceeded,
            daily_window_started_at=daily_window_started_at,
            session_budget_usd=effective_session_budget,
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
            budget_policy_source=(
                project_policy.source if project_policy is not None
                else _BUDGET_POLICY_SOURCE_DEFAULT
            ),
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
