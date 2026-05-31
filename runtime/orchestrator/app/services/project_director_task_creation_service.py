"""AI Project Director formal project/task creation service.

Stage 4-B3-A adds an explicit user action that turns a confirmed
Project Director draft into a formal Project plus a pending Task queue.

Strict boundary:
- Does NOT call planning/apply.
- Does NOT dispatch workers.
- Does NOT write repositories.
- Does NOT call AI Providers.
- Does NOT auto-execute tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.domain.project import Project, ProjectStage, ProjectStatus
from app.domain.project_director_plan_version import (
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
    ProposedTask,
)
from app.domain.project_director_task_creation import (
    ProjectDirectorTaskCreationRecord,
)
from app.domain.project_role import ProjectRoleCode
from app.domain.task import Task, TaskPriority
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_task_creation_repository import (
    ProjectDirectorTaskCreationRecordRepository,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository


_PRIORITY_MAP: dict[str, TaskPriority] = {
    "high": TaskPriority.HIGH,
    "urgent": TaskPriority.URGENT,
    "low": TaskPriority.LOW,
}

_BOUNDARY_ACTIONS = [
    "不自动调用 Worker",
    "Do not auto-dispatch Worker",
    "Do not auto-execute tasks",
    "Do not call planning/apply",
    "Do not call apply-local",
    "Do not write repository files",
    "Do not call real AI providers",
    "Do not create Agent Sessions",
    "Do not create real Skill bindings",
    "Do not create real repository bindings",
]


def _map_priority(priority_hint: str) -> TaskPriority:
    """Map plan version priority_hint to TaskPriority."""
    return _PRIORITY_MAP.get(priority_hint.lower(), TaskPriority.NORMAL)


@dataclass(slots=True)
class TaskCreationResult:
    """Immutable result of a plan-version formalization batch."""

    plan_version_id: UUID
    session_id: UUID
    project_id: UUID
    project_name: str | None
    created_task_ids: list[UUID]
    task_count: int
    status: str
    already_created: bool
    next_action: str
    forbidden_actions: list[str]
    gate_conclusion: str


class ProjectDirectorTaskCreationService:
    """Creates formal Projects and real tasks from confirmed draft plans."""

    def __init__(
        self,
        *,
        plan_repo: ProjectDirectorPlanVersionRepository,
        task_repo: TaskRepository,
        creation_repo: ProjectDirectorTaskCreationRecordRepository,
        project_repo: ProjectRepository,
    ) -> None:
        self._plan_repo = plan_repo
        self._task_repo = task_repo
        self._creation_repo = creation_repo
        self._project_repo = project_repo

    def create_tasks_from_plan_version(
        self, plan_version_id: UUID
    ) -> TaskCreationResult:
        """Create tasks for a confirmed plan already bound to a Project.

        This preserves the existing BCG-04A API contract: duplicate calls
        still raise a conflict and unbound plan versions are rejected.
        """

        plan_version = self._require_confirmed_plan_version(
            plan_version_id,
            action_name="create tasks",
        )

        if plan_version.project_id is None:
            raise ValueError(
                "Plan version must have a project_id to create tasks. "
                "Please create the plan version from a session that is bound to a project."
            )

        existing = self._creation_repo.get_by_plan_version_id(plan_version_id)
        if existing is not None:
            raise ValueError(
                f"Tasks have already been created for plan version {plan_version_id}. "
                f"Existing creation record: {existing.id}. "
                f"Use GET /project-director/plan-versions/{plan_version_id}/created-tasks "
                f"to retrieve the previously created task IDs."
            )

        if not self._project_repo.exists(plan_version.project_id):
            raise ValueError(
                f"Project {plan_version.project_id} not found. "
                f"The project may have been deleted."
            )

        self._ensure_proposed_tasks_are_valid(plan_version)
        return self._create_task_queue_for_plan_version(plan_version)

    def create_formal_project_from_plan_version(
        self, plan_version_id: UUID
    ) -> TaskCreationResult:
        """Create/read formal Project + Task queue for a confirmed draft.

        This is the Stage 4-B3-A explicit user action. It is idempotent:
        repeated calls return the previous creation record and never duplicate
        the Project or Tasks.
        """

        plan_version = self._require_confirmed_plan_version(
            plan_version_id,
            action_name="create a formal project",
        )

        existing = self._creation_repo.get_by_plan_version_id(plan_version_id)
        if existing is not None:
            return self._result_from_record(existing, already_created=True)

        self._ensure_proposed_tasks_are_valid(plan_version)

        if plan_version.project_id is None:
            project = self._project_repo.add_no_commit(
                self._build_project_from_plan_version(plan_version)
            )
            plan_version = self._plan_repo.bind_project_no_commit(
                plan_version.id,
                project.id,
            )
        elif not self._project_repo.exists(plan_version.project_id):
            raise ValueError(
                f"Project {plan_version.project_id} not found. "
                f"The project may have been deleted."
            )

        return self._create_task_queue_for_plan_version(plan_version)

    def get_created_tasks(
        self, plan_version_id: UUID
    ) -> TaskCreationResult | None:
        """Return the task/project creation result for a plan version, or None."""
        record = self._creation_repo.get_by_plan_version_id(plan_version_id)
        if record is None:
            return None
        return self._result_from_record(record, already_created=False)

    def _require_confirmed_plan_version(
        self,
        plan_version_id: UUID,
        *,
        action_name: str,
    ) -> ProjectDirectorPlanVersion:
        plan_version = self._plan_repo.get_by_id(plan_version_id)
        if plan_version is None:
            raise ValueError(f"Plan version {plan_version_id} not found")

        if plan_version.status != PlanVersionStatus.CONFIRMED:
            raise ValueError(
                f"Plan version is in '{plan_version.status}' status. "
                f"Only 'confirmed' plan versions can {action_name}."
            )
        return plan_version

    def _create_task_queue_for_plan_version(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> TaskCreationResult:
        """Create tasks + creation record for an already validated plan."""

        created_tasks = self._create_tasks_atomic(plan_version)
        record = ProjectDirectorTaskCreationRecord(
            id=uuid4(),
            plan_version_id=plan_version.id,
            session_id=plan_version.session_id,
            project_id=plan_version.project_id,
            version_no=plan_version.version_no,
            source_type="project_director_plan_version",
            task_ids=[t.id for t in created_tasks],
            task_count=len(created_tasks),
        )

        try:
            self._creation_repo.create(record)
        except Exception:
            # Roll back any uncommitted Project, plan-version binding, and Tasks.
            self._task_repo.session.rollback()
            raise ValueError(
                "Failed to persist task creation record. "
                "No project or tasks were created. Please try again."
            )

        for task in created_tasks:
            self._task_repo.publish_created(task)

        return TaskCreationResult(
            plan_version_id=plan_version.id,
            session_id=plan_version.session_id,
            project_id=plan_version.project_id,
            project_name=self._get_project_name(plan_version.project_id),
            created_task_ids=[t.id for t in created_tasks],
            task_count=len(created_tasks),
            status="created",
            already_created=False,
            next_action=(
                "Formal Project and pending Task queue were created. "
                "Worker dispatch remains a separate manual action."
            ),
            forbidden_actions=_BOUNDARY_ACTIONS,
            gate_conclusion=(
                "Partial (formal Project + Task queue creation Pass; "
                "Worker execution not completed)"
            ),
        )

    def _result_from_record(
        self,
        record: ProjectDirectorTaskCreationRecord,
        *,
        already_created: bool,
    ) -> TaskCreationResult:
        return TaskCreationResult(
            plan_version_id=record.plan_version_id,
            session_id=record.session_id,
            project_id=record.project_id,
            project_name=self._get_project_name(record.project_id),
            created_task_ids=record.task_ids,
            task_count=record.task_count,
            status="already_created" if already_created else "created",
            already_created=already_created,
            next_action=(
                "This confirmed draft already has a formal Project and Task queue. "
                "The request returned the existing record and did not duplicate anything."
                if already_created
                else "Formal Project and pending Task queue have been created."
            ),
            forbidden_actions=[*_BOUNDARY_ACTIONS, "Do not duplicate Project/Tasks"],
            gate_conclusion=(
                "Partial (formal Project + Task queue creation record already exists)"
                if already_created
                else "Partial (formal Project + Task queue creation Pass)"
            ),
        )

    def _build_project_from_plan_version(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> Project:
        summary = plan_version.plan_summary.strip()
        if not summary:
            summary = (
                f"Formal project created from Project Director plan version "
                f"{plan_version.id}."
            )

        first_line = next(
            (line.strip() for line in summary.splitlines() if line.strip()),
            f"Project Director Plan v{plan_version.version_no}",
        )

        return Project(
            name=first_line[:120],
            summary=summary[:2000],
            status=ProjectStatus.ACTIVE,
            stage=ProjectStage.PLANNING,
        )

    def _get_project_name(self, project_id: UUID | None) -> str | None:
        if project_id is None:
            return None
        project = self._project_repo.get_by_id(project_id)
        return project.name if project is not None else None

    @staticmethod
    def _build_input_summary(pt: ProposedTask) -> str:
        """Build input_summary from proposed_task, falling back for empty description."""
        if pt.description and pt.description.strip():
            return pt.description.strip()
        return f"由计划版本生成的任务: {pt.title}"

    @staticmethod
    def _validate_proposed_tasks(
        plan_version: ProjectDirectorPlanVersion,
    ) -> list[str]:
        """Pre-validate all proposed_tasks before any DB write."""
        errors: list[str] = []
        valid_role_codes = {r.value for r in ProjectRoleCode}

        for i, pt in enumerate(plan_version.proposed_tasks):
            if not pt.title or not pt.title.strip():
                errors.append(f"Proposed task {i} has empty title")
            if pt.suggested_role_code.value not in valid_role_codes:
                errors.append(
                    f"Proposed task {i} ('{pt.title}') has invalid "
                    f"role_code: {pt.suggested_role_code.value}"
                )
            hint = pt.priority_hint.lower()
            if hint not in _PRIORITY_MAP and hint != "normal":
                errors.append(
                    f"Proposed task {i} ('{pt.title}') has unmappable "
                    f"priority_hint: '{pt.priority_hint}'"
                )

        return errors

    @staticmethod
    def _ensure_proposed_tasks_are_valid(
        plan_version: ProjectDirectorPlanVersion,
    ) -> None:
        validation_errors = ProjectDirectorTaskCreationService._validate_proposed_tasks(
            plan_version
        )
        if validation_errors:
            raise ValueError(
                "Proposed task validation failed: "
                + "; ".join(validation_errors)
            )

    def _create_tasks_atomic(
        self, plan_version: ProjectDirectorPlanVersion
    ) -> list[Task]:
        """Convert proposed_tasks into real Tasks without committing."""
        created: list[Task] = []
        source_draft_id = f"pdv:{plan_version.id}:{plan_version.version_no}"

        try:
            for pt in plan_version.proposed_tasks:
                task = Task(
                    project_id=plan_version.project_id,
                    title=pt.title,
                    input_summary=self._build_input_summary(pt),
                    priority=_map_priority(pt.priority_hint),
                    owner_role_code=pt.suggested_role_code,
                    source_draft_id=source_draft_id,
                )
                created.append(self._task_repo.add_no_commit(task))
            return created
        except Exception:
            self._task_repo.session.rollback()
            raise
