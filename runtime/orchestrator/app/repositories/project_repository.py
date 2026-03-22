"""Persistence helpers for `Project` records."""

from collections import Counter
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db_tables import ProjectTable, TaskTable
from app.domain._base import ensure_utc_datetime
from app.domain.project import (
    Project,
    ProjectStage,
    ProjectStageHistoryEntry,
    ProjectTaskStats,
)
from app.domain.task import TaskStatus
from app.repositories.repository_snapshot_repository import (
    RepositorySnapshotRepository,
)
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)


class ProjectRepository:
    """Encapsulate project-related database operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, project: Project) -> Project:
        """Persist a new project and return the stored domain model."""

        project_row = ProjectTable(
            id=project.id,
            name=project.name,
            summary=project.summary,
            status=project.status,
            stage=project.stage,
            sop_template_code=project.sop_template_code,
            stage_history_json=self._serialize_stage_history(project.stage_history),
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

        self.session.add(project_row)
        self.session.commit()
        self.session.refresh(project_row)
        return self._to_domain(project_row, task_stats=ProjectTaskStats())

    def list_all(self) -> list[Project]:
        """Return all projects ordered by creation time descending."""

        statement = (
            select(ProjectTable)
            .options(
                selectinload(ProjectTable.tasks),
                selectinload(ProjectTable.repository_workspace),
                selectinload(ProjectTable.repository_snapshot),
            )
            .order_by(ProjectTable.created_at.desc())
        )
        project_rows = self.session.execute(statement).scalars().all()
        return [
            self._to_domain(
                project_row,
                task_stats=self._build_task_stats(project_row.tasks),
            )
            for project_row in project_rows
        ]

    def get_by_id(self, project_id: UUID) -> Project | None:
        """Return one project by ID, if it exists."""

        statement = (
            select(ProjectTable)
            .options(
                selectinload(ProjectTable.tasks),
                selectinload(ProjectTable.repository_workspace),
                selectinload(ProjectTable.repository_snapshot),
            )
            .where(ProjectTable.id == project_id)
        )
        project_row = self.session.execute(statement).scalar_one_or_none()
        if project_row is None:
            return None

        return self._to_domain(
            project_row,
            task_stats=self._build_task_stats(project_row.tasks),
        )

    def exists(self, project_id: UUID) -> bool:
        """Return whether one project already exists."""

        statement = select(ProjectTable.id).where(ProjectTable.id == project_id)
        return self.session.execute(statement).scalar_one_or_none() is not None

    def update_stage_state(
        self,
        project_id: UUID,
        *,
        stage_history: list[ProjectStageHistoryEntry],
        stage: ProjectStage | None = None,
    ) -> Project:
        """Persist one project stage/history update and return the fresh aggregate."""

        project_row = self.session.get(ProjectTable, project_id)
        if project_row is None:
            raise ValueError(f"Project not found: {project_id}")

        if stage is not None:
            project_row.stage = stage

        project_row.stage_history_json = self._serialize_stage_history(stage_history)
        self.session.commit()
        refreshed_project = self.get_by_id(project_id)
        if refreshed_project is None:
            raise ValueError(f"Project not found after update: {project_id}")

        return refreshed_project

    def update_sop_template(
        self,
        project_id: UUID,
        *,
        sop_template_code: str | None,
    ) -> Project:
        """Persist one project's selected SOP template and return the fresh aggregate."""

        project_row = self.session.get(ProjectTable, project_id)
        if project_row is None:
            raise ValueError(f"Project not found: {project_id}")

        project_row.sop_template_code = sop_template_code
        self.session.commit()

        refreshed_project = self.get_by_id(project_id)
        if refreshed_project is None:
            raise ValueError(f"Project not found after update: {project_id}")

        return refreshed_project

    @staticmethod
    def _build_task_stats(task_rows: list[TaskTable]) -> ProjectTaskStats:
        """Aggregate one minimal task-status snapshot for a project."""

        if not task_rows:
            return ProjectTaskStats()

        status_counts = Counter(task_row.status for task_row in task_rows)
        latest_task_updated_at = max(
            (ensure_utc_datetime(task_row.updated_at) for task_row in task_rows),
            default=None,
        )
        return ProjectTaskStats(
            total_tasks=len(task_rows),
            pending_tasks=status_counts.get(TaskStatus.PENDING, 0),
            running_tasks=status_counts.get(TaskStatus.RUNNING, 0),
            paused_tasks=status_counts.get(TaskStatus.PAUSED, 0),
            waiting_human_tasks=status_counts.get(TaskStatus.WAITING_HUMAN, 0),
            completed_tasks=status_counts.get(TaskStatus.COMPLETED, 0),
            failed_tasks=status_counts.get(TaskStatus.FAILED, 0),
            blocked_tasks=status_counts.get(TaskStatus.BLOCKED, 0),
            last_task_updated_at=latest_task_updated_at,
        )

    @staticmethod
    def _to_domain(
        project_row: ProjectTable,
        *,
        task_stats: ProjectTaskStats,
    ) -> Project:
        """Convert an ORM row back into the domain model."""

        return Project(
            id=project_row.id,
            name=project_row.name,
            summary=project_row.summary,
            status=project_row.status,
            stage=project_row.stage,
            sop_template_code=project_row.sop_template_code,
            task_stats=task_stats,
            repository_workspace=(
                RepositoryWorkspaceRepository.to_domain_model(
                    project_row.repository_workspace
                )
                if project_row.repository_workspace is not None
                else None
            ),
            latest_repository_snapshot=(
                RepositorySnapshotRepository.to_domain_model(
                    project_row.repository_snapshot
                )
                if (
                    project_row.repository_snapshot is not None
                    and project_row.repository_workspace is not None
                    and project_row.repository_snapshot.repository_root_path
                    == project_row.repository_workspace.root_path
                )
                else None
            ),
            stage_history=ProjectRepository._deserialize_stage_history(
                project_row.stage_history_json
            ),
            created_at=ensure_utc_datetime(project_row.created_at),
            updated_at=ensure_utc_datetime(project_row.updated_at),
        )

    @staticmethod
    def _serialize_stage_history(
        stage_history: list[ProjectStageHistoryEntry],
    ) -> str:
        """Store one stage-history list as JSON text in SQLite."""

        return json.dumps(
            [entry.model_dump(mode="json") for entry in stage_history],
            ensure_ascii=False,
        )

    @staticmethod
    def _deserialize_stage_history(
        raw_value: str | None,
    ) -> list[ProjectStageHistoryEntry]:
        """Read one JSON-encoded stage-history list from SQLite."""

        if not raw_value:
            return []

        try:
            decoded_value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded_value, list):
            return []

        normalized_history: list[ProjectStageHistoryEntry] = []
        for item in decoded_value:
            if not isinstance(item, dict):
                continue

            try:
                normalized_history.append(ProjectStageHistoryEntry.model_validate(item))
            except ValueError:
                continue

        return normalized_history
