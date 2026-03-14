"""Console metrics aggregation helpers for V2-B Day 8."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from app.domain.run import (
    RunFailureCategory,
    RunStatus,
)
from app.repositories.run_repository import RunRepository
from app.services.budget_guard_service import BudgetGuardService, BudgetSnapshot


@dataclass(slots=True, frozen=True)
class ConsoleMetricsOverview:
    """Core run/cost metrics displayed by the console overview panels."""

    total_runs: int
    queued_runs: int
    running_runs: int
    succeeded_runs: int
    failed_runs: int
    cancelled_runs: int
    total_estimated_cost: float
    avg_estimated_cost: float
    total_prompt_tokens: int
    total_completion_tokens: int
    avg_prompt_tokens: float
    avg_completion_tokens: float
    latest_run_created_at: datetime | None


@dataclass(slots=True, frozen=True)
class RunStatusDistributionItem:
    """One run-status distribution bucket."""

    status: RunStatus
    label: str
    count: int


@dataclass(slots=True, frozen=True)
class FailureCategoryDistributionItem:
    """One failure-category distribution bucket."""

    category_code: str
    category_label: str
    count: int


@dataclass(slots=True, frozen=True)
class ConsoleFailureDistribution:
    """Failure-focused distribution payload used by Day 8 and Day 9 panels."""

    total_runs: int
    failed_or_cancelled_runs: int
    status_distribution: list[RunStatusDistributionItem]
    failure_category_distribution: list[FailureCategoryDistributionItem]


@dataclass(slots=True, frozen=True)
class RoutingReasonDistributionItem:
    """One coarse routing-reason distribution bucket."""

    reason_code: str
    reason_label: str
    count: int


@dataclass(slots=True, frozen=True)
class ConsoleRoutingDistribution:
    """Routing-reason distribution payload for console observability panels."""

    total_routed_runs: int
    distribution: list[RoutingReasonDistributionItem]


_RUN_STATUS_LABELS: dict[RunStatus, str] = {
    RunStatus.QUEUED: "排队中",
    RunStatus.RUNNING: "运行中",
    RunStatus.SUCCEEDED: "已成功",
    RunStatus.FAILED: "已失败",
    RunStatus.CANCELLED: "已取消",
}

_FAILURE_CATEGORY_LABELS: dict[str, str] = {
    RunFailureCategory.EXECUTION_FAILED.value: "执行失败",
    RunFailureCategory.VERIFICATION_FAILED.value: "验证失败",
    RunFailureCategory.VERIFICATION_CONFIGURATION_FAILED.value: "验证配置失败",
    RunFailureCategory.DAILY_BUDGET_EXCEEDED.value: "日预算超限",
    RunFailureCategory.SESSION_BUDGET_EXCEEDED.value: "会话预算超限",
    RunFailureCategory.RETRY_LIMIT_EXCEEDED.value: "重试上限超限",
    "unknown": "未分类失败",
}

_ROUTING_REASON_LABELS: dict[str, str] = {
    "bg-normal-full-speed": "预算正常执行",
    "bg-warning-conservative": "预算预警保守",
    "bg-critical-degraded": "预算临界降级",
    "bg-blocked-stop": "预算超限阻断",
    "bg-retry-limit": "重试上限阻断",
    "readiness_blocked": "依赖未就绪",
    "ready_routed": "任务就绪可路由",
    "other": "其他原因",
}

_STRATEGY_CODE_PATTERN = re.compile(r"\[(bg-[a-z0-9-]+)\]")


class ConsoleMetricsService:
    """Build stable console metrics payloads from run-level persisted data."""

    def __init__(
        self,
        *,
        run_repository: RunRepository,
        budget_guard_service: BudgetGuardService,
    ) -> None:
        self.run_repository = run_repository
        self.budget_guard_service = budget_guard_service

    def get_metrics(self) -> ConsoleMetricsOverview:
        """Return one compact metrics overview for `/console/metrics`."""

        aggregate = self.run_repository.get_metrics_aggregate()
        status_counts = self.run_repository.count_runs_grouped_by_status()

        return ConsoleMetricsOverview(
            total_runs=aggregate.total_runs,
            queued_runs=status_counts.get(RunStatus.QUEUED, 0),
            running_runs=status_counts.get(RunStatus.RUNNING, 0),
            succeeded_runs=status_counts.get(RunStatus.SUCCEEDED, 0),
            failed_runs=status_counts.get(RunStatus.FAILED, 0),
            cancelled_runs=status_counts.get(RunStatus.CANCELLED, 0),
            total_estimated_cost=_round_metric(aggregate.total_estimated_cost),
            avg_estimated_cost=_round_metric(aggregate.avg_estimated_cost),
            total_prompt_tokens=aggregate.total_prompt_tokens,
            total_completion_tokens=aggregate.total_completion_tokens,
            avg_prompt_tokens=_round_metric(aggregate.avg_prompt_tokens),
            avg_completion_tokens=_round_metric(aggregate.avg_completion_tokens),
            latest_run_created_at=aggregate.latest_run_created_at,
        )

    def get_budget_health(self) -> BudgetSnapshot:
        """Return budget pressure and strategy data for `/console/budget-health`."""

        return self.budget_guard_service.build_budget_snapshot()

    def get_failure_distribution(self) -> ConsoleFailureDistribution:
        """Return failure and status distributions for `/console/failure-distribution`."""

        aggregate = self.run_repository.get_metrics_aggregate()
        status_counts = self.run_repository.count_runs_grouped_by_status()
        failure_category_counts = (
            self.run_repository.count_failure_categories_for_failed_runs()
        )

        failed_or_cancelled_runs = (
            status_counts.get(RunStatus.FAILED, 0)
            + status_counts.get(RunStatus.CANCELLED, 0)
        )
        status_distribution = _build_status_distribution(status_counts)
        failure_category_distribution = _build_failure_category_distribution(
            failure_category_counts
        )

        return ConsoleFailureDistribution(
            total_runs=aggregate.total_runs,
            failed_or_cancelled_runs=failed_or_cancelled_runs,
            status_distribution=status_distribution,
            failure_category_distribution=failure_category_distribution,
        )

    def get_routing_distribution(self) -> ConsoleRoutingDistribution:
        """Return coarse routing reason buckets for `/console/routing-distribution`."""

        raw_reason_rows = self.run_repository.count_runs_grouped_by_route_reason()
        bucket_counts: dict[str, int] = {}
        total_routed_runs = 0

        for route_reason, count in raw_reason_rows:
            reason_code = _normalize_route_reason_code(route_reason)
            bucket_counts[reason_code] = bucket_counts.get(reason_code, 0) + count
            total_routed_runs += count

        distribution = [
            RoutingReasonDistributionItem(
                reason_code=reason_code,
                reason_label=_ROUTING_REASON_LABELS.get(reason_code, "其他原因"),
                count=count,
            )
            for reason_code, count in sorted(
                bucket_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]

        return ConsoleRoutingDistribution(
            total_routed_runs=total_routed_runs,
            distribution=distribution,
        )


def _build_status_distribution(
    status_counts: dict[RunStatus, int],
) -> list[RunStatusDistributionItem]:
    """Convert grouped run status counts into ordered distribution DTOs."""

    return [
        RunStatusDistributionItem(
            status=status,
            label=_RUN_STATUS_LABELS[status],
            count=status_counts.get(status, 0),
        )
        for status in (
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.RUNNING,
            RunStatus.QUEUED,
            RunStatus.SUCCEEDED,
        )
    ]


def _build_failure_category_distribution(
    failure_category_counts: dict[RunFailureCategory | None, int],
) -> list[FailureCategoryDistributionItem]:
    """Convert grouped failure categories into API-ready distribution items."""

    normalized_counts: dict[str, int] = {}
    for category, count in failure_category_counts.items():
        category_code = category.value if category is not None else "unknown"
        normalized_counts[category_code] = normalized_counts.get(category_code, 0) + count

    return [
        FailureCategoryDistributionItem(
            category_code=category_code,
            category_label=_FAILURE_CATEGORY_LABELS.get(category_code, category_code),
            count=count,
        )
        for category_code, count in sorted(
            normalized_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _normalize_route_reason_code(route_reason: str) -> str:
    """Reduce one route_reason text into a stable coarse distribution bucket."""

    strategy_match = _STRATEGY_CODE_PATTERN.search(route_reason)
    if strategy_match:
        return strategy_match.group(1)

    if "readiness=no" in route_reason:
        return "readiness_blocked"
    if "readiness=yes" in route_reason:
        return "ready_routed"

    return "other"


def _round_metric(value: float) -> float:
    """Keep metric precision stable for UI rendering."""

    return round(value, 6)
