"""Task 领域模型定义。"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from app.domain._base import DomainModel, utc_now


class TaskStatus(StrEnum):
    """任务整体状态。

    `Task` 关注的是“这件事现在推进到哪了”，
    而不是某次执行尝试的细节。
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class TaskPriority(StrEnum):
    """任务优先级。"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Task(DomainModel):
    """V1 最小任务对象。

    当前只保留 Day 2 必要字段：

    - `id`：任务唯一标识
    - `title`：任务标题
    - `status`：任务整体推进状态
    - `priority`：任务优先级
    - `input_summary`：任务输入摘要
    - `created_at`：创建时间
    - `updated_at`：更新时间
    """

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=200)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    input_summary: str = Field(min_length=1, max_length=2_000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
