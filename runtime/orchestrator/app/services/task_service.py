"""任务服务。

这里承接 Day 4 / Day 5 的最小业务逻辑：

- 接收任务创建输入
- 提供任务列表和详情查询
- 生成领域对象
- 调用仓储完成持久化
"""

from dataclasses import dataclass
from uuid import UUID

from app.domain.task import (
    Task,
    TaskHumanStatus,
    TaskPriority,
    TaskRiskLevel,
    TaskStatus,
)
from app.repositories.task_repository import TaskRepository
from app.services.budget_guard_service import BudgetGuardService
from app.services.event_stream_service import event_stream_service
from app.services.task_state_machine_service import (
    TaskStateMachineService,
    TaskStateTransition,
)


@dataclass(slots=True, frozen=True)
class TaskRetryResult:
    """任务重试结果。"""

    task: Task
    previous_status: TaskStatus


@dataclass(slots=True, frozen=True)
class TaskStateActionResult:
    """Result returned after one manual state-control action."""

    task: Task
    previous_status: TaskStatus
    message: str


class TaskService:
    """处理 `Task` 相关的最小业务动作。"""

    def __init__(
        self,
        task_repository: TaskRepository,
        budget_guard_service: BudgetGuardService,
        task_state_machine_service: TaskStateMachineService,
    ) -> None:
        """注入任务仓储，方便后续扩展和测试。"""

        self.task_repository = task_repository
        self.budget_guard_service = budget_guard_service
        self.task_state_machine_service = task_state_machine_service

    def create_task(
        self,
        *,
        title: str,
        input_summary: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        acceptance_criteria: list[str] | None = None,
        depends_on_task_ids: list[UUID] | None = None,
        risk_level: TaskRiskLevel = TaskRiskLevel.NORMAL,
        human_status: TaskHumanStatus = TaskHumanStatus.NONE,
        paused_reason: str | None = None,
    ) -> Task:
        """创建一条新任务。

        Day 4 的规则保持极简：

        - `status` 统一由服务端默认成 `pending`
        - `created_at / updated_at` 统一由领域模型生成
        - 客户端不允许直接传入这些服务端字段
        """

        dependency_ids = depends_on_task_ids or []
        existing_dependency_ids = self.task_repository.get_existing_ids(dependency_ids)
        missing_dependency_ids = [
            dependency_id
            for dependency_id in dependency_ids
            if dependency_id not in existing_dependency_ids
        ]
        if missing_dependency_ids:
            missing_ids_text = ", ".join(
                str(dependency_id) for dependency_id in missing_dependency_ids
            )
            raise ValueError(f"Task dependencies not found: {missing_ids_text}")

        initial_status = self.task_state_machine_service.derive_initial_status(
            human_status=human_status,
            paused_reason=paused_reason,
        )

        task = Task(
            title=title,
            status=initial_status,
            input_summary=input_summary,
            priority=priority,
            acceptance_criteria=acceptance_criteria or [],
            depends_on_task_ids=dependency_ids,
            risk_level=risk_level,
            human_status=human_status,
            paused_reason=paused_reason,
        )

        return self.task_repository.create(task)

    def list_tasks(self) -> list[Task]:
        """获取当前全部任务。"""

        return self.task_repository.list_all()

    def get_task(self, task_id: UUID) -> Task | None:
        """按任务 ID 获取单条任务。"""

        return self.task_repository.get_by_id(task_id)

    def retry_task(self, task_id: UUID) -> TaskRetryResult | None:
        """把失败或阻塞任务重新置回 `pending`。"""

        task = self.task_repository.get_by_id(task_id)
        if task is None:
            return None

        retry_status = self.budget_guard_service.build_retry_status(task_id)
        if retry_status.retry_limit_reached:
            raise ValueError(
                "Retry limit reached for this task. "
                f"Max retries: {retry_status.max_task_retries}; "
                f"recorded execution attempts: {retry_status.execution_attempts}."
            )

        transition = self.task_state_machine_service.build_retry_transition(task=task)
        updated_task = self._apply_transition(task_id=task_id, transition=transition)
        self.task_repository.session.commit()
        event_stream_service.publish_task_updated(
            task=updated_task,
            reason=transition.event_reason,
            previous_status=task.status,
        )
        return TaskRetryResult(
            task=updated_task,
            previous_status=task.status,
        )

    def pause_task(
        self,
        task_id: UUID,
        *,
        reason: str | None,
    ) -> TaskStateActionResult | None:
        """Move one task into the explicit `paused` state."""

        task = self.task_repository.get_by_id(task_id)
        if task is None:
            return None

        transition = self.task_state_machine_service.build_pause_transition(
            task=task,
            reason=reason,
        )
        updated_task = self._apply_transition(task_id=task_id, transition=transition)
        self.task_repository.session.commit()
        event_stream_service.publish_task_updated(
            task=updated_task,
            reason=transition.event_reason,
            previous_status=task.status,
        )
        return TaskStateActionResult(
            task=updated_task,
            previous_status=task.status,
            message=transition.message,
        )

    def resume_task(self, task_id: UUID) -> TaskStateActionResult | None:
        """Resume one paused task back into the pending queue."""

        task = self.task_repository.get_by_id(task_id)
        if task is None:
            return None

        transition = self.task_state_machine_service.build_resume_transition(task=task)
        updated_task = self._apply_transition(task_id=task_id, transition=transition)
        self.task_repository.session.commit()
        event_stream_service.publish_task_updated(
            task=updated_task,
            reason=transition.event_reason,
            previous_status=task.status,
        )
        return TaskStateActionResult(
            task=updated_task,
            previous_status=task.status,
            message=transition.message,
        )

    def request_human_review(self, task_id: UUID) -> TaskStateActionResult | None:
        """Move one task into the explicit `waiting_human` state."""

        task = self.task_repository.get_by_id(task_id)
        if task is None:
            return None

        transition = self.task_state_machine_service.build_request_human_review_transition(
            task=task,
        )
        updated_task = self._apply_transition(task_id=task_id, transition=transition)
        self.task_repository.session.commit()
        event_stream_service.publish_task_updated(
            task=updated_task,
            reason=transition.event_reason,
            previous_status=task.status,
        )
        return TaskStateActionResult(
            task=updated_task,
            previous_status=task.status,
            message=transition.message,
        )

    def resolve_human_review(self, task_id: UUID) -> TaskStateActionResult | None:
        """Resolve one waiting-human task and return it to routing."""

        task = self.task_repository.get_by_id(task_id)
        if task is None:
            return None

        transition = self.task_state_machine_service.build_resolve_human_review_transition(
            task=task,
        )
        updated_task = self._apply_transition(task_id=task_id, transition=transition)
        self.task_repository.session.commit()
        event_stream_service.publish_task_updated(
            task=updated_task,
            reason=transition.event_reason,
            previous_status=task.status,
        )
        return TaskStateActionResult(
            task=updated_task,
            previous_status=task.status,
            message=transition.message,
        )

    def _apply_transition(
        self,
        *,
        task_id: UUID,
        transition: TaskStateTransition,
    ) -> Task:
        """Persist one validated transition through the repository."""

        update_kwargs: dict[str, object] = {"status": transition.status}
        if transition.update_human_status:
            update_kwargs["human_status"] = transition.human_status
        if transition.update_paused_reason:
            update_kwargs["paused_reason"] = transition.paused_reason

        return self.task_repository.update_control_state(task_id, **update_kwargs)
