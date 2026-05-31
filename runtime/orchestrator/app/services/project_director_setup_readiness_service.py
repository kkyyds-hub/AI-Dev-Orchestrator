"""Read-only setup readiness aggregation for AI Project Director projects.

This service only reads existing Project, Task, Project Director draft, and
review-config rows. It never creates Runs, Agent Sessions, Skill bindings,
Repository workspaces, provider calls, worker dispatches, validation commands,
planning/apply actions, local apply actions, product git commits, or repository
writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db_tables import ProjectDirectorTaskCreationRecordTable
from app.domain.task import TaskStatus
from app.repositories.project_director_agent_team_config_repository import (
    ProjectDirectorAgentTeamConfigRepository,
)
from app.repositories.project_director_repository_binding_config_repository import (
    ProjectDirectorRepositoryBindingConfigRepository,
)
from app.repositories.project_director_skill_binding_config_repository import (
    ProjectDirectorSkillBindingConfigRepository,
)
from app.repositories.project_director_verification_config_repository import (
    ProjectDirectorVerificationConfigRepository,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository

SetupConfigStatus = str


_READ_ONLY_WARNINGS = [
    "该接口只读，只汇总既有项目、任务和 AI 主管配置状态。",
    "不会启动 Worker。",
    "不会创建 Run。",
    "不会执行验证命令。",
    "不会调用 subprocess / os.system / shell。",
    "不会写仓库。",
    "不会调用 provider / planning/apply / apply-local / git-commit。",
]


@dataclass(frozen=True)
class ProjectDirectorSetupReadiness:
    project_id: UUID
    source_plan_version_id: UUID | None
    source_draft_id: str | None
    created_by_director: bool
    formal_project_created: bool
    task_queue_created: bool
    task_count: int
    pending_task_count: int
    agent_team_config_status: SetupConfigStatus
    skill_binding_config_status: SetupConfigStatus
    repository_binding_config_status: SetupConfigStatus
    verification_config_status: SetupConfigStatus
    pending_confirmation_count: int
    rejected_count: int
    confirmed_count: int
    ready_for_manual_execution: bool
    next_steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ProjectDirectorSetupReadinessService:
    """Build a read-only readiness summary for one project."""

    def __init__(
        self,
        *,
        session: Session,
        project_repo: ProjectRepository,
        task_repo: TaskRepository,
        agent_team_config_repo: ProjectDirectorAgentTeamConfigRepository,
        skill_binding_config_repo: ProjectDirectorSkillBindingConfigRepository,
        repository_binding_config_repo: ProjectDirectorRepositoryBindingConfigRepository,
        verification_config_repo: ProjectDirectorVerificationConfigRepository,
    ) -> None:
        self._session = session
        self._project_repo = project_repo
        self._task_repo = task_repo
        self._agent_team_config_repo = agent_team_config_repo
        self._skill_binding_config_repo = skill_binding_config_repo
        self._repository_binding_config_repo = repository_binding_config_repo
        self._verification_config_repo = verification_config_repo

    def get_project_setup_readiness(
        self,
        project_id: UUID,
    ) -> ProjectDirectorSetupReadiness:
        """Return a project setup-readiness snapshot without side effects."""

        project = self._project_repo.get_by_id(project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        tasks = self._task_repo.list_by_project_id(project_id)
        creation_record = self._get_creation_record(project_id)
        task_source_draft_id = next(
            (
                task.source_draft_id
                for task in tasks
                if self._extract_project_director_plan_version_id(
                    task.source_draft_id
                )
                is not None
            ),
            None,
        )
        source_draft_id = (
            self._source_draft_id_from_record(creation_record)
            if creation_record is not None
            else task_source_draft_id
        )
        source_plan_version_id = (
            creation_record.plan_version_id
            if creation_record is not None
            else self._extract_project_director_plan_version_id(source_draft_id)
        )

        config_statuses = {
            "agent_team": self._status_or_missing(
                self._agent_team_config_repo.get_by_project_id(project_id)
            ),
            "skill_binding": self._status_or_missing(
                self._skill_binding_config_repo.get_by_project_id(project_id)
            ),
            "repository_binding": self._status_or_missing(
                self._repository_binding_config_repo.get_by_project_id(project_id)
            ),
            "verification": self._status_or_missing(
                self._verification_config_repo.get_by_project_id(project_id)
            ),
        }

        task_count = len(tasks)
        pending_task_count = sum(1 for task in tasks if task.status == TaskStatus.PENDING)
        created_by_director = source_plan_version_id is not None
        task_queue_created = task_count > 0
        pending_confirmation_count = self._count_status(
            config_statuses.values(), "pending_confirmation"
        )
        rejected_count = self._count_status(config_statuses.values(), "rejected")
        confirmed_count = self._count_status(config_statuses.values(), "confirmed")
        missing_count = self._count_status(config_statuses.values(), "missing")
        ready_for_manual_execution = (
            created_by_director
            and task_queue_created
            and confirmed_count == 4
            and pending_confirmation_count == 0
            and rejected_count == 0
            and missing_count == 0
        )

        return ProjectDirectorSetupReadiness(
            project_id=project_id,
            source_plan_version_id=source_plan_version_id,
            source_draft_id=source_draft_id,
            created_by_director=created_by_director,
            formal_project_created=created_by_director,
            task_queue_created=task_queue_created,
            task_count=task_count,
            pending_task_count=pending_task_count,
            agent_team_config_status=config_statuses["agent_team"],
            skill_binding_config_status=config_statuses["skill_binding"],
            repository_binding_config_status=config_statuses["repository_binding"],
            verification_config_status=config_statuses["verification"],
            pending_confirmation_count=pending_confirmation_count,
            rejected_count=rejected_count,
            confirmed_count=confirmed_count,
            ready_for_manual_execution=ready_for_manual_execution,
            next_steps=self._build_next_steps(
                created_by_director=created_by_director,
                task_queue_created=task_queue_created,
                pending_confirmation_count=pending_confirmation_count,
                rejected_count=rejected_count,
                missing_count=missing_count,
                ready_for_manual_execution=ready_for_manual_execution,
            ),
            warnings=list(_READ_ONLY_WARNINGS),
        )

    def _get_creation_record(
        self,
        project_id: UUID,
    ) -> ProjectDirectorTaskCreationRecordTable | None:
        statement = (
            select(ProjectDirectorTaskCreationRecordTable)
            .where(ProjectDirectorTaskCreationRecordTable.project_id == project_id)
            .order_by(ProjectDirectorTaskCreationRecordTable.created_at.desc())
        )
        return self._session.execute(statement).scalars().first()

    @staticmethod
    def _source_draft_id_from_record(
        record: ProjectDirectorTaskCreationRecordTable | None,
    ) -> str | None:
        if record is None:
            return None
        return f"pdv:{record.plan_version_id}:{record.version_no}"

    @staticmethod
    def _extract_project_director_plan_version_id(
        source_draft_id: str | None,
    ) -> UUID | None:
        if not source_draft_id:
            return None
        parts = source_draft_id.split(":")
        if len(parts) < 3 or parts[0] != "pdv":
            return None
        try:
            return UUID(parts[1])
        except ValueError:
            return None

    @staticmethod
    def _status_or_missing(config: object | None) -> SetupConfigStatus:
        if config is None:
            return "missing"
        status = getattr(config, "status", None)
        return str(getattr(status, "value", status))

    @staticmethod
    def _count_status(statuses, target: str) -> int:
        return sum(1 for status_value in statuses if status_value == target)

    @staticmethod
    def _build_next_steps(
        *,
        created_by_director: bool,
        task_queue_created: bool,
        pending_confirmation_count: int,
        rejected_count: int,
        missing_count: int,
        ready_for_manual_execution: bool,
    ) -> list[str]:
        steps: list[str] = []
        if not created_by_director:
            return ["普通项目：未识别到 AI 主管草案来源，不按 AI 主管创建项目展示。"]
        if not task_queue_created:
            steps.append("尚未识别到 pending Task 队列，请先确认是否已创建正式任务队列。")
        if pending_confirmation_count:
            steps.append(f"还有 {pending_confirmation_count} 类 AI 主管建议配置待确认。")
        if rejected_count:
            steps.append("存在已拒绝配置，请先处理被拒绝配置或重新生成/调整对应建议。")
        if missing_count:
            steps.append(f"还有 {missing_count} 类 AI 主管建议配置未生成。")
        if ready_for_manual_execution:
            steps.append("所有建议配置已确认；用户可以手动考虑启动 Worker，但本接口不会自动启动。")
        if not steps:
            steps.append("继续在项目详情页确认配置状态；本接口不会执行任何运行时动作。")
        return steps
