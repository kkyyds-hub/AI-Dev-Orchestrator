"""Business services for Day07 change-batch execution preparation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain._base import utc_now
from app.domain.change_batch import (
    ChangeBatch,
    ChangeBatchLinkedDeliverable,
    ChangeBatchPlanSnapshot,
    ChangeBatchStatus,
)
from app.domain.change_plan import ChangePlanTargetFile, ChangePlanVersion
from app.domain.repository_workspace import RepositoryWorkspace
from app.domain.task import Task
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.change_plan_repository import ChangePlanRecord, ChangePlanRepository
from app.repositories.deliverable_repository import DeliverableRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.task_repository import TaskRepository


@dataclass(slots=True, frozen=True)
class ChangeBatchDependencyView:
    """One task dependency rendered inside the Day07 execution board."""

    task_id: UUID
    task_title: str
    in_batch: bool
    missing: bool
    order_index: int | None


@dataclass(slots=True, frozen=True)
class ChangeBatchTaskView:
    """One ordered task item shown inside a Day07 change batch."""

    order_index: int
    task_id: UUID
    task_title: str
    task_priority: str
    task_risk_level: str
    change_plan_id: UUID
    change_plan_title: str
    selected_version_number: int
    intent_summary: str
    expected_actions: list[str]
    verification_commands: list[str]
    related_deliverables: list[ChangeBatchLinkedDeliverable]
    dependencies: list[ChangeBatchDependencyView]
    target_files: list[ChangePlanTargetFile]
    overlap_file_paths: list[str]


@dataclass(slots=True, frozen=True)
class ChangeBatchTargetFileView:
    """One aggregated repository file captured by a Day07 change batch."""

    relative_path: str
    language: str
    file_type: str
    match_reasons: list[str]
    rationales: list[str]
    task_ids: list[UUID]
    task_titles: list[str]
    change_plan_ids: list[UUID]
    change_plan_titles: list[str]
    overlap_count: int


@dataclass(slots=True, frozen=True)
class ChangeBatchTimelineEntry:
    """One timeline row rendered inside the Day07 board."""

    entry_type: str
    label: str
    summary: str
    occurred_at: datetime


@dataclass(slots=True, frozen=True)
class ChangeBatchSummary:
    """One project-scoped Day07 change-batch summary row."""

    change_batch: ChangeBatch
    active: bool
    change_plan_count: int
    task_count: int
    target_file_count: int
    overlap_file_count: int
    dependency_count: int
    verification_command_count: int


@dataclass(slots=True, frozen=True)
class ChangeBatchDetail:
    """Full Day07 change-batch detail shown in the repository view."""

    summary: ChangeBatchSummary
    repository_workspace: RepositoryWorkspace | None
    tasks: list[ChangeBatchTaskView]
    target_files: list[ChangeBatchTargetFileView]
    overlap_files: list[ChangeBatchTargetFileView]
    timeline: list[ChangeBatchTimelineEntry]


class ChangeBatchError(ValueError):
    """Base error raised by the Day07 change-batch service."""


class ChangeBatchProjectNotFoundError(ChangeBatchError):
    """Raised when the requested project is missing."""


class ChangeBatchWorkspaceNotFoundError(ChangeBatchError):
    """Raised when the project has no bound repository workspace."""


class ChangeBatchNotFoundError(ChangeBatchError):
    """Raised when the requested change batch cannot be found."""


class ChangeBatchActiveConflictError(ChangeBatchError):
    """Raised when a project already has one active Day07 batch."""


class ChangeBatchPlanNotFoundError(ChangeBatchError):
    """Raised when one selected ChangePlan cannot be resolved."""


class ChangeBatchPlanTaskConflictError(ChangeBatchError):
    """Raised when selected ChangePlans cannot form a clean task ordering."""


class ChangeBatchDeliverableNotFoundError(ChangeBatchError):
    """Raised when one linked deliverable snapshot cannot be resolved."""


class ChangeBatchService:
    """Create and query Day07 change batches without entering Day08 preflight."""

    def __init__(
        self,
        *,
        change_batch_repository: ChangeBatchRepository,
        change_plan_repository: ChangePlanRepository,
        project_repository: ProjectRepository,
        repository_workspace_repository: RepositoryWorkspaceRepository,
        task_repository: TaskRepository,
        deliverable_repository: DeliverableRepository,
    ) -> None:
        self.change_batch_repository = change_batch_repository
        self.change_plan_repository = change_plan_repository
        self.project_repository = project_repository
        self.repository_workspace_repository = repository_workspace_repository
        self.task_repository = task_repository
        self.deliverable_repository = deliverable_repository

    def create_change_batch(
        self,
        *,
        project_id: UUID,
        title: str | None,
        change_plan_ids: list[UUID],
    ) -> ChangeBatchDetail:
        """Create one new active Day07 batch from multiple latest ChangePlan heads."""

        self._ensure_project_exists(project_id)
        workspace = self._require_repository_workspace(project_id)

        active_batch = self.change_batch_repository.get_active_by_project_id(project_id)
        if active_batch is not None:
            raise ChangeBatchActiveConflictError(
                f"Project already has an active change batch: {active_batch.id}"
            )

        normalized_plan_ids = list(dict.fromkeys(change_plan_ids))
        if len(normalized_plan_ids) < 2:
            raise ValueError("Change batch must merge at least two change plans.")

        deliverable_map = self._build_project_deliverable_map(project_id)
        plan_snapshots = [
            self._build_plan_snapshot(
                project_id=project_id,
                change_plan_id=change_plan_id,
                deliverable_map=deliverable_map,
            )
            for change_plan_id in normalized_plan_ids
        ]
        ordered_snapshots = self._order_plan_snapshots(plan_snapshots)
        timestamp = utc_now()
        target_files = self._build_target_file_views(ordered_snapshots)
        overlap_files = [
            item for item in target_files if item.overlap_count > 1
        ]

        change_batch = ChangeBatch(
            project_id=project_id,
            repository_workspace_id=workspace.id,
            status=ChangeBatchStatus.PREPARING,
            title=self._resolve_title(title=title, plan_snapshots=ordered_snapshots),
            summary=self._build_summary(
                plan_snapshots=ordered_snapshots,
                target_files=target_files,
                overlap_files=overlap_files,
            ),
            plan_snapshots=ordered_snapshots,
            created_at=timestamp,
            updated_at=timestamp,
        )
        persisted_batch = self.change_batch_repository.create(change_batch)
        return self._to_detail(persisted_batch, repository_workspace=workspace)

    def list_change_batches(self, project_id: UUID) -> list[ChangeBatchSummary]:
        """List all Day07 change batches under one project."""

        self._ensure_project_exists(project_id)
        return [
            self._to_summary(change_batch)
            for change_batch in self.change_batch_repository.list_by_project_id(project_id)
        ]

    def get_change_batch_detail(self, change_batch_id: UUID) -> ChangeBatchDetail:
        """Return one Day07 batch detail by ID."""

        change_batch = self.change_batch_repository.get_by_id(change_batch_id)
        if change_batch is None:
            raise ChangeBatchNotFoundError(f"Change batch not found: {change_batch_id}")

        repository_workspace = None
        if change_batch.repository_workspace_id is not None:
            repository_workspace = self.repository_workspace_repository.get_by_project_id(
                change_batch.project_id
            )

        return self._to_detail(change_batch, repository_workspace=repository_workspace)

    def _to_summary(self, change_batch: ChangeBatch) -> ChangeBatchSummary:
        """Convert one persisted change batch into a compact summary view."""

        target_files = self._build_target_file_views(change_batch.plan_snapshots)
        verification_commands = {
            command
            for snapshot in change_batch.plan_snapshots
            for command in snapshot.verification_commands
        }

        return ChangeBatchSummary(
            change_batch=change_batch,
            active=change_batch.status == ChangeBatchStatus.PREPARING,
            change_plan_count=len(change_batch.plan_snapshots),
            task_count=len(change_batch.plan_snapshots),
            target_file_count=len(target_files),
            overlap_file_count=sum(1 for item in target_files if item.overlap_count > 1),
            dependency_count=sum(
                len(snapshot.depends_on_task_ids) for snapshot in change_batch.plan_snapshots
            ),
            verification_command_count=len(verification_commands),
        )

    def _to_detail(
        self,
        change_batch: ChangeBatch,
        *,
        repository_workspace: RepositoryWorkspace | None,
    ) -> ChangeBatchDetail:
        """Convert one persisted Day07 batch into the repository-board detail view."""

        summary = self._to_summary(change_batch)
        target_files = self._build_target_file_views(change_batch.plan_snapshots)
        overlap_path_set = {
            item.relative_path for item in target_files if item.overlap_count > 1
        }
        order_map = {
            snapshot.task_id: index + 1
            for index, snapshot in enumerate(change_batch.plan_snapshots)
        }
        dependency_ids = [
            dependency_id
            for snapshot in change_batch.plan_snapshots
            for dependency_id in snapshot.depends_on_task_ids
        ]
        dependency_task_map = self.task_repository.get_by_ids(dependency_ids)

        task_views: list[ChangeBatchTaskView] = []
        for index, snapshot in enumerate(change_batch.plan_snapshots, start=1):
            dependencies = [
                ChangeBatchDependencyView(
                    task_id=dependency_id,
                    task_title=(
                        dependency_task_map[dependency_id].title
                        if dependency_id in dependency_task_map
                        else "缺失依赖任务"
                    ),
                    in_batch=dependency_id in order_map,
                    missing=dependency_id not in dependency_task_map,
                    order_index=order_map.get(dependency_id),
                )
                for dependency_id in snapshot.depends_on_task_ids
            ]
            overlap_file_paths = sorted(
                {
                    target_file.relative_path
                    for target_file in snapshot.target_files
                    if target_file.relative_path in overlap_path_set
                }
            )
            task_views.append(
                ChangeBatchTaskView(
                    order_index=index,
                    task_id=snapshot.task_id,
                    task_title=snapshot.task_title,
                    task_priority=snapshot.task_priority.value,
                    task_risk_level=snapshot.task_risk_level.value,
                    change_plan_id=snapshot.change_plan_id,
                    change_plan_title=snapshot.change_plan_title,
                    selected_version_number=snapshot.selected_version_number,
                    intent_summary=snapshot.intent_summary,
                    expected_actions=list(snapshot.expected_actions),
                    verification_commands=list(snapshot.verification_commands),
                    related_deliverables=list(snapshot.related_deliverables),
                    dependencies=dependencies,
                    target_files=list(snapshot.target_files),
                    overlap_file_paths=overlap_file_paths,
                )
            )

        return ChangeBatchDetail(
            summary=summary,
            repository_workspace=repository_workspace,
            tasks=task_views,
            target_files=target_files,
            overlap_files=[item for item in target_files if item.overlap_count > 1],
            timeline=self._build_timeline(change_batch),
        )

    def _build_plan_snapshot(
        self,
        *,
        project_id: UUID,
        change_plan_id: UUID,
        deliverable_map: dict[UUID, ChangeBatchLinkedDeliverable],
    ) -> ChangeBatchPlanSnapshot:
        """Capture one ChangePlan head as an immutable Day07 batch snapshot."""

        record = self.change_plan_repository.get_record_by_id(change_plan_id)
        if record is None:
            raise ChangeBatchPlanNotFoundError(f"Change plan not found: {change_plan_id}")
        if record.change_plan.project_id != project_id:
            raise ChangeBatchPlanNotFoundError(
                f"Change plan does not belong to project: {change_plan_id}"
            )

        task = self.task_repository.get_by_id(record.change_plan.task_id)
        if task is None or task.project_id != project_id:
            raise ChangeBatchPlanTaskConflictError(
                f"Change plan task not found in project: {record.change_plan.task_id}"
            )

        latest_version = self._require_latest_version(record, change_plan_id=change_plan_id)
        related_deliverables = []
        for deliverable_id in latest_version.related_deliverable_ids:
            if deliverable_id not in deliverable_map:
                raise ChangeBatchDeliverableNotFoundError(
                    f"Deliverable not found in project: {deliverable_id}"
                )
            related_deliverables.append(deliverable_map[deliverable_id])

        return ChangeBatchPlanSnapshot(
            change_plan_id=record.change_plan.id,
            change_plan_title=record.change_plan.title,
            change_plan_status=record.change_plan.status,
            selected_version_id=latest_version.id,
            selected_version_number=latest_version.version_number,
            task_id=task.id,
            task_title=task.title,
            task_priority=task.priority,
            task_risk_level=task.risk_level,
            depends_on_task_ids=list(task.depends_on_task_ids),
            intent_summary=latest_version.intent_summary,
            source_summary=latest_version.source_summary,
            focus_terms=list(latest_version.focus_terms),
            target_files=list(latest_version.target_files),
            expected_actions=list(latest_version.expected_actions),
            risk_notes=list(latest_version.risk_notes),
            verification_commands=list(latest_version.verification_commands),
            related_deliverables=related_deliverables,
            context_pack_generated_at=latest_version.context_pack_generated_at,
            captured_at=latest_version.created_at,
        )

    @staticmethod
    def _require_latest_version(
        record: ChangePlanRecord,
        *,
        change_plan_id: UUID,
    ) -> ChangePlanVersion:
        """Return the latest ChangePlan version or raise a Day07-scoped error."""

        if not record.versions:
            raise ChangeBatchPlanNotFoundError(
                f"Change plan has no persisted versions: {change_plan_id}"
            )

        return record.versions[0]

    def _order_plan_snapshots(
        self,
        plan_snapshots: list[ChangeBatchPlanSnapshot],
    ) -> list[ChangeBatchPlanSnapshot]:
        """Return selected snapshots in dependency-safe order and reject invalid graphs."""

        task_to_snapshot = {
            snapshot.task_id: snapshot for snapshot in plan_snapshots
        }
        if len(task_to_snapshot) != len(plan_snapshots):
            raise ChangeBatchPlanTaskConflictError(
                "Selected change plans must map to distinct tasks."
            )

        original_order = {
            snapshot.task_id: index for index, snapshot in enumerate(plan_snapshots)
        }
        indegree: dict[UUID, int] = {}
        outgoing: dict[UUID, list[UUID]] = {
            snapshot.task_id: [] for snapshot in plan_snapshots
        }

        for snapshot in plan_snapshots:
            dependency_ids = []
            for dependency_id in snapshot.depends_on_task_ids:
                if dependency_id == snapshot.task_id:
                    raise ChangeBatchPlanTaskConflictError(
                        f"Task cannot depend on itself inside change batch: {snapshot.task_id}"
                    )
                if dependency_id not in task_to_snapshot:
                    continue
                dependency_ids.append(dependency_id)

            unique_dependency_ids = list(dict.fromkeys(dependency_ids))
            indegree[snapshot.task_id] = len(unique_dependency_ids)
            for dependency_id in unique_dependency_ids:
                outgoing[dependency_id].append(snapshot.task_id)

        ready_queue = deque(
            sorted(
                (task_id for task_id, degree in indegree.items() if degree == 0),
                key=lambda task_id: original_order[task_id],
            )
        )
        ordered_snapshots: list[ChangeBatchPlanSnapshot] = []

        while ready_queue:
            task_id = ready_queue.popleft()
            ordered_snapshots.append(task_to_snapshot[task_id])

            next_ready_ids: list[UUID] = []
            for dependent_id in outgoing[task_id]:
                indegree[dependent_id] -= 1
                if indegree[dependent_id] == 0:
                    next_ready_ids.append(dependent_id)

            for dependent_id in sorted(next_ready_ids, key=lambda item: original_order[item]):
                ready_queue.append(dependent_id)

        if len(ordered_snapshots) != len(plan_snapshots):
            raise ChangeBatchPlanTaskConflictError(
                "Selected change plans contain a task dependency cycle."
            )

        return ordered_snapshots

    @staticmethod
    def _build_target_file_views(
        plan_snapshots: list[ChangeBatchPlanSnapshot],
    ) -> list[ChangeBatchTargetFileView]:
        """Aggregate all selected target files into one Day07 repository-level view."""

        aggregated_items: dict[str, dict[str, object]] = {}
        for snapshot in plan_snapshots:
            for target_file in snapshot.target_files:
                entry = aggregated_items.setdefault(
                    target_file.relative_path,
                    {
                        "relative_path": target_file.relative_path,
                        "language": target_file.language,
                        "file_type": target_file.file_type,
                        "match_reasons": [],
                        "rationales": [],
                        "task_ids": [],
                        "task_titles": [],
                        "change_plan_ids": [],
                        "change_plan_titles": [],
                    },
                )
                ChangeBatchService._append_unique_strings(
                    entry["match_reasons"],
                    list(target_file.match_reasons),
                )
                if target_file.rationale:
                    ChangeBatchService._append_unique_strings(
                        entry["rationales"],
                        [target_file.rationale],
                    )
                ChangeBatchService._append_unique_uuid(entry["task_ids"], snapshot.task_id)
                ChangeBatchService._append_unique_strings(
                    entry["task_titles"],
                    [snapshot.task_title],
                )
                ChangeBatchService._append_unique_uuid(
                    entry["change_plan_ids"],
                    snapshot.change_plan_id,
                )
                ChangeBatchService._append_unique_strings(
                    entry["change_plan_titles"],
                    [snapshot.change_plan_title],
                )

        return [
            ChangeBatchTargetFileView(
                relative_path=item["relative_path"],
                language=item["language"],
                file_type=item["file_type"],
                match_reasons=list(item["match_reasons"]),
                rationales=list(item["rationales"]),
                task_ids=list(item["task_ids"]),
                task_titles=list(item["task_titles"]),
                change_plan_ids=list(item["change_plan_ids"]),
                change_plan_titles=list(item["change_plan_titles"]),
                overlap_count=len(item["change_plan_ids"]),
            )
            for item in sorted(
                aggregated_items.values(),
                key=lambda item: (
                    -len(item["change_plan_ids"]),
                    item["relative_path"],
                ),
            )
        ]

    @staticmethod
    def _append_unique_strings(target: object, values: list[str]) -> None:
        """Append unique strings into one mutable list stored inside a dict."""

        target_list = target  # help mypy / pyright for local mutation
        if not isinstance(target_list, list):
            return

        for value in values:
            if value in target_list:
                continue
            target_list.append(value)

    @staticmethod
    def _append_unique_uuid(target: object, value: UUID) -> None:
        """Append one unique UUID into one mutable list stored inside a dict."""

        target_list = target
        if not isinstance(target_list, list) or value in target_list:
            return

        target_list.append(value)

    @staticmethod
    def _build_timeline(change_batch: ChangeBatch) -> list[ChangeBatchTimelineEntry]:
        """Build one Day07-local timeline without entering global Day11 event aggregation."""

        entries = [
            ChangeBatchTimelineEntry(
                entry_type="change_batch_created",
                label="创建变更批次",
                summary=change_batch.summary,
                occurred_at=change_batch.created_at,
            )
        ]
        entries.extend(
            ChangeBatchTimelineEntry(
                entry_type="change_plan_snapshot",
                label=f"纳入 ChangePlan v{snapshot.selected_version_number}",
                summary=(
                    f"{snapshot.task_title} / {snapshot.change_plan_title}"
                    f" · {len(snapshot.target_files)} 个目标文件"
                ),
                occurred_at=snapshot.captured_at,
            )
            for snapshot in change_batch.plan_snapshots
        )
        return sorted(
            entries,
            key=lambda item: (item.occurred_at, item.label),
            reverse=True,
        )

    @staticmethod
    def _resolve_title(
        *,
        title: str | None,
        plan_snapshots: list[ChangeBatchPlanSnapshot],
    ) -> str:
        """Build one stable Day07 batch title when the caller does not provide one."""

        normalized_title = (title or "").strip()
        if normalized_title:
            return normalized_title

        first_task_title = plan_snapshots[0].task_title
        remaining_count = len(plan_snapshots) - 1
        generated_title = (
            f"{first_task_title} 等 {len(plan_snapshots)} 项执行准备"
            if remaining_count > 0
            else f"{first_task_title} 执行准备"
        )
        if len(generated_title) <= 200:
            return generated_title

        return generated_title[:197].rstrip() + "..."

    @staticmethod
    def _build_summary(
        *,
        plan_snapshots: list[ChangeBatchPlanSnapshot],
        target_files: list[ChangeBatchTargetFileView],
        overlap_files: list[ChangeBatchTargetFileView],
    ) -> str:
        """Build one short Day07 batch summary stored on the head row."""

        sequence_preview = " → ".join(
            snapshot.task_title for snapshot in plan_snapshots[:3]
        )
        if len(plan_snapshots) > 3:
            sequence_preview += f" → +{len(plan_snapshots) - 3} 项"

        overlap_summary = (
            f"{len(overlap_files)} 个文件存在重叠提醒"
            if overlap_files
            else "当前未发现文件重叠"
        )
        summary = (
            f"覆盖 {len(plan_snapshots)} 个 ChangePlan、"
            f"{len(target_files)} 个目标文件；建议顺序：{sequence_preview}；"
            f"{overlap_summary}。"
        )
        if len(summary) <= 1_200:
            return summary

        return summary[:1_197].rstrip() + "..."

    def _ensure_project_exists(self, project_id: UUID) -> None:
        """Validate that one project exists before Day07 batch work begins."""

        if self.project_repository.get_by_id(project_id) is None:
            raise ChangeBatchProjectNotFoundError(f"Project not found: {project_id}")

    def _require_repository_workspace(self, project_id: UUID) -> RepositoryWorkspace:
        """Require one bound repository workspace before execution preparation."""

        workspace = self.repository_workspace_repository.get_by_project_id(project_id)
        if workspace is None:
            raise ChangeBatchWorkspaceNotFoundError(
                f"Repository workspace not found for project: {project_id}"
            )

        return workspace

    def _build_project_deliverable_map(
        self,
        project_id: UUID,
    ) -> dict[UUID, ChangeBatchLinkedDeliverable]:
        """Return project deliverables keyed by ID for stable Day07 snapshots."""

        return {
            record.deliverable.id: ChangeBatchLinkedDeliverable(
                deliverable_id=record.deliverable.id,
                title=record.deliverable.title,
                type=record.deliverable.type,
                current_version_number=record.deliverable.current_version_number,
            )
            for record in self.deliverable_repository.list_records_by_project_id(project_id)
        }
