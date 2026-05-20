"""AI Project Director Task Creation service.

BCG-04A Phase1: creates real Task objects from a confirmed plan version.

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


# ── Priority mapping ────────────────────────────────────────────────

_PRIORITY_MAP: dict[str, TaskPriority] = {
    "high": TaskPriority.HIGH,
    "urgent": TaskPriority.URGENT,
    "low": TaskPriority.LOW,
}


def _map_priority(priority_hint: str) -> TaskPriority:
    """Map plan version priority_hint to TaskPriority."""
    return _PRIORITY_MAP.get(priority_hint.lower(), TaskPriority.NORMAL)


# ── Result ──────────────────────────────────────────────────────────


@dataclass(slots=True)
class TaskCreationResult:
    """Immutable result of a plan-to-task creation batch."""

    plan_version_id: UUID
    session_id: UUID
    project_id: UUID
    created_task_ids: list[UUID]
    task_count: int
    status: str
    next_action: str
    forbidden_actions: list[str]
    gate_conclusion: str


# ── Service ──────────────────────────────────────────────────────────


class ProjectDirectorTaskCreationService:
    """Creates real tasks from a confirmed Project Director plan version."""

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

    # ── Public API ──────────────────────────────────────────────────

    def create_tasks_from_plan_version(
        self, plan_version_id: UUID
    ) -> TaskCreationResult:
        """Create real tasks from a confirmed plan version.

        Atomic guarantee: either all tasks AND the creation record are
        persisted, or nothing is. Pre-validates all proposed_tasks
        before any database write.

        Raises ValueError with distinct messages for:
        - Plan version not found
        - Plan version not in 'confirmed' status
        - Plan version has no project_id
        - Tasks already created for this plan version
        - Project not found
        - Proposed task validation failures (empty title, invalid role, etc.)
        """

        plan_version = self._plan_repo.get_by_id(plan_version_id)
        if plan_version is None:
            raise ValueError(f"Plan version {plan_version_id} not found")

        if plan_version.status != PlanVersionStatus.CONFIRMED:
            raise ValueError(
                f"Plan version is in '{plan_version.status}' status. "
                f"Only 'confirmed' plan versions can create tasks."
            )

        if plan_version.project_id is None:
            raise ValueError(
                "Plan version must have a project_id to create tasks. "
                "Please create the plan version from a session that is bound to a project."
            )

        # Idempotency guard: one plan version → one creation batch
        existing = self._creation_repo.get_by_plan_version_id(plan_version_id)
        if existing is not None:
            raise ValueError(
                f"Tasks have already been created for plan version {plan_version_id}. "
                f"Existing creation record: {existing.id}. "
                f"Use GET /project-director/plan-versions/{plan_version_id}/created-tasks "
                f"to retrieve the previously created task IDs."
            )

        # Verify project exists
        if not self._project_repo.exists(plan_version.project_id):
            raise ValueError(
                f"Project {plan_version.project_id} not found. "
                f"The project may have been deleted."
            )

        # Pre-validate all proposed_tasks before any DB write
        validation_errors = self._validate_proposed_tasks(plan_version)
        if validation_errors:
            raise ValueError(
                "Proposed task validation failed: "
                + "; ".join(validation_errors)
            )

        # Create tasks (add without commit)
        created_tasks = self._create_tasks_atomic(plan_version)

        # Persist creation record → single commit point for tasks + record
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
            # Rollback the tasks that were added but not yet committed
            self._task_repo.session.rollback()
            raise ValueError(
                "Failed to persist task creation record. "
                "No tasks were created. Please try again."
            )

        return TaskCreationResult(
            plan_version_id=plan_version.id,
            session_id=plan_version.session_id,
            project_id=plan_version.project_id,
            created_task_ids=[t.id for t in created_tasks],
            task_count=len(created_tasks),
            status="created",
            next_action=(
                "任务已创建并进入队列。"
                "后续需手动触发 Worker 调度执行任务。"
                "当前阶段不自动执行。"
            ),
            forbidden_actions=[
                "不自动调用 Worker",
                "不自动执行任务",
                "不调用 planning/apply",
                "不写仓库",
                "不把任务创建等同于任务执行",
            ],
            gate_conclusion="Partial（任务创建闭环 Pass，Worker 执行未完成）",
        )

    def get_created_tasks(
        self, plan_version_id: UUID
    ) -> TaskCreationResult | None:
        """Return the task creation result for a plan version, or None."""
        record = self._creation_repo.get_by_plan_version_id(plan_version_id)
        if record is None:
            return None

        return TaskCreationResult(
            plan_version_id=record.plan_version_id,
            session_id=record.session_id,
            project_id=record.project_id,
            created_task_ids=record.task_ids,
            task_count=record.task_count,
            status="created",
            next_action=(
                "任务已创建并进入队列。"
                "后续需手动触发 Worker 调度执行任务。"
            ),
            forbidden_actions=[
                "不自动调用 Worker",
                "不自动执行任务",
                "不调用 planning/apply",
                "不写仓库",
            ],
            gate_conclusion="Partial（任务创建闭环 Pass，Worker 执行未完成）",
        )

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _build_input_summary(pt: ProposedTask) -> str:
        """Build input_summary from proposed_task, falling back for empty description."""
        if pt.description and pt.description.strip():
            return pt.description.strip()
        return f"由计划版本生成的任务：{pt.title}"

    @staticmethod
    def _validate_proposed_tasks(
        plan_version: ProjectDirectorPlanVersion,
    ) -> list[str]:
        """Pre-validate all proposed_tasks before any DB write.

        Returns a list of error messages. Empty list means all valid.
        Validates: title non-empty, role_code valid, priority_hint mappable.
        """
        errors: list[str] = []
        valid_role_codes = {r.value for r in ProjectRoleCode}

        for i, pt in enumerate(plan_version.proposed_tasks):
            if not pt.title or not pt.title.strip():
                errors.append(
                    f"Proposed task {i} has empty title"
                )
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

    def _create_tasks_atomic(
        self, plan_version: ProjectDirectorPlanVersion
    ) -> list[Task]:
        """Convert proposed_tasks into real Tasks with atomic commit.

        All tasks are added without commit, then the creation record
        commits everything in one transaction. If any step fails,
        the session rolls back, leaving no orphaned tasks.
        """
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
            # Rollback any flushed tasks so the session stays clean
            self._task_repo.session.rollback()
            raise
