"""Project memory consolidation and lightweight retrieval for V3 Day14."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.approval import ApprovalDecisionAction
from app.domain.project import Project, ProjectStage
from app.domain.project_role import ProjectRoleCode
from app.domain.run import Run, RunFailureCategory, RunStatus
from app.domain.task import Task
from app.repositories.approval_repository import ApprovalRecord, ApprovalRepository
from app.repositories.deliverable_repository import DeliverableRecord, DeliverableRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.failure_review_service import FailureReviewRecord, FailureReviewService

_PROJECT_MEMORY_SUMMARY_LIMIT = 600
_PROJECT_MEMORY_DETAIL_LIMIT = 1_400
_QUERY_TERM_LIMIT = 30
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]+", re.IGNORECASE)


class ProjectMemoryKind(StrEnum):
    """Stable Day14 project-memory categories."""

    CONCLUSION = "conclusion"
    FAILURE_PATTERN = "failure_pattern"
    APPROVAL_FEEDBACK = "approval_feedback"
    DELIVERABLE_SUMMARY = "deliverable_summary"


class ProjectMemorySourceKind(StrEnum):
    """Stable Day14 project-memory provenance types."""

    RUN = "run"
    FAILURE_REVIEW = "failure_review"
    APPROVAL_DECISION = "approval_decision"
    DELIVERABLE_VERSION = "deliverable_version"


@dataclass(slots=True, frozen=True)
class ProjectMemoryCount:
    memory_type: ProjectMemoryKind
    count: int


@dataclass(slots=True, frozen=True)
class ProjectMemoryItem:
    memory_id: str
    project_id: UUID
    memory_type: ProjectMemoryKind
    title: str
    summary: str
    detail: str | None
    stage: ProjectStage | None
    role_code: ProjectRoleCode | None
    actor_name: str | None
    source_kind: ProjectMemorySourceKind
    source_label: str
    task_id: UUID | None
    run_id: UUID | None
    approval_id: UUID | None
    deliverable_id: UUID | None
    deliverable_version_id: UUID | None
    tags: list[str]
    created_at: datetime


@dataclass(slots=True, frozen=True)
class ProjectMemorySnapshot:
    project_id: UUID
    project_name: str
    generated_at: datetime
    total_memories: int
    counts: list[ProjectMemoryCount]
    items: list[ProjectMemoryItem]
    storage_path: str | None = None


@dataclass(slots=True, frozen=True)
class ProjectMemorySearchHit:
    item: ProjectMemoryItem
    score: float
    matched_terms: list[str]


@dataclass(slots=True, frozen=True)
class ProjectMemorySearchResult:
    project_id: UUID
    query: str
    total_matches: int
    hits: list[ProjectMemorySearchHit]


@dataclass(slots=True, frozen=True)
class TaskProjectMemoryContext:
    project_id: UUID
    task_id: UUID
    task_title: str
    query_text: str
    items: list[ProjectMemoryItem]
    context_summary: str


class ProjectMemoryService:
    """Build, persist and retrieve lightweight project-memory snapshots."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        deliverable_repository: DeliverableRepository,
        approval_repository: ApprovalRepository,
        failure_review_service: FailureReviewService,
    ) -> None:
        self.project_repository = project_repository
        self.task_repository = task_repository
        self.run_repository = run_repository
        self.deliverable_repository = deliverable_repository
        self.approval_repository = approval_repository
        self.failure_review_service = failure_review_service
        self._base_dir = settings.runtime_data_dir / "project-memories"

    def get_project_memory_snapshot(
        self,
        *,
        project_id: UUID,
        refresh: bool = True,
    ) -> ProjectMemorySnapshot | None:
        if refresh:
            return self.refresh_project_memory(project_id=project_id)
        return self._load_snapshot(project_id=project_id)

    def refresh_project_memory(self, *, project_id: UUID) -> ProjectMemorySnapshot | None:
        project = self.project_repository.get_by_id(project_id)
        if project is None:
            return None

        task_map = {
            task.id: task for task in self.task_repository.list_by_project_id(project_id)
        }
        runs = self.run_repository.list_by_task_ids(list(task_map))
        run_map = {run.id: run for run in runs}
        deliverables = self.deliverable_repository.list_records_by_project_id(project_id)
        approvals = self.approval_repository.list_records_by_project_id(project_id)
        failure_reviews = self.failure_review_service.list_reviews_for_run_ids(
            run_ids=list(run_map),
        )

        items = self._build_project_memory_items(
            project=project,
            task_map=task_map,
            runs=runs,
            failure_reviews=failure_reviews,
            deliverables=deliverables,
            approvals=approvals,
        )
        snapshot = ProjectMemorySnapshot(
            project_id=project.id,
            project_name=project.name,
            generated_at=utc_now(),
            total_memories=len(items),
            counts=self._build_counts(items),
            items=items,
        )
        storage_path = self._save_snapshot(snapshot=snapshot)
        return ProjectMemorySnapshot(
            project_id=snapshot.project_id,
            project_name=snapshot.project_name,
            generated_at=snapshot.generated_at,
            total_memories=snapshot.total_memories,
            counts=snapshot.counts,
            items=snapshot.items,
            storage_path=storage_path,
        )

    def search_project_memories(
        self,
        *,
        project_id: UUID,
        query: str,
        limit: int = 10,
        memory_type: ProjectMemoryKind | None = None,
    ) -> ProjectMemorySearchResult | None:
        snapshot = self.get_project_memory_snapshot(project_id=project_id)
        if snapshot is None:
            return None

        normalized_query = _normalize_text(query)
        if not normalized_query:
            return ProjectMemorySearchResult(
                project_id=project_id,
                query=query,
                total_matches=0,
                hits=[],
            )

        query_terms = _extract_query_terms(query)
        hits: list[ProjectMemorySearchHit] = []
        for item in snapshot.items:
            if memory_type is not None and item.memory_type != memory_type:
                continue

            score, matched_terms = self._score_item(
                item=item,
                normalized_query=normalized_query,
                query_terms=query_terms,
            )
            if score <= 0:
                continue

            hits.append(
                ProjectMemorySearchHit(
                    item=item,
                    score=score,
                    matched_terms=matched_terms,
                )
            )

        hits.sort(
            key=lambda item: (item.score, item.item.created_at, item.item.memory_id),
            reverse=True,
        )
        return ProjectMemorySearchResult(
            project_id=project_id,
            query=query,
            total_matches=len(hits),
            hits=hits[: max(limit, 0)],
        )

    def build_task_memory_context(
        self,
        *,
        task: Task,
        limit: int = 3,
    ) -> TaskProjectMemoryContext | None:
        if task.project_id is None:
            return None

        query_text = self._build_task_query_text(task)
        search_result = self.search_project_memories(
            project_id=task.project_id,
            query=query_text,
            limit=limit,
        )
        if search_result is None:
            return None

        recalled_items = [hit.item for hit in search_result.hits]
        return TaskProjectMemoryContext(
            project_id=task.project_id,
            task_id=task.id,
            task_title=task.title,
            query_text=query_text,
            items=recalled_items,
            context_summary=self._build_task_context_summary(
                task=task,
                items=recalled_items,
            ),
        )

    def _build_project_memory_items(
        self,
        *,
        project: Project,
        task_map: dict[UUID, Task],
        runs: list[Run],
        failure_reviews: list[FailureReviewRecord],
        deliverables: list[DeliverableRecord],
        approvals: list[ApprovalRecord],
    ) -> list[ProjectMemoryItem]:
        items: dict[str, ProjectMemoryItem] = {}
        run_map = {run.id: run for run in runs}

        for run in runs:
            item = self._build_run_conclusion_item(
                project=project,
                run=run,
                task=task_map.get(run.task_id),
            )
            if item is not None:
                items[item.memory_id] = item

        for review in failure_reviews:
            item = self._build_failure_review_item(
                project=project,
                review=review,
                run=run_map.get(review.run_id),
                task=task_map.get(review.task_id),
            )
            if item is not None:
                items[item.memory_id] = item

        for approval_record in approvals:
            for item in self._build_approval_feedback_items(
                project=project,
                approval_record=approval_record,
            ):
                items[item.memory_id] = item

        for deliverable_record in deliverables:
            for item in self._build_deliverable_summary_items(
                project=project,
                deliverable_record=deliverable_record,
            ):
                items[item.memory_id] = item

        return sorted(
            items.values(),
            key=lambda item: (item.created_at, item.memory_id),
            reverse=True,
        )

    def _build_run_conclusion_item(
        self,
        *,
        project: Project,
        run: Run,
        task: Task | None,
    ) -> ProjectMemoryItem | None:
        if run.status != RunStatus.SUCCEEDED and run.quality_gate_passed is not True:
            return None

        summary = _first_non_empty(run.verification_summary, run.result_summary)
        if summary is None:
            return None

        task_title = task.title if task is not None else f"任务 {run.task_id}"
        detail = _join_detail_parts(
            [
                _prefixed("运行结论", run.result_summary),
                _prefixed("验证结论", run.verification_summary),
                _prefixed("路由原因", run.route_reason),
            ]
        )
        return ProjectMemoryItem(
            memory_id=f"run-conclusion-{run.id}",
            project_id=project.id,
            memory_type=ProjectMemoryKind.CONCLUSION,
            title=f"关键结论：{task_title}",
            summary=summary,
            detail=detail,
            stage=_infer_run_stage(run),
            role_code=run.owner_role_code,
            actor_name=None,
            source_kind=ProjectMemorySourceKind.RUN,
            source_label=f"{task_title} / 运行 {run.id}",
            task_id=task.id if task is not None else run.task_id,
            run_id=run.id,
            approval_id=None,
            deliverable_id=None,
            deliverable_version_id=None,
            tags=_normalize_tags(
                [
                    "run",
                    "success",
                    task_title,
                    run.status.value,
                    _enum_value(_infer_run_stage(run)),
                    _enum_value(run.owner_role_code),
                ]
            ),
            created_at=ensure_utc_datetime(run.finished_at or run.created_at),
        )

    def _build_failure_review_item(
        self,
        *,
        project: Project,
        review: FailureReviewRecord,
        run: Run | None,
        task: Task | None,
    ) -> ProjectMemoryItem | None:
        task_title = task.title if task is not None else review.task_title or f"任务 {review.task_id}"
        detail = _join_detail_parts(
            [
                _prefixed("处置摘要", review.action_summary),
                _prefixed("运行摘要", review.result_summary),
                _prefixed("路由原因", review.route_reason),
                (
                    "证据事件：" + "、".join(review.evidence_events[:5])
                    if review.evidence_events
                    else None
                ),
            ]
        )
        return ProjectMemoryItem(
            memory_id=f"failure-review-{review.run_id}",
            project_id=project.id,
            memory_type=ProjectMemoryKind.FAILURE_PATTERN,
            title=f"失败模式：{task_title}",
            summary=review.conclusion,
            detail=detail,
            stage=_infer_run_stage(run),
            role_code=run.owner_role_code if run is not None else None,
            actor_name=None,
            source_kind=ProjectMemorySourceKind.FAILURE_REVIEW,
            source_label=f"{task_title} / 失败复盘 {review.review_id}",
            task_id=review.task_id,
            run_id=review.run_id,
            approval_id=None,
            deliverable_id=None,
            deliverable_version_id=None,
            tags=_normalize_tags(
                [
                    "failure_review",
                    task_title,
                    _enum_value(review.failure_category),
                    _enum_value(_infer_run_stage(run)),
                    _enum_value(run.owner_role_code if run is not None else None),
                    *review.evidence_events[:5],
                ]
            ),
            created_at=ensure_utc_datetime(review.created_at),
        )

    def _build_approval_feedback_items(
        self,
        *,
        project: Project,
        approval_record: ApprovalRecord,
    ) -> list[ProjectMemoryItem]:
        approval = approval_record.approval
        items: list[ProjectMemoryItem] = []
        for decision in approval_record.decisions:
            decision_label = _APPROVAL_ACTION_LABELS.get(
                decision.action,
                decision.action.value,
            )
            detail = _join_detail_parts(
                [
                    _prefixed("审批备注", decision.comment),
                    (
                        "重点风险：" + "；".join(decision.highlighted_risks)
                        if decision.highlighted_risks
                        else None
                    ),
                    (
                        "要求变更：" + "；".join(decision.requested_changes)
                        if decision.requested_changes
                        else None
                    ),
                    _prefixed("发起说明", approval.request_note),
                ]
            )
            items.append(
                ProjectMemoryItem(
                    memory_id=f"approval-decision-{decision.id}",
                    project_id=project.id,
                    memory_type=ProjectMemoryKind.APPROVAL_FEEDBACK,
                    title=(
                        f"审批意见：{approval.deliverable_title}"
                        f" v{approval.deliverable_version_number}"
                    ),
                    summary=f"{decision_label}：{decision.summary}",
                    detail=detail,
                    stage=approval.deliverable_stage,
                    role_code=approval.requester_role_code,
                    actor_name=decision.actor_name,
                    source_kind=ProjectMemorySourceKind.APPROVAL_DECISION,
                    source_label=f"{approval.deliverable_title} / 审批 {approval.id}",
                    task_id=None,
                    run_id=None,
                    approval_id=approval.id,
                    deliverable_id=approval.deliverable_id,
                    deliverable_version_id=approval.deliverable_version_id,
                    tags=_normalize_tags(
                        [
                            "approval",
                            approval.deliverable_title,
                            approval.deliverable_type.value,
                            approval.deliverable_stage.value,
                            approval.requester_role_code.value,
                            decision.action.value,
                            decision.actor_name,
                            *decision.highlighted_risks[:3],
                            *decision.requested_changes[:3],
                        ]
                    ),
                    created_at=ensure_utc_datetime(decision.created_at),
                )
            )
        return items

    def _build_deliverable_summary_items(
        self,
        *,
        project: Project,
        deliverable_record: DeliverableRecord,
    ) -> list[ProjectMemoryItem]:
        deliverable = deliverable_record.deliverable
        items: list[ProjectMemoryItem] = []
        for version in deliverable_record.versions:
            detail = _join_detail_parts(
                [
                    _prefixed("版本摘要", version.summary),
                    _prefixed("内容摘录", _preview_text(version.content, 240)),
                ]
            )
            items.append(
                ProjectMemoryItem(
                    memory_id=f"deliverable-version-{version.id}",
                    project_id=project.id,
                    memory_type=ProjectMemoryKind.DELIVERABLE_SUMMARY,
                    title=f"交付件摘要：{deliverable.title} v{version.version_number}",
                    summary=version.summary,
                    detail=detail,
                    stage=deliverable.stage,
                    role_code=version.author_role_code,
                    actor_name=None,
                    source_kind=ProjectMemorySourceKind.DELIVERABLE_VERSION,
                    source_label=f"{deliverable.title} / v{version.version_number}",
                    task_id=version.source_task_id,
                    run_id=version.source_run_id,
                    approval_id=None,
                    deliverable_id=deliverable.id,
                    deliverable_version_id=version.id,
                    tags=_normalize_tags(
                        [
                            "deliverable",
                            deliverable.title,
                            deliverable.type.value,
                            deliverable.stage.value,
                            version.author_role_code.value,
                            version.content_format.value,
                        ]
                    ),
                    created_at=ensure_utc_datetime(version.created_at),
                )
            )
        return items

    @staticmethod
    def _build_counts(items: list[ProjectMemoryItem]) -> list[ProjectMemoryCount]:
        type_counts = {memory_type: 0 for memory_type in ProjectMemoryKind}
        for item in items:
            type_counts[item.memory_type] = type_counts.get(item.memory_type, 0) + 1

        return [
            ProjectMemoryCount(memory_type=memory_type, count=type_counts[memory_type])
            for memory_type in ProjectMemoryKind
        ]

    def _save_snapshot(self, *, snapshot: ProjectMemorySnapshot) -> str:
        absolute_path = self._resolve_snapshot_path(project_id=snapshot.project_id)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._snapshot_to_payload(snapshot)
        absolute_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return absolute_path.relative_to(settings.runtime_data_dir).as_posix()

    def _load_snapshot(self, *, project_id: UUID) -> ProjectMemorySnapshot | None:
        absolute_path = self._resolve_snapshot_path(project_id=project_id)
        if not absolute_path.exists():
            return None

        try:
            payload = json.loads(absolute_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        return self._snapshot_from_payload(payload, storage_path=absolute_path)

    def _snapshot_to_payload(self, snapshot: ProjectMemorySnapshot) -> dict[str, Any]:
        return {
            "project_id": str(snapshot.project_id),
            "project_name": snapshot.project_name,
            "generated_at": snapshot.generated_at.isoformat(),
            "total_memories": snapshot.total_memories,
            "counts": [
                {
                    "memory_type": item.memory_type.value,
                    "count": item.count,
                }
                for item in snapshot.counts
            ],
            "items": [self._item_to_payload(item) for item in snapshot.items],
        }

    def _snapshot_from_payload(
        self,
        payload: dict[str, Any],
        *,
        storage_path: Path,
    ) -> ProjectMemorySnapshot | None:
        try:
            project_id = UUID(str(payload["project_id"]))
            counts = [
                ProjectMemoryCount(
                    memory_type=ProjectMemoryKind(str(item.get("memory_type"))),
                    count=int(item.get("count", 0)),
                )
                for item in payload.get("counts", [])
            ]
            items = [
                self._item_from_payload(item)
                for item in payload.get("items", [])
                if isinstance(item, dict)
            ]
        except (KeyError, TypeError, ValueError):
            return None

        return ProjectMemorySnapshot(
            project_id=project_id,
            project_name=str(payload.get("project_name", "")),
            generated_at=_parse_datetime(payload.get("generated_at")),
            total_memories=int(payload.get("total_memories", len(items))),
            counts=counts,
            items=items,
            storage_path=storage_path.relative_to(settings.runtime_data_dir).as_posix(),
        )

    @staticmethod
    def _item_to_payload(item: ProjectMemoryItem) -> dict[str, Any]:
        return {
            "memory_id": item.memory_id,
            "project_id": str(item.project_id),
            "memory_type": item.memory_type.value,
            "title": item.title,
            "summary": item.summary,
            "detail": item.detail,
            "stage": item.stage.value if item.stage is not None else None,
            "role_code": item.role_code.value if item.role_code is not None else None,
            "actor_name": item.actor_name,
            "source_kind": item.source_kind.value,
            "source_label": item.source_label,
            "task_id": str(item.task_id) if item.task_id is not None else None,
            "run_id": str(item.run_id) if item.run_id is not None else None,
            "approval_id": str(item.approval_id) if item.approval_id is not None else None,
            "deliverable_id": str(item.deliverable_id) if item.deliverable_id is not None else None,
            "deliverable_version_id": (
                str(item.deliverable_version_id)
                if item.deliverable_version_id is not None
                else None
            ),
            "tags": list(item.tags),
            "created_at": item.created_at.isoformat(),
        }

    @staticmethod
    def _item_from_payload(payload: dict[str, Any]) -> ProjectMemoryItem:
        return ProjectMemoryItem(
            memory_id=str(payload.get("memory_id", "")),
            project_id=UUID(str(payload["project_id"])),
            memory_type=ProjectMemoryKind(str(payload["memory_type"])),
            title=str(payload.get("title", "")),
            summary=str(payload.get("summary", "")),
            detail=str(payload["detail"]) if payload.get("detail") is not None else None,
            stage=(
                ProjectStage(str(payload["stage"]))
                if isinstance(payload.get("stage"), str) and payload.get("stage")
                else None
            ),
            role_code=(
                ProjectRoleCode(str(payload["role_code"]))
                if isinstance(payload.get("role_code"), str) and payload.get("role_code")
                else None
            ),
            actor_name=(
                str(payload["actor_name"]) if payload.get("actor_name") is not None else None
            ),
            source_kind=ProjectMemorySourceKind(str(payload["source_kind"])),
            source_label=str(payload.get("source_label", "")),
            task_id=UUID(str(payload["task_id"])) if payload.get("task_id") is not None else None,
            run_id=UUID(str(payload["run_id"])) if payload.get("run_id") is not None else None,
            approval_id=(
                UUID(str(payload["approval_id"]))
                if payload.get("approval_id") is not None
                else None
            ),
            deliverable_id=(
                UUID(str(payload["deliverable_id"]))
                if payload.get("deliverable_id") is not None
                else None
            ),
            deliverable_version_id=(
                UUID(str(payload["deliverable_version_id"]))
                if payload.get("deliverable_version_id") is not None
                else None
            ),
            tags=[str(item) for item in payload.get("tags", []) if str(item).strip()],
            created_at=_parse_datetime(payload.get("created_at")),
        )

    def _score_item(
        self,
        *,
        item: ProjectMemoryItem,
        normalized_query: str,
        query_terms: list[str],
    ) -> tuple[float, list[str]]:
        normalized_title = _normalize_text(item.title)
        normalized_summary = _normalize_text(item.summary)
        normalized_detail = _normalize_text(item.detail or "")
        normalized_meta = _normalize_text(
            " ".join(
                [
                    item.source_label,
                    _enum_value(item.stage) or "",
                    _enum_value(item.role_code) or "",
                    item.actor_name or "",
                    " ".join(item.tags),
                ]
            )
        )

        score = 0.0
        matched_terms: list[str] = []
        if normalized_query in normalized_title:
            score += 8.0
            matched_terms.append(normalized_query)
        elif normalized_query in normalized_summary:
            score += 6.0
            matched_terms.append(normalized_query)
        elif normalized_query in normalized_detail:
            score += 4.0
            matched_terms.append(normalized_query)
        elif normalized_query in normalized_meta:
            score += 3.0
            matched_terms.append(normalized_query)

        for term in query_terms:
            if term in normalized_title:
                score += 3.0
                matched_terms.append(term)
                continue
            if term in normalized_summary:
                score += 2.2
                matched_terms.append(term)
                continue
            if term in normalized_detail:
                score += 1.6
                matched_terms.append(term)
                continue
            if term in normalized_meta:
                score += 1.2
                matched_terms.append(term)

        age_days = max((utc_now() - item.created_at).days, 0)
        score += max(0.0, 1.0 - min(age_days, 30) / 30)
        return score, list(dict.fromkeys(matched_terms))[:8]

    @staticmethod
    def _build_task_query_text(task: Task) -> str:
        query_parts = [task.title, task.input_summary, *task.acceptance_criteria[:3]]
        return "\n".join(
            item.strip() for item in query_parts if isinstance(item, str) and item.strip()
        )

    @staticmethod
    def _build_task_context_summary(
        *,
        task: Task,
        items: list[ProjectMemoryItem],
    ) -> str:
        if not items:
            return (
                f"Project memory recall for {task.title}: no closely related project memory was found."
            )

        summary_lines = [f"Project memory recall for {task.title}:"]
        for item in items[:3]:
            descriptor_parts = [
                item.memory_type.value,
                _enum_value(item.stage),
                _enum_value(item.role_code),
                item.actor_name,
            ]
            descriptor = " / ".join(part for part in descriptor_parts if part)
            summary_lines.append(
                f"- [{descriptor}] {item.title}: {item.summary}"
                if descriptor
                else f"- {item.title}: {item.summary}"
            )

        return _truncate("\n".join(summary_lines), _PROJECT_MEMORY_SUMMARY_LIMIT)

    def _resolve_snapshot_path(self, *, project_id: UUID) -> Path:
        project_prefix = str(project_id)[:2]
        return self._base_dir / project_prefix / f"{project_id}.json"


_APPROVAL_ACTION_LABELS: dict[ApprovalDecisionAction, str] = {
    ApprovalDecisionAction.APPROVE: "审批通过",
    ApprovalDecisionAction.REJECT: "审批驳回",
    ApprovalDecisionAction.REQUEST_CHANGES: "要求修改",
}


def _infer_run_stage(run: Run | None) -> ProjectStage | None:
    if run is None:
        return None

    if run.verification_summary is not None or run.failure_category in {
        RunFailureCategory.VERIFICATION_CONFIGURATION_FAILED,
        RunFailureCategory.VERIFICATION_FAILED,
    }:
        return ProjectStage.VERIFICATION

    return ProjectStage.EXECUTION


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _extract_query_terms(value: str) -> list[str]:
    normalized_value = _normalize_text(value)
    if not normalized_value:
        return []

    terms: list[str] = []
    seen_terms: set[str] = set()
    for raw_token in _TOKEN_PATTERN.findall(normalized_value):
        token = raw_token.strip()
        if len(token) <= 1:
            continue

        for candidate in _expand_token_candidates(token):
            if len(candidate) <= 1 or candidate in seen_terms:
                continue
            terms.append(candidate)
            seen_terms.add(candidate)
            if len(terms) >= _QUERY_TERM_LIMIT:
                return terms

    return terms


def _expand_token_candidates(token: str) -> list[str]:
    candidates = [token]
    if _CJK_PATTERN.fullmatch(token):
        if len(token) > 4:
            candidates.extend(token[index : index + 2] for index in range(len(token) - 1))
        if len(token) > 6:
            candidates.extend(token[index : index + 3] for index in range(len(token) - 2))

    return candidates


def _normalize_tags(values: list[str | None]) -> list[str]:
    normalized_values: list[str] = []
    seen_values: set[str] = set()
    for value in values:
        if value is None:
            continue
        normalized_value = str(value).strip()
        if not normalized_value or normalized_value in seen_values:
            continue
        normalized_values.append(normalized_value)
        seen_values.add(normalized_value)
    return normalized_values


def _join_detail_parts(parts: list[str | None]) -> str | None:
    normalized_parts = [part.strip() for part in parts if isinstance(part, str) and part.strip()]
    if not normalized_parts:
        return None

    return _truncate("\n".join(normalized_parts), _PROJECT_MEMORY_DETAIL_LIMIT)


def _prefixed(prefix: str, value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = value.strip()
    if not normalized_value:
        return None

    return f"{prefix}：{normalized_value}"


def _preview_text(value: str, max_length: int) -> str | None:
    normalized_value = " ".join(value.split())
    if not normalized_value:
        return None

    return _truncate(normalized_value, max_length)


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value

    return value[: max_length - 3].rstrip() + "..."


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc_datetime(value)

    if isinstance(value, str) and value.strip():
        return ensure_utc_datetime(datetime.fromisoformat(value))

    return utc_now()


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value is None:
            continue
        normalized_value = value.strip()
        if normalized_value:
            return normalized_value

    return None


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None

    return str(getattr(value, "value", value))
