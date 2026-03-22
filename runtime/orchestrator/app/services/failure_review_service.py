"""Failure review generation and clustering for V2-C."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.run import Run, RunFailureCategory, RunStatus
from app.domain.task import Task, TaskStatus
from app.repositories.failure_review_repository import FailureReviewRepository
from app.services.run_logging_service import RunLoggingService


@dataclass(slots=True, frozen=True)
class FailureReviewRecord:
    """Persisted minimum review record for one failed or blocked run."""

    review_id: str
    task_id: UUID
    task_title: str
    task_status: TaskStatus
    run_id: UUID
    run_status: RunStatus
    created_at: datetime
    failure_category: RunFailureCategory | None
    quality_gate_passed: bool | None
    route_reason: str | None
    result_summary: str | None
    log_path: str | None
    evidence_events: list[str]
    action_summary: str
    conclusion: str
    storage_path: str | None = None


@dataclass(slots=True, frozen=True)
class FailureReviewCluster:
    """Small aggregate summary for similar failure reviews."""

    cluster_key: str
    failure_category: str
    count: int
    latest_run_created_at: datetime
    route_reason_excerpt: str | None
    sample_task_titles: list[str]
    run_ids: list[UUID]


class FailureReviewService:
    """Create file-backed failure reviews and aggregate them for the console."""

    def __init__(
        self,
        *,
        failure_review_repository: FailureReviewRepository,
        run_logging_service: RunLoggingService,
    ) -> None:
        self.failure_review_repository = failure_review_repository
        self.run_logging_service = run_logging_service

    def should_create_review(self, *, run: Run) -> bool:
        """Return whether one run should produce a review record."""

        if run.failure_category is not None:
            return True

        return run.status in {RunStatus.FAILED, RunStatus.CANCELLED}

    def get_review(self, *, run_id: UUID) -> FailureReviewRecord | None:
        """Return one stored review record if it already exists."""

        payload = self.failure_review_repository.get(run_id=run_id)
        if payload is None:
            return None

        return self._from_payload(payload)

    def ensure_review(self, *, task: Task, run: Run) -> FailureReviewRecord | None:
        """Create or refresh one failure review when the run qualifies."""

        if not self.should_create_review(run=run):
            return None

        existing = self.get_review(run_id=run.id)
        if existing is not None:
            return existing

        review = self._build_review(task=task, run=run)
        payload = self._to_payload(review)
        storage_path = self.failure_review_repository.save(run_id=run.id, payload=payload)
        return FailureReviewRecord(
            **{
                **asdict(review),
                "storage_path": storage_path,
            }
        )

    def list_clusters(self, *, limit: int = 20) -> list[FailureReviewCluster]:
        """Aggregate stored reviews into coarse failure clusters."""

        return self._build_clusters(
            reviews=[
                self._from_payload(payload)
                for payload in self.failure_review_repository.list_all()
            ],
            limit=limit,
        )

    def list_reviews_for_run_ids(
        self,
        *,
        run_ids: list[UUID],
        limit: int | None = None,
    ) -> list[FailureReviewRecord]:
        """Return stored review records that belong to the provided run IDs."""

        if not run_ids:
            return []

        reviews: list[FailureReviewRecord] = []
        for payload in self.failure_review_repository.list_for_run_ids(run_ids=run_ids):
            reviews.append(self._from_payload(payload))
        reviews.sort(key=lambda item: item.created_at, reverse=True)
        if limit is None:
            return reviews

        return reviews[:limit]

    def list_clusters_for_run_ids(
        self,
        *,
        run_ids: list[UUID],
        limit: int = 20,
    ) -> list[FailureReviewCluster]:
        """Aggregate failure reviews belonging to the provided runs."""

        return self._build_clusters(
            reviews=self.list_reviews_for_run_ids(run_ids=run_ids),
            limit=limit,
        )

    def _build_review(self, *, task: Task, run: Run) -> FailureReviewRecord:
        """Derive one minimal review from the finalized task, run and log trail."""

        log_result = self.run_logging_service.read_events(log_path=run.log_path, limit=50)
        evidence_events = [event.event for event in log_result.events]
        action_summary = self._build_action_summary(run=run, evidence_events=evidence_events)
        conclusion = self._build_conclusion(run=run)
        return FailureReviewRecord(
            review_id=f"review-{run.id}",
            task_id=task.id,
            task_title=task.title,
            task_status=task.status,
            run_id=run.id,
            run_status=run.status,
            created_at=run.created_at,
            failure_category=run.failure_category,
            quality_gate_passed=run.quality_gate_passed,
            route_reason=run.route_reason,
            result_summary=run.result_summary,
            log_path=run.log_path,
            evidence_events=evidence_events,
            action_summary=action_summary,
            conclusion=conclusion,
        )

    @staticmethod
    def _build_action_summary(*, run: Run, evidence_events: list[str]) -> str:
        """Summarize what the system did after the failure signal appeared."""

        if "guard_blocked" in evidence_events:
            return "Budget or retry guard blocked the run before execution continued."
        if "verification_finished" in evidence_events:
            return "Execution completed, then verification decided whether the task could pass."
        if "execution_finished" in evidence_events:
            return "Execution finished and the worker finalized the task outcome."

        return (
            run.result_summary
            or "The worker finalized the run without a richer structured action summary."
        )

    @staticmethod
    def _build_conclusion(*, run: Run) -> str:
        """Return a concise review conclusion."""

        if run.failure_category == RunFailureCategory.DAILY_BUDGET_EXCEEDED:
            return "Daily budget guard blocked this task before execution."
        if run.failure_category == RunFailureCategory.SESSION_BUDGET_EXCEEDED:
            return "Session budget guard blocked this task before execution."
        if run.failure_category == RunFailureCategory.RETRY_LIMIT_EXCEEDED:
            return "Retry guard blocked this task because it exceeded the configured limit."
        if run.failure_category == RunFailureCategory.VERIFICATION_CONFIGURATION_FAILED:
            return "Execution succeeded, but verification configuration was invalid."
        if run.failure_category == RunFailureCategory.VERIFICATION_FAILED:
            return "Execution completed, but verification blocked the final completion state."
        if run.failure_category == RunFailureCategory.EXECUTION_FAILED:
            return "Execution itself failed and the task was finalized as failed."
        if run.status == RunStatus.CANCELLED:
            return "The run was cancelled before it could reach successful completion."

        return "The run requires review because it did not reach a normal successful completion."

    @staticmethod
    def _build_clusters(
        *,
        reviews: list[FailureReviewRecord],
        limit: int,
    ) -> list[FailureReviewCluster]:
        """Aggregate review records into coarse clusters."""

        if not reviews:
            return []

        grouped: dict[str, list[FailureReviewRecord]] = {}
        for review in reviews:
            cluster_key = (
                review.failure_category.value
                if review.failure_category
                else review.run_status.value
            )
            grouped.setdefault(cluster_key, []).append(review)

        clusters: list[FailureReviewCluster] = []
        for cluster_key, cluster_reviews in grouped.items():
            ordered_reviews = sorted(
                cluster_reviews,
                key=lambda item: item.created_at,
                reverse=True,
            )
            latest_review = ordered_reviews[0]
            sample_task_titles = list(
                dict.fromkeys(review.task_title for review in ordered_reviews[:5])
            )
            clusters.append(
                FailureReviewCluster(
                    cluster_key=cluster_key,
                    failure_category=cluster_key,
                    count=len(ordered_reviews),
                    latest_run_created_at=latest_review.created_at,
                    route_reason_excerpt=_truncate(latest_review.route_reason, 160),
                    sample_task_titles=sample_task_titles,
                    run_ids=[review.run_id for review in ordered_reviews[:5]],
                )
            )

        return sorted(
            clusters,
            key=lambda cluster: (cluster.count, cluster.latest_run_created_at),
            reverse=True,
        )[:limit]

    @staticmethod
    def _to_payload(review: FailureReviewRecord) -> dict[str, Any]:
        """Serialize one review record for file storage."""

        payload = asdict(review)
        payload["task_id"] = str(review.task_id)
        payload["task_status"] = review.task_status.value
        payload["run_id"] = str(review.run_id)
        payload["run_status"] = review.run_status.value
        payload["created_at"] = review.created_at.isoformat()
        payload["failure_category"] = (
            review.failure_category.value if review.failure_category is not None else None
        )
        return payload

    @staticmethod
    def _from_payload(payload: dict[str, Any]) -> FailureReviewRecord:
        """Hydrate one stored review payload back into a typed record."""

        failure_category = payload.get("failure_category")
        return FailureReviewRecord(
            review_id=str(payload.get("review_id", "")),
            task_id=UUID(str(payload["task_id"])),
            task_title=str(payload.get("task_title", "")),
            task_status=TaskStatus(str(payload.get("task_status", TaskStatus.FAILED.value))),
            run_id=UUID(str(payload["run_id"])),
            run_status=RunStatus(str(payload.get("run_status", RunStatus.FAILED.value))),
            created_at=_parse_datetime(payload.get("created_at")),
            failure_category=(
                RunFailureCategory(str(failure_category))
                if isinstance(failure_category, str) and failure_category
                else None
            ),
            quality_gate_passed=(
                payload.get("quality_gate_passed")
                if isinstance(payload.get("quality_gate_passed"), bool)
                or payload.get("quality_gate_passed") is None
                else None
            ),
            route_reason=(
                str(payload["route_reason"]) if payload.get("route_reason") is not None else None
            ),
            result_summary=(
                str(payload["result_summary"])
                if payload.get("result_summary") is not None
                else None
            ),
            log_path=str(payload["log_path"]) if payload.get("log_path") is not None else None,
            evidence_events=[
                str(event_name)
                for event_name in payload.get("evidence_events", [])
                if str(event_name)
            ],
            action_summary=str(payload.get("action_summary", "")),
            conclusion=str(payload.get("conclusion", "")),
            storage_path=(
                str(payload["storage_path"]) if payload.get("storage_path") is not None else None
            ),
        )


def _truncate(value: str | None, max_length: int) -> str | None:
    """Trim long review snippets for cluster summaries."""

    if value is None or len(value) <= max_length:
        return value

    return value[: max_length - 3] + "..."


def _parse_datetime(value: Any) -> datetime:
    """Parse one stored ISO datetime with a UTC fallback."""

    if isinstance(value, datetime):
        return ensure_utc_datetime(value) or utc_now()

    if isinstance(value, str) and value:
        try:
            return ensure_utc_datetime(datetime.fromisoformat(value)) or utc_now()
        except ValueError:
            return utc_now()

    return utc_now()
