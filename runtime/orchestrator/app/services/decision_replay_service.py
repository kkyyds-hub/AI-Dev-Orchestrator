"""Decision replay helpers built on structured run logs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.run import Run, RunFailureCategory, RunStatus
from app.services.failure_review_service import FailureReviewRecord, FailureReviewService
from app.services.run_logging_service import RunLogEvent, RunLoggingService


_TRACE_EVENT_MAPPING = {
    "task_routed": ("routing", "任务路由"),
    "role_handoff": ("handoff", "角色接力"),
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

_PROJECT_TIMELINE_EVENT_TYPES = {
    "role_handoff": "role_handoff",
    "task_routed": "decision",
    "guard_blocked": "decision",
    "execution_finished": "decision",
    "verification_finished": "decision",
    "verification_skipped": "decision",
    "run_finalized": "decision",
    "run_recovered": "decision",
    "worker_rolled_back": "decision",
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


@dataclass(slots=True, frozen=True)
class ProjectDecisionTimelineEntry:
    """One run-log event normalized for the Day11 project timeline."""

    timeline_type: str
    occurred_at: datetime
    task_id: UUID
    task_title: str | None
    run_id: UUID
    run_status: RunStatus
    trace_item: DecisionTraceItem


@dataclass(slots=True, frozen=True)
class ProjectFailureRetrospectiveItem:
    """One failed / blocked run summarized for the Day12 project retrospective."""

    run_id: UUID
    task_id: UUID
    task_title: str | None
    created_at: datetime
    run_status: RunStatus
    failure_category: RunFailureCategory | None
    headline: str
    stages: list[str]
    failure_review: FailureReviewRecord | None


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

    def build_project_timeline_entries(
        self,
        *,
        runs: list[Run],
        task_titles: dict[UUID, str] | None = None,
    ) -> list[ProjectDecisionTimelineEntry]:
        """Flatten run logs into project-level decision / handoff timeline entries."""

        title_map = task_titles or {}
        timeline_entries: list[ProjectDecisionTimelineEntry] = []

        for run in runs:
            log_result = self.run_logging_service.read_events(log_path=run.log_path, limit=200)
            for event in log_result.events:
                timeline_type = _PROJECT_TIMELINE_EVENT_TYPES.get(event.event)
                if timeline_type is None:
                    continue

                trace_item = self._to_trace_item(event)
                timeline_entries.append(
                    ProjectDecisionTimelineEntry(
                        timeline_type=timeline_type,
                        occurred_at=(
                            self._parse_event_timestamp(event.timestamp)
                            or run.finished_at
                            or run.started_at
                            or run.created_at
                        ),
                        task_id=run.task_id,
                        task_title=title_map.get(run.task_id),
                        run_id=run.id,
                        run_status=run.status,
                        trace_item=trace_item,
                    )
                )

        timeline_entries.sort(key=lambda item: item.occurred_at, reverse=True)
        return timeline_entries

    def build_project_failure_history(
        self,
        *,
        runs: list[Run],
        task_titles: dict[UUID, str] | None = None,
        limit: int = 10,
    ) -> list[ProjectFailureRetrospectiveItem]:
        """Return recent failed / cancelled runs for the Day12 retrospective view."""

        title_map = task_titles or {}
        history_items: list[ProjectFailureRetrospectiveItem] = []

        for run in sorted(runs, key=lambda item: item.created_at, reverse=True):
            if run.failure_category is None and run.status not in {
                RunStatus.FAILED,
                RunStatus.CANCELLED,
            }:
                continue

            log_result = self.run_logging_service.read_events(log_path=run.log_path, limit=50)
            trace_items = [self._to_trace_item(event) for event in log_result.events]
            history_items.append(
                ProjectFailureRetrospectiveItem(
                    run_id=run.id,
                    task_id=run.task_id,
                    task_title=title_map.get(run.task_id),
                    created_at=run.created_at,
                    run_status=run.status,
                    failure_category=run.failure_category,
                    headline=self._build_headline(run=run, trace_items=trace_items),
                    stages=list(dict.fromkeys(item.stage for item in trace_items)),
                    failure_review=self.failure_review_service.get_review(run_id=run.id),
                )
            )

        return history_items[:limit]

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

    @staticmethod
    def _parse_event_timestamp(value: str) -> datetime | None:
        """Best-effort parse for ISO timestamps stored inside structured logs."""

        if not value:
            return None

        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
