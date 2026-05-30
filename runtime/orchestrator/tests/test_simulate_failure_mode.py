"""State-machine coverage for safe simulate blocker evidence."""

from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import Task, TaskStatus
from app.services.task_state_machine_service import TaskStateMachineService


def test_simulate_blocked_resolution_marks_task_blocked_and_run_cancelled() -> None:
    task = Task(
        title="simulate blocked evidence",
        input_summary="created through API only",
        status=TaskStatus.RUNNING,
    )
    resolution = TaskStateMachineService().build_simulate_blocked_resolution(task=task)

    assert resolution.task_transition.status == TaskStatus.BLOCKED
    assert resolution.run_status == RunStatus.CANCELLED
    assert resolution.failure_category == RunFailureCategory.RETRY_LIMIT_EXCEEDED
    assert resolution.quality_gate_passed is False
