"""任务服务。

这里承接 Day 4 / Day 5 的最小业务逻辑：

- 接收任务创建输入
- 提供任务列表和详情查询
- 生成领域对象
- 调用仓储完成持久化
"""

from uuid import UUID

from app.domain.task import Task, TaskPriority
from app.repositories.task_repository import TaskRepository


class TaskService:
    """处理 `Task` 相关的最小业务动作。"""

    def __init__(self, task_repository: TaskRepository) -> None:
        """注入任务仓储，方便后续扩展和测试。"""

        self.task_repository = task_repository

    def create_task(
        self,
        *,
        title: str,
        input_summary: str,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> Task:
        """创建一条新任务。

        Day 4 的规则保持极简：

        - `status` 统一由服务端默认成 `pending`
        - `created_at / updated_at` 统一由领域模型生成
        - 客户端不允许直接传入这些服务端字段
        """

        task = Task(
            title=title,
            input_summary=input_summary,
            priority=priority,
        )

        return self.task_repository.create(task)

    def list_tasks(self) -> list[Task]:
        """获取当前全部任务。"""

        return self.task_repository.list_all()

    def get_task(self, task_id: UUID) -> Task | None:
        """按任务 ID 获取单条任务。"""

        return self.task_repository.get_by_id(task_id)
