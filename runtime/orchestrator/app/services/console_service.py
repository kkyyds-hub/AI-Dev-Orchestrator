"""Console-facing aggregation helpers for the Day 10 / Day 11 console."""

from dataclasses import dataclass
from uuid import UUID

from app.domain.run import Run
from app.domain.task import Task, TaskStatus
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardService, BudgetSnapshot
from app.services.context_builder_service import ContextBuilderService, TaskContextPackage


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


class ConsoleService:
    """Build the minimal console homepage and task detail data."""

    def __init__(
        self,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        budget_guard_service: BudgetGuardService,
        context_builder_service: ContextBuilderService,
    ) -> None:
        self.task_repository = task_repository
        self.run_repository = run_repository
        self.budget_guard_service = budget_guard_service
        self.context_builder_service = context_builder_service

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

    @staticmethod
    def _count_by_status(items: list[ConsoleTaskItem], status: TaskStatus) -> int:
        """Count tasks for a single status bucket."""

        return sum(1 for item in items if item.task.status == status)
