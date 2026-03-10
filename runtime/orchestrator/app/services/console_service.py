"""Console-facing aggregation helpers for the Day 10 homepage."""

from dataclasses import dataclass

from app.domain.run import Run
from app.domain.task import Task, TaskStatus
from app.repositories.task_repository import TaskRepository


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
    completed_tasks: int
    failed_tasks: int
    blocked_tasks: int
    total_estimated_cost: float
    total_prompt_tokens: int
    total_completion_tokens: int
    tasks: list[ConsoleTaskItem]


class ConsoleService:
    """Build the minimal console homepage data from persisted tasks and runs."""

    def __init__(self, task_repository: TaskRepository) -> None:
        self.task_repository = task_repository

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

        return ConsoleOverview(
            total_tasks=total_tasks,
            pending_tasks=pending_tasks,
            running_tasks=running_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            blocked_tasks=blocked_tasks,
            total_estimated_cost=total_estimated_cost,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            tasks=items,
        )

    @staticmethod
    def _count_by_status(items: list[ConsoleTaskItem], status: TaskStatus) -> int:
        """Count tasks for a single status bucket."""

        return sum(1 for item in items if item.task.status == status)
