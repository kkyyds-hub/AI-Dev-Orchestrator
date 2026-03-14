"""Decision replay helpers built on structured run logs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.run import Run, RunFailureCategory, RunStatus
from app.services.failure_review_service import FailureReviewRecord, FailureReviewService
from app.services.run_logging_service import RunLogEvent, RunLoggingService


_TRACE_EVENT_MAPPING = {
    "task_routed": ("routing", "任务路由"),
    "run_claimed": ("claim", "任务领取"),
    "context_built": ("context", "上下文构建"),
    "guard_blocked": ("guard", "预算 / 重试守卫"),
    "execution_finished": ("execution", "执行结果"),
    "verification_finished": ("verification", "验证结果"),
    "verification_skipped": ("verification", "验证跳过"),
    "cost_estimated": ("cost", "成本估算"),
    "run_finalized": ("finalize", "最终收口"),
    "run_recovered": ("recovery", "故障恢复"),
    "worker_slot_assigned": ("parallel", "槽位分配"),
    "worker_slot_released": ("parallel", "槽位释放"),
    "worker_rolled_back": ("recovery", "异常回滚"),
}


@dataclass(slots=True, frozen=True)
class DecisionTraceItem:
    """One normalized timeline item in the decision replay view."""

    timestamp: str
    stage: str
    title: str
    event: str
    level: str
    summary: str
    data: dict[str, Any]


@dataclass(slots=True, frozen=True)
class DecisionTrace:
    """Decision replay payload for one persisted run."""

    run_id: UUID
    task_id: UUID
    run_status: RunStatus
    failure_category: RunFailureCategory | None
    quality_gate_passed: bool | None
    trace_items: list[DecisionTraceItem]
    failure_review: FailureReviewRecord | None


@dataclass(slots=True, frozen=True)
class DecisionHistoryItem:
    """One task-level historical decision trace summary."""

    run_id: UUID
    status: RunStatus
    failure_category: RunFailureCategory | None
    quality_gate_passed: bool | None
    created_at: str
    headline: str
    stages: list[str]


class DecisionReplayService:
    """Transform structured JSONL logs into replay-friendly views."""

    def __init__(
        self,
        *,
        run_logging_service: RunLoggingService,
        failure_review_service: FailureReviewService,
    ) -> None:
        self.run_logging_service = run_logging_service
        self.failure_review_service = failure_review_service

    def build_run_trace(self, *, run: Run) -> DecisionTrace:
        """Build one replay timeline for a finalized run."""

        log_result = self.run_logging_service.read_events(log_path=run.log_path, limit=200)
        trace_items = [self._to_trace_item(event) for event in log_result.events]
        failure_review = self.failure_review_service.get_review(run_id=run.id)
        return DecisionTrace(
            run_id=run.id,
            task_id=run.task_id,
            run_status=run.status,
            failure_category=run.failure_category,
            quality_gate_passed=run.quality_gate_passed,
            trace_items=trace_items,
            failure_review=failure_review,
        )

    def build_task_history(self, *, runs: list[Run]) -> list[DecisionHistoryItem]:
        """Build one lightweight decision history for all runs of a task."""

        history_items: list[DecisionHistoryItem] = []
        for run in runs:
            log_result = self.run_logging_service.read_events(log_path=run.log_path, limit=50)
            trace_items = [self._to_trace_item(event) for event in log_result.events]
            history_items.append(
                DecisionHistoryItem(
                    run_id=run.id,
                    status=run.status,
                    failure_category=run.failure_category,
                    quality_gate_passed=run.quality_gate_passed,
                    created_at=run.created_at.isoformat(),
                    headline=self._build_headline(run=run, trace_items=trace_items),
                    stages=list(dict.fromkeys(item.stage for item in trace_items)),
                )
            )

        return history_items

    @staticmethod
    def _to_trace_item(event: RunLogEvent) -> DecisionTraceItem:
        """Map one raw log event into a higher-level decision trace node."""

        stage, title = _TRACE_EVENT_MAPPING.get(
            event.event,
            ("runtime", event.event.replace("_", " ").strip() or "运行事件"),
        )
        return DecisionTraceItem(
            timestamp=event.timestamp,
            stage=stage,
            title=title,
            event=event.event,
            level=event.level,
            summary=event.message,
            data=event.data,
        )

    @staticmethod
    def _build_headline(
        *,
        run: Run,
        trace_items: list[DecisionTraceItem],
    ) -> str:
        """Choose one short headline for task-level decision history."""

        if run.failure_category is not None:
            return f"{run.failure_category.value}: {run.result_summary or 'No run summary.'}"

        if trace_items:
            return trace_items[-1].summary

        return run.result_summary or f"Run finished with status {run.status.value}."
