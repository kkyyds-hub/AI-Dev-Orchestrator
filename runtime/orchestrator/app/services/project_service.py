"""Project service helpers for V3 Day01 / Day03."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from uuid import UUID

from app.domain.project import (
    Project,
    ProjectStage,
    ProjectStageGuard,
    ProjectStageHistoryEntry,
    ProjectStatus,
)
from app.domain.task import Task
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_stage_service import ProjectStageService
from app.services.sop_engine_service import ProjectSopSnapshot, SopEngineService


@dataclass(slots=True, frozen=True)
class ProjectTaskTreeItem:
    """One task node shown inside the Day03 project detail tree."""

    task: Task
    depth: int
    child_task_ids: list[UUID]


@dataclass(slots=True, frozen=True)
class ProjectDetail:
    """Project aggregate enriched with its ordered task tree."""

    project: Project
    task_tree: list[ProjectTaskTreeItem]
    stage_guard: ProjectStageGuard | None = None
    stage_timeline: list[ProjectStageHistoryEntry] | None = None
    sop_snapshot: ProjectSopSnapshot | None = None


class ProjectService:
    """Handle minimal project-oriented business actions."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        task_repository: TaskRepository | None = None,
        project_stage_service: ProjectStageService | None = None,
        sop_engine_service: SopEngineService | None = None,
    ) -> None:
        """Inject project/task repositories for reuse and testing."""

        self.project_repository = project_repository
        self.task_repository = task_repository
        self.project_stage_service = project_stage_service
        self.sop_engine_service = sop_engine_service

    def create_project(
        self,
        *,
        name: str,
        summary: str,
        status: ProjectStatus = ProjectStatus.ACTIVE,
        stage: ProjectStage = ProjectStage.INTAKE,
    ) -> Project:
        """Create one project."""

        project = Project(
            name=name,
            summary=summary,
            status=status,
            stage=stage,
        )
        return self.project_repository.create(project)

    def list_projects(self) -> list[Project]:
        """List all projects."""

        return self.project_repository.list_all()

    def get_project(self, project_id: UUID) -> Project | None:
        """Return one project by ID."""

        return self.project_repository.get_by_id(project_id)

    def get_project_detail(self, project_id: UUID) -> ProjectDetail | None:
        """Return one project together with its Day03 task-tree payload."""

        project = self.project_repository.get_by_id(project_id)
        if project is None:
            return None

        if self.task_repository is None:
            stage_guard = (
                self.project_stage_service.get_project_stage_guard(project)
                if self.project_stage_service is not None
                else None
            )
            sop_snapshot = (
                self.sop_engine_service.get_project_sop_snapshot(
                    project=project,
                    tasks=[],
                    next_stage=stage_guard.target_stage if stage_guard is not None else None,
                    can_advance=stage_guard.can_advance if stage_guard is not None else None,
                    blocking_reasons=stage_guard.blocking_reasons if stage_guard is not None else [],
                )
                if self.sop_engine_service is not None
                else None
            )
            return ProjectDetail(
                project=project,
                task_tree=[],
                stage_guard=stage_guard,
                stage_timeline=list(project.stage_history),
                sop_snapshot=sop_snapshot,
            )

        project_tasks = self.task_repository.list_by_project_id(project_id)
        stage_guard = (
            self.project_stage_service.evaluate_stage_guard(
                project=project,
                tasks=project_tasks,
            )
            if self.project_stage_service is not None
            else None
        )
        sop_snapshot = (
            self.sop_engine_service.get_project_sop_snapshot(
                project=project,
                tasks=project_tasks,
                next_stage=stage_guard.target_stage if stage_guard is not None else None,
                can_advance=stage_guard.can_advance if stage_guard is not None else None,
                blocking_reasons=stage_guard.blocking_reasons if stage_guard is not None else [],
            )
            if self.sop_engine_service is not None
            else None
        )
        return ProjectDetail(
            project=project,
            task_tree=self._build_task_tree(project_tasks),
            stage_guard=stage_guard,
            stage_timeline=list(project.stage_history),
            sop_snapshot=sop_snapshot,
        )

    @staticmethod
    def _build_task_tree(tasks: list[Task]) -> list[ProjectTaskTreeItem]:
        """Return project tasks in dependency-safe order with tree depth hints."""

        if not tasks:
            return []

        task_map = {task.id: task for task in tasks}
        original_order = {task.id: index for index, task in enumerate(tasks)}
        internal_dependency_map: dict[UUID, list[UUID]] = {}
        child_task_map: dict[UUID, list[UUID]] = {task.id: [] for task in tasks}
        indegree: dict[UUID, int] = {}

        for task in tasks:
            unique_dependency_ids: list[UUID] = []
            seen_dependency_ids: set[UUID] = set()
            for dependency_id in task.depends_on_task_ids:
                if dependency_id not in task_map or dependency_id in seen_dependency_ids:
                    continue
                unique_dependency_ids.append(dependency_id)
                seen_dependency_ids.add(dependency_id)
                child_task_map[dependency_id].append(task.id)

            internal_dependency_map[task.id] = unique_dependency_ids
            indegree[task.id] = len(unique_dependency_ids)

        ready_queue = deque(
            sorted(
                (task_id for task_id, degree in indegree.items() if degree == 0),
                key=lambda task_id: original_order[task_id],
            )
        )
        task_depth_map: dict[UUID, int] = {}
        ordered_task_tree: list[ProjectTaskTreeItem] = []

        while ready_queue:
            task_id = ready_queue.popleft()
            dependency_ids = internal_dependency_map[task_id]
            task_depth_map[task_id] = (
                max((task_depth_map[dependency_id] for dependency_id in dependency_ids), default=-1)
                + 1
            )
            ordered_task_tree.append(
                ProjectTaskTreeItem(
                    task=task_map[task_id],
                    depth=task_depth_map[task_id],
                    child_task_ids=sorted(
                        child_task_map[task_id],
                        key=lambda child_task_id: original_order[child_task_id],
                    ),
                )
            )

            next_ready_ids: list[UUID] = []
            for child_task_id in child_task_map[task_id]:
                indegree[child_task_id] -= 1
                if indegree[child_task_id] == 0:
                    next_ready_ids.append(child_task_id)

            for child_task_id in sorted(next_ready_ids, key=lambda item: original_order[item]):
                ready_queue.append(child_task_id)

        if len(ordered_task_tree) == len(tasks):
            return ordered_task_tree

        appended_task_ids = {item.task.id for item in ordered_task_tree}
        for task in tasks:
            if task.id in appended_task_ids:
                continue
            ordered_task_tree.append(
                ProjectTaskTreeItem(
                    task=task,
                    depth=0,
                    child_task_ids=sorted(
                        child_task_map[task.id],
                        key=lambda child_task_id: original_order[child_task_id],
                    ),
                )
            )

        return ordered_task_tree
