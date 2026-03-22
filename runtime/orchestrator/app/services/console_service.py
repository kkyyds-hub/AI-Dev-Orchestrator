"""Console-facing aggregation helpers for the Day08/Day10 UI surfaces and V3 boss homepage."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain._base import ensure_utc_datetime, utc_now
from app.domain.approval import ApprovalStatus
from app.domain.project import Project, ProjectStage, ProjectStatus, ProjectTaskStats
from app.domain.project_role import ProjectRoleCode
from app.domain.run import Run, RunStatus
from app.domain.task import Task, TaskRiskLevel, TaskStatus
from app.repositories.project_repository import ProjectRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.approval_service import ApprovalService, ApprovalStageGate
from app.services.budget_guard_service import BudgetGuardService, BudgetSnapshot
from app.services.context_builder_service import ContextBuilderService, TaskContextPackage
from app.services.role_catalog_service import RoleCatalogService
from app.services.run_logging_service import RunLoggingService


@dataclass(slots=True, frozen=True)
class ConsoleTaskItem:
    """A task together with the latest run info used by the console UI."""

    task: Task
    latest_run: Run | None


@dataclass(slots=True, frozen=True)
class ConsoleOverview:
    """Aggregated data needed by the minimal Day 10 homepage."""

    total_tasks: int
    pending_tasks: int
    running_tasks: int
    paused_tasks: int
    waiting_human_tasks: int
    completed_tasks: int
    failed_tasks: int
    blocked_tasks: int
    total_estimated_cost: float
    total_prompt_tokens: int
    total_completion_tokens: int
    budget: BudgetSnapshot
    tasks: list[ConsoleTaskItem]


@dataclass(slots=True, frozen=True)
class ConsoleTaskDetail:
    """Aggregated task detail payload used by the Day 11 side panel."""

    task: Task
    latest_run: Run | None
    runs: list[Run]
    context_preview: TaskContextPackage


@dataclass(slots=True, frozen=True)
class ConsoleProjectStageItem:
    """One project-stage distribution bucket for the boss homepage."""

    stage: ProjectStage
    count: int


@dataclass(slots=True, frozen=True)
class ConsoleProjectLatestTask:
    """Latest task snapshot surfaced in the project detail panel."""

    task: Task
    latest_run: Run | None


@dataclass(slots=True, frozen=True)
class ConsoleProjectItem:
    """One project row/card shown on the boss homepage."""

    project: Project
    latest_progress_summary: str
    latest_progress_at: datetime | None
    key_risk_summary: str
    risk_level: str
    blocked: bool
    estimated_cost: float
    prompt_tokens: int
    completion_tokens: int
    attention_task_count: int
    high_risk_task_count: int
    latest_task: ConsoleProjectLatestTask | None


@dataclass(slots=True, frozen=True)
class ConsoleProjectOverview:
    """Project-first homepage payload introduced for V3 Day02."""

    total_projects: int
    active_projects: int
    completed_projects: int
    blocked_projects: int
    total_project_tasks: int
    unassigned_tasks: int
    stage_distribution: list[ConsoleProjectStageItem]
    budget: BudgetSnapshot
    projects: list[ConsoleProjectItem]


@dataclass(slots=True, frozen=True)
class ConsoleRoleProfile:
    """One role lane definition used by the Day08 role workbench."""

    role_code: ProjectRoleCode
    role_name: str
    role_summary: str
    enabled: bool
    sort_order: int


@dataclass(slots=True, frozen=True)
class ConsoleRoleWorkbenchTaskItem:
    """A role-workbench task card with its latest run and project context."""

    task: Task
    latest_run: Run | None
    project: Project | None


@dataclass(slots=True, frozen=True)
class ConsoleRoleHandoffItem:
    """One recent role handoff event extracted from structured run logs."""

    id: str
    timestamp: datetime
    task: Task
    latest_run: Run | None
    project: Project | None
    owner_role_code: ProjectRoleCode | None
    upstream_role_code: ProjectRoleCode | None
    downstream_role_code: ProjectRoleCode | None
    dispatch_status: str | None
    handoff_reason: str | None
    message: str
    log_path: str | None


@dataclass(slots=True, frozen=True)
class ConsoleRoleLane:
    """One role column shown on the Day08 workbench."""

    role: ConsoleRoleProfile
    current_tasks: list[ConsoleRoleWorkbenchTaskItem]
    blocked_tasks: list[ConsoleRoleWorkbenchTaskItem]
    running_tasks: list[ConsoleRoleWorkbenchTaskItem]
    recent_handoffs: list[ConsoleRoleHandoffItem]


@dataclass(slots=True, frozen=True)
class ConsoleRoleWorkbenchOverview:
    """Aggregated Day08 payload for the role workbench page."""

    project: Project | None
    scope_label: str
    total_roles: int
    enabled_roles: int
    total_tasks: int
    active_tasks: int
    running_tasks: int
    blocked_tasks: int
    unassigned_tasks: int
    recent_handoff_count: int
    budget: BudgetSnapshot
    lanes: list[ConsoleRoleLane]
    recent_handoffs: list[ConsoleRoleHandoffItem]
    generated_at: datetime


class ConsoleService:
    """Build task-console and boss-homepage aggregation payloads."""

    def __init__(
        self,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        project_repository: ProjectRepository,
        budget_guard_service: BudgetGuardService,
        context_builder_service: ContextBuilderService,
        approval_service: ApprovalService | None = None,
        role_catalog_service: RoleCatalogService | None = None,
        run_logging_service: RunLoggingService | None = None,
    ) -> None:
        self.task_repository = task_repository
        self.run_repository = run_repository
        self.project_repository = project_repository
        self.budget_guard_service = budget_guard_service
        self.context_builder_service = context_builder_service
        self.approval_service = approval_service
        self.role_catalog_service = role_catalog_service
        self.run_logging_service = run_logging_service

    def get_overview(self) -> ConsoleOverview:
        """Return all Day 10 homepage data in one small payload."""

        task_pairs = self.task_repository.list_with_latest_run()
        items = [
            ConsoleTaskItem(task=task, latest_run=latest_run)
            for task, latest_run in task_pairs
        ]

        total_tasks = len(items)
        pending_tasks = self._count_by_status(items, TaskStatus.PENDING)
        running_tasks = self._count_by_status(items, TaskStatus.RUNNING)
        paused_tasks = self._count_by_status(items, TaskStatus.PAUSED)
        waiting_human_tasks = self._count_by_status(items, TaskStatus.WAITING_HUMAN)
        completed_tasks = self._count_by_status(items, TaskStatus.COMPLETED)
        failed_tasks = self._count_by_status(items, TaskStatus.FAILED)
        blocked_tasks = self._count_by_status(items, TaskStatus.BLOCKED)
        total_estimated_cost = round(
            sum(item.latest_run.estimated_cost for item in items if item.latest_run is not None),
            6,
        )
        total_prompt_tokens = sum(
            item.latest_run.prompt_tokens for item in items if item.latest_run is not None
        )
        total_completion_tokens = sum(
            item.latest_run.completion_tokens
            for item in items
            if item.latest_run is not None
        )
        budget = self.budget_guard_service.build_budget_snapshot()

        return ConsoleOverview(
            total_tasks=total_tasks,
            pending_tasks=pending_tasks,
            running_tasks=running_tasks,
            paused_tasks=paused_tasks,
            waiting_human_tasks=waiting_human_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            blocked_tasks=blocked_tasks,
            total_estimated_cost=total_estimated_cost,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            budget=budget,
            tasks=items,
        )

    def get_project_overview(self) -> ConsoleProjectOverview:
        """Return the V3 Day02 boss homepage payload."""

        projects = self.project_repository.list_all()
        task_pairs = self.task_repository.list_with_latest_run()
        grouped_task_items: dict[UUID, list[ConsoleTaskItem]] = defaultdict(list)
        unassigned_tasks = 0

        for task, latest_run in task_pairs:
            item = ConsoleTaskItem(task=task, latest_run=latest_run)
            if task.project_id is None:
                unassigned_tasks += 1
                continue
            grouped_task_items[task.project_id].append(item)

        project_items = [
            self._build_project_item(project, grouped_task_items.get(project.id, []))
            for project in projects
        ]
        risk_order = {"danger": 0, "warning": 1, "healthy": 2}
        project_items.sort(
            key=lambda item: (
                not item.blocked,
                risk_order.get(item.risk_level, 3),
                -(item.latest_progress_at or item.project.updated_at).timestamp(),
            )
        )

        return ConsoleProjectOverview(
            total_projects=len(projects),
            active_projects=sum(1 for project in projects if project.status == ProjectStatus.ACTIVE),
            completed_projects=sum(
                1 for project in projects if project.status == ProjectStatus.COMPLETED
            ),
            blocked_projects=sum(1 for item in project_items if item.blocked),
            total_project_tasks=sum(project.task_stats.total_tasks for project in projects),
            unassigned_tasks=unassigned_tasks,
            stage_distribution=self._build_stage_distribution(projects),
            budget=self.budget_guard_service.build_budget_snapshot(),
            projects=project_items,
        )

    def get_role_workbench(
        self,
        project_id: UUID | None = None,
    ) -> ConsoleRoleWorkbenchOverview | None:
        """Return the Day08 role-workbench snapshot for one project or all projects."""

        selected_project: Project | None = None
        if project_id is not None:
            selected_project = self.project_repository.get_by_id(project_id)
            if selected_project is None:
                return None

        projects = (
            [selected_project]
            if selected_project is not None
            else self.project_repository.list_all()
        )
        project_map = {project.id: project for project in projects}
        task_items = self._build_role_workbench_task_items(project_id=project_id, project_map=project_map)
        role_profiles = self._build_role_profiles(project_id=project_id)
        recent_handoffs = self._collect_recent_role_handoffs(task_items)

        lanes = [
            ConsoleRoleLane(
                role=role_profile,
                current_tasks=self._filter_role_tasks(
                    task_items=task_items,
                    role_code=role_profile.role_code,
                    blocked_only=False,
                    running_only=False,
                ),
                blocked_tasks=self._filter_role_tasks(
                    task_items=task_items,
                    role_code=role_profile.role_code,
                    blocked_only=True,
                    running_only=False,
                ),
                running_tasks=self._filter_role_tasks(
                    task_items=task_items,
                    role_code=role_profile.role_code,
                    blocked_only=False,
                    running_only=True,
                ),
                recent_handoffs=self._filter_role_handoffs(
                    recent_handoffs=recent_handoffs,
                    role_code=role_profile.role_code,
                ),
            )
            for role_profile in role_profiles
        ]

        return ConsoleRoleWorkbenchOverview(
            project=selected_project,
            scope_label=selected_project.name if selected_project is not None else "全部项目",
            total_roles=len(role_profiles),
            enabled_roles=sum(1 for role_profile in role_profiles if role_profile.enabled),
            total_tasks=len(task_items),
            active_tasks=sum(1 for item in task_items if item.task.status != TaskStatus.COMPLETED),
            running_tasks=sum(1 for item in task_items if self._is_running_task(item)),
            blocked_tasks=sum(1 for item in task_items if self._is_blocked_task(item.task)),
            unassigned_tasks=sum(
                1 for item in task_items if item.task.owner_role_code is None
            ),
            recent_handoff_count=len(recent_handoffs),
            budget=self.budget_guard_service.build_budget_snapshot(),
            lanes=lanes,
            recent_handoffs=recent_handoffs[:12],
            generated_at=utc_now(),
        )

    def get_task_runs(self, task_id: UUID) -> list[Run] | None:
        """Return all persisted runs for one task, if the task exists."""

        task = self.task_repository.get_by_id(task_id)
        if task is None:
            return None

        return self.run_repository.list_by_task_id(task_id)

    def get_task_detail(self, task_id: UUID) -> ConsoleTaskDetail | None:
        """Return the Day 11 task detail payload for one task."""

        task = self.task_repository.get_by_id(task_id)
        if task is None:
            return None

        runs = self.run_repository.list_by_task_id(task_id)
        latest_run = runs[0] if runs else None
        context_preview = self.context_builder_service.build_context_package(task=task)
        return ConsoleTaskDetail(
            task=task,
            latest_run=latest_run,
            runs=runs,
            context_preview=context_preview,
        )

    def _build_role_profiles(self, *, project_id: UUID | None) -> list[ConsoleRoleProfile]:
        """Resolve the role lanes shown by the Day08 workbench."""

        if self.role_catalog_service is not None and project_id is not None:
            project_role_catalog = self.role_catalog_service.get_project_role_catalog(project_id)
            if project_role_catalog is not None:
                return sorted(
                    [
                        ConsoleRoleProfile(
                            role_code=role.role_code,
                            role_name=role.name,
                            role_summary=role.summary,
                            enabled=role.enabled,
                            sort_order=role.sort_order,
                        )
                        for role in project_role_catalog.roles
                    ],
                    key=lambda item: (item.sort_order, item.role_name),
                )

        if self.role_catalog_service is not None:
            return sorted(
                [
                    ConsoleRoleProfile(
                        role_code=role.code,
                        role_name=role.name,
                        role_summary=role.summary,
                        enabled=role.enabled_by_default,
                        sort_order=role.sort_order,
                    )
                    for role in self.role_catalog_service.list_system_role_catalog()
                ],
                key=lambda item: (item.sort_order, item.role_name),
            )

        return [
            ConsoleRoleProfile(
                role_code=role_code,
                role_name=role_code.value,
                role_summary="",
                enabled=True,
                sort_order=index,
            )
            for index, role_code in enumerate(ProjectRoleCode, start=1)
        ]

    def _build_role_workbench_task_items(
        self,
        *,
        project_id: UUID | None,
        project_map: dict[UUID, Project],
    ) -> list[ConsoleRoleWorkbenchTaskItem]:
        """Build one scoped task list shared by all role lanes."""

        items: list[ConsoleRoleWorkbenchTaskItem] = []
        for task, latest_run in self.task_repository.list_with_latest_run():
            if task.project_id is None:
                if project_id is not None:
                    continue
                project = None
            else:
                if project_id is not None and task.project_id != project_id:
                    continue
                project = project_map.get(task.project_id)
                if project_id is None and project is None:
                    continue

            items.append(
                ConsoleRoleWorkbenchTaskItem(
                    task=task,
                    latest_run=latest_run,
                    project=project,
                )
            )

        return self._sort_role_task_items(items)

    def _collect_recent_role_handoffs(
        self,
        task_items: list[ConsoleRoleWorkbenchTaskItem],
    ) -> list[ConsoleRoleHandoffItem]:
        """Collect recent role handoff events from the latest run logs."""

        if self.run_logging_service is None:
            return []

        handoff_items: list[ConsoleRoleHandoffItem] = []
        for item in task_items:
            if item.latest_run is None or item.latest_run.log_path is None:
                continue

            log_events = self.run_logging_service.read_events(
                log_path=item.latest_run.log_path,
                limit=50,
            ).events
            for log_event in log_events:
                if log_event.event != "role_handoff":
                    continue

                handoff_items.append(
                    ConsoleRoleHandoffItem(
                        id=f"{item.task.id}:{log_event.timestamp}",
                        timestamp=self._parse_log_timestamp(
                            log_event.timestamp,
                            fallback=item.task.updated_at,
                        ),
                        task=item.task,
                        latest_run=item.latest_run,
                        project=item.project,
                        owner_role_code=self._parse_role_code(
                            log_event.data.get("owner_role_code")
                        ),
                        upstream_role_code=self._parse_role_code(
                            log_event.data.get("upstream_role_code")
                        ),
                        downstream_role_code=self._parse_role_code(
                            log_event.data.get("downstream_role_code")
                        ),
                        dispatch_status=self._coerce_optional_string(
                            log_event.data.get("dispatch_status")
                        ),
                        handoff_reason=self._coerce_optional_string(
                            log_event.data.get("handoff_reason")
                        ),
                        message=log_event.message,
                        log_path=item.latest_run.log_path,
                    )
                )

        return sorted(
            handoff_items,
            key=lambda item: item.timestamp,
            reverse=True,
        )

    def _filter_role_tasks(
        self,
        *,
        task_items: list[ConsoleRoleWorkbenchTaskItem],
        role_code: ProjectRoleCode,
        blocked_only: bool,
        running_only: bool,
    ) -> list[ConsoleRoleWorkbenchTaskItem]:
        """Return the task cards for one role lane and one status slice."""

        scoped_items = [
            item for item in task_items if item.task.owner_role_code == role_code
        ]
        if blocked_only:
            scoped_items = [
                item for item in scoped_items if self._is_blocked_task(item.task)
            ]
        elif running_only:
            scoped_items = [item for item in scoped_items if self._is_running_task(item)]
        else:
            scoped_items = [
                item for item in scoped_items if item.task.status != TaskStatus.COMPLETED
            ]

        return self._sort_role_task_items(scoped_items)

    @staticmethod
    def _filter_role_handoffs(
        *,
        recent_handoffs: list[ConsoleRoleHandoffItem],
        role_code: ProjectRoleCode,
    ) -> list[ConsoleRoleHandoffItem]:
        """Return the recent handoffs that touch one role lane."""

        return [
            handoff
            for handoff in recent_handoffs
            if role_code
            in {
                handoff.owner_role_code,
                handoff.upstream_role_code,
                handoff.downstream_role_code,
            }
        ][:4]

    @classmethod
    def _sort_role_task_items(
        cls,
        items: list[ConsoleRoleWorkbenchTaskItem],
    ) -> list[ConsoleRoleWorkbenchTaskItem]:
        """Sort role lane tasks by urgency and recent activity."""

        return sorted(
            items,
            key=lambda item: (
                cls._task_lane_rank(item.task.status),
                -item.task.updated_at.timestamp(),
                item.task.title,
            ),
        )

    @staticmethod
    def _task_lane_rank(status: TaskStatus) -> int:
        """Return a stable ordering for role-lane task cards."""

        order = {
            TaskStatus.RUNNING: 0,
            TaskStatus.BLOCKED: 1,
            TaskStatus.WAITING_HUMAN: 2,
            TaskStatus.FAILED: 3,
            TaskStatus.PAUSED: 4,
            TaskStatus.PENDING: 5,
            TaskStatus.COMPLETED: 6,
        }
        return order.get(status, 99)

    @staticmethod
    def _is_blocked_task(task: Task) -> bool:
        """Return whether one task should appear in the blocked lane slice."""

        return task.status in {
            TaskStatus.BLOCKED,
            TaskStatus.FAILED,
            TaskStatus.PAUSED,
            TaskStatus.WAITING_HUMAN,
        }

    @staticmethod
    def _is_running_task(item: ConsoleRoleWorkbenchTaskItem) -> bool:
        """Return whether one task/run pair should appear in the running slice."""

        return item.task.status == TaskStatus.RUNNING or (
            item.latest_run is not None
            and item.latest_run.status in {RunStatus.QUEUED, RunStatus.RUNNING}
        )

    @staticmethod
    def _parse_log_timestamp(value: str, *, fallback: datetime) -> datetime:
        """Parse one log timestamp while keeping Day08 payloads UTC-aware."""

        try:
            return ensure_utc_datetime(datetime.fromisoformat(value))
        except ValueError:
            return fallback

    @staticmethod
    def _parse_role_code(value: object) -> ProjectRoleCode | None:
        """Best-effort conversion from raw log payloads back to role enums."""

        if isinstance(value, ProjectRoleCode):
            return value
        if not isinstance(value, str):
            return None

        normalized_value = value.strip()
        if not normalized_value:
            return None

        try:
            return ProjectRoleCode(normalized_value)
        except ValueError:
            return None

    @staticmethod
    def _coerce_optional_string(value: object) -> str | None:
        """Normalize optional string-like payload fields."""

        if value is None:
            return None
        normalized_value = str(value).strip()
        return normalized_value or None

    def _build_project_item(
        self,
        project: Project,
        items: list[ConsoleTaskItem],
    ) -> ConsoleProjectItem:
        """Build one project-card view model from project/task data."""

        latest_task_item = max(
            items,
            key=lambda item: item.task.updated_at,
            default=None,
        )
        latest_task = (
            ConsoleProjectLatestTask(
                task=latest_task_item.task,
                latest_run=latest_task_item.latest_run,
            )
            if latest_task_item is not None
            else None
        )
        high_risk_task_count = sum(
            1 for item in items if item.task.risk_level == TaskRiskLevel.HIGH
        )
        attention_task_count = (
            project.task_stats.blocked_tasks
            + project.task_stats.waiting_human_tasks
            + project.task_stats.failed_tasks
        )
        approval_gate = (
            self.approval_service.build_stage_gate(
                project_id=project.id,
                stage=project.stage,
            )
            if self.approval_service is not None
            else None
        )
        blocked = self._is_project_blocked(
            project.task_stats,
            project.status,
            approval_blocked=approval_gate is not None and not approval_gate.can_advance,
        )
        risk_level, key_risk_summary = self._build_project_risk_summary(
            project=project,
            items=items,
            high_risk_task_count=high_risk_task_count,
            blocked=blocked,
            approval_gate=approval_gate,
        )
        latest_progress_summary, latest_progress_at = self._build_project_progress_summary(
            project=project,
            latest_task=latest_task,
        )
        estimated_cost = round(
            sum(item.latest_run.estimated_cost for item in items if item.latest_run is not None),
            6,
        )
        prompt_tokens = sum(
            item.latest_run.prompt_tokens for item in items if item.latest_run is not None
        )
        completion_tokens = sum(
            item.latest_run.completion_tokens for item in items if item.latest_run is not None
        )

        return ConsoleProjectItem(
            project=project,
            latest_progress_summary=latest_progress_summary,
            latest_progress_at=latest_progress_at,
            key_risk_summary=key_risk_summary,
            risk_level=risk_level,
            blocked=blocked,
            estimated_cost=estimated_cost,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            attention_task_count=attention_task_count,
            high_risk_task_count=high_risk_task_count,
            latest_task=latest_task,
        )

    @staticmethod
    def _build_stage_distribution(projects: list[Project]) -> list[ConsoleProjectStageItem]:
        """Return a stable stage-distribution list in enum order."""

        return [
            ConsoleProjectStageItem(
                stage=stage,
                count=sum(1 for project in projects if project.stage == stage),
            )
            for stage in ProjectStage
        ]

    def _build_project_progress_summary(
        self,
        *,
        project: Project,
        latest_task: ConsoleProjectLatestTask | None,
    ) -> tuple[str, datetime | None]:
        """Summarize one project's latest progress in one boss-friendly sentence."""

        if latest_task is None:
            return (
                "项目已建档，当前还没有挂接任务，等待进入下一步规划或拆解。",
                project.updated_at,
            )

        task_status_label = self._task_status_label(latest_task.task.status)
        if latest_task.latest_run is not None and latest_task.latest_run.result_summary:
            return (
                f"最近更新：任务「{latest_task.task.title}」{task_status_label}，"
                f"摘要：{latest_task.latest_run.result_summary}",
                latest_task.task.updated_at,
            )

        if latest_task.latest_run is not None:
            run_status_label = self._run_status_label(latest_task.latest_run.status)
            return (
                f"最近更新：任务「{latest_task.task.title}」状态为{task_status_label}，"
                f"最新运行结果为{run_status_label}。",
                latest_task.task.updated_at,
            )

        return (
            f"最近更新：任务「{latest_task.task.title}」当前状态为{task_status_label}。",
            latest_task.task.updated_at,
        )

    def _build_project_risk_summary(
        self,
        *,
        project: Project,
        items: list[ConsoleTaskItem],
        high_risk_task_count: int,
        blocked: bool,
        approval_gate: ApprovalStageGate | None,
    ) -> tuple[str, str]:
        """Build one normalized project-risk label and summary."""

        if project.status == ProjectStatus.ON_HOLD:
            return (
                "danger",
                "项目当前处于挂起状态，需要老板确认是否恢复推进。",
            )

        if project.task_stats.blocked_tasks > 0:
            return (
                "danger",
                f"存在 {project.task_stats.blocked_tasks} 个阻塞任务，需要先解除卡点。",
            )

        if approval_gate is not None and not approval_gate.can_advance:
            rejected_count = sum(
                1
                for item in approval_gate.blocking_items
                if item.approval.status == ApprovalStatus.REJECTED
            )
            changes_requested_count = sum(
                1
                for item in approval_gate.blocking_items
                if item.approval.status == ApprovalStatus.CHANGES_REQUESTED
            )
            pending_count = sum(
                1
                for item in approval_gate.blocking_items
                if item.approval.status == ApprovalStatus.PENDING_APPROVAL
            )

            if rejected_count > 0:
                return (
                    "danger",
                    f"有 {rejected_count} 个关键交付件被老板驳回，需先处理审批结论再继续推进。",
                )

            if changes_requested_count > 0:
                return (
                    "warning",
                    f"有 {changes_requested_count} 个关键交付件被要求补充信息，当前阶段仍未通过老板审批。",
                )

            if approval_gate.overdue_requests > 0:
                return (
                    "danger",
                    f"有 {pending_count} 个关键交付件等待老板审批，其中 {approval_gate.overdue_requests} 个已超时。",
                )

            return (
                "warning",
                f"有 {pending_count} 个关键交付件待老板审批，审批通过前不会推进下一阶段。",
            )

        if project.task_stats.waiting_human_tasks > 0:
            return (
                "warning",
                f"有 {project.task_stats.waiting_human_tasks} 个任务等待人工处理或确认。",
            )

        if project.task_stats.failed_tasks > 0:
            return (
                "warning",
                f"最近有 {project.task_stats.failed_tasks} 个任务执行失败，建议优先复盘。",
            )

        if high_risk_task_count > 0:
            return (
                "warning",
                f"包含 {high_risk_task_count} 个高风险任务，建议关注验证与里程碑。",
            )

        if not items:
            return (
                "warning",
                "项目已创建但尚未拆解任务，当前只完成立项建档。",
            )

        if blocked:
            return (
                "warning",
                "项目存在待处理阻塞信号，建议检查人工或预算守卫状态。",
            )

        return (
            "healthy",
            "当前未发现显著阻塞风险，可以继续按阶段推进。",
        )

    @staticmethod
    def _is_project_blocked(
        task_stats: ProjectTaskStats,
        project_status: ProjectStatus,
        *,
        approval_blocked: bool = False,
    ) -> bool:
        """Return whether the project should be surfaced as blocked on the homepage."""

        return (
            project_status == ProjectStatus.ON_HOLD
            or task_stats.blocked_tasks > 0
            or task_stats.waiting_human_tasks > 0
            or approval_blocked
        )

    @staticmethod
    def _count_by_status(items: list[ConsoleTaskItem], status: TaskStatus) -> int:
        """Count tasks for a single status bucket."""

        return sum(1 for item in items if item.task.status == status)

    @staticmethod
    def _task_status_label(status: TaskStatus) -> str:
        """Map one task status to a short Chinese label for boss summaries."""

        mapping = {
            TaskStatus.PENDING: "待处理",
            TaskStatus.RUNNING: "执行中",
            TaskStatus.PAUSED: "已暂停",
            TaskStatus.WAITING_HUMAN: "待人工",
            TaskStatus.COMPLETED: "已完成",
            TaskStatus.FAILED: "失败",
            TaskStatus.BLOCKED: "阻塞",
        }
        return mapping.get(status, status.value)

    @staticmethod
    def _run_status_label(status: RunStatus) -> str:
        """Map one run status to a short Chinese label for summaries."""

        mapping = {
            RunStatus.QUEUED: "排队中",
            RunStatus.RUNNING: "执行中",
            RunStatus.SUCCEEDED: "已成功",
            RunStatus.FAILED: "已失败",
            RunStatus.CANCELLED: "已取消",
        }
        return mapping.get(status, status.value)
