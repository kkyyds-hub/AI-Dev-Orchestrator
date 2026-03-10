"""领域对象层。

当前先冻结 Day 2 需要的最小核心对象：

- `Task`：表示“要做什么”以及任务整体推进状态
- `Run`：表示“某次执行尝试”以及执行结果摘要
"""

from app.domain.run import Run, RunStatus
from app.domain.task import Task, TaskPriority, TaskStatus

__all__ = [
    "Run",
    "RunStatus",
    "Task",
    "TaskPriority",
    "TaskStatus",
]
