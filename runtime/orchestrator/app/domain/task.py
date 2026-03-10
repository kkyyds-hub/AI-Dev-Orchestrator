"""Task 领域模型定义。"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from app.domain._base import DomainModel, utc_now


class TaskStatus(StrEnum):
    """任务整体状态。

    `Task` 关注的是“这件事现在推进到哪了”，
    而不是某次执行尝试的细节。
    """

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class TaskPriority(StrEnum):
    """任务优先级。"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskRiskLevel(StrEnum):
    """任务风险等级。"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class TaskHumanStatus(StrEnum):
    """任务当前的人工作业状态。"""

    NONE = "none"
    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class TaskEventReason(StrEnum):
    """Stable task event reasons published to the console stream."""

    CREATED = "created"
    CLAIMED = "claimed"
    RETRIED = "retried"
    PAUSED = "paused"
    RESUMED = "resumed"
    WAITING_HUMAN = "waiting_human"
    HUMAN_RESOLVED = "human_resolved"
    GUARD_BLOCKED = "guard_blocked"
    FINALIZED = "finalized"


class TaskBlockingReasonCategory(StrEnum):
    """High-level buckets for one task blocking signal."""

    DEPENDENCY = "dependency"
    STATUS = "status"
    HUMAN = "human"
    PAUSE = "pause"
    BUDGET = "budget"


class TaskBlockingReasonCode(StrEnum):
    """Stable blocking reason codes used by readiness and UI layers."""

    BUDGET_GUARD_BLOCKED = "budget_guard_blocked"
    DEPENDENCY_MISSING = "dependency_missing"
    DEPENDENCY_INCOMPLETE = "dependency_incomplete"
    TASK_NOT_PENDING = "task_not_pending"
    TASK_PAUSED = "task_paused"
    TASK_WAITING_HUMAN = "task_waiting_human"
    HUMAN_REVIEW_REQUESTED = "human_review_requested"
    HUMAN_REVIEW_IN_PROGRESS = "human_review_in_progress"
    PAUSE_NOTE_PRESENT = "pause_note_present"


class Task(DomainModel):
    """V1 最小任务对象。

    在 Day 16 起，任务对象开始补充最小调度元数据：

    - `id`：任务唯一标识
    - `title`：任务标题
    - `status`：任务整体推进状态
    - `priority`：任务优先级
    - `input_summary`：任务输入摘要
    - `acceptance_criteria`：最小验收标准列表
    - `depends_on_task_ids`：前置依赖任务
    - `risk_level`：保守的风险标记
    - `human_status`：是否需要人工接管
    - `paused_reason`：后续暂停 / 恢复能力预留说明
    - `created_at`：创建时间
    - `updated_at`：更新时间
    """

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=200)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    input_summary: str = Field(min_length=1, max_length=2_000)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=10)
    depends_on_task_ids: list[UUID] = Field(default_factory=list, max_length=20)
    risk_level: TaskRiskLevel = Field(default=TaskRiskLevel.NORMAL)
    human_status: TaskHumanStatus = Field(default=TaskHumanStatus.NONE)
    paused_reason: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def default_acceptance_criteria(
        cls,
        value: list[str] | None,
    ) -> list[str]:
        """Normalize missing acceptance criteria to an empty list."""

        return value or []

    @field_validator("acceptance_criteria")
    @classmethod
    def normalize_acceptance_criteria(cls, value: list[str]) -> list[str]:
        """Trim, validate and deduplicate acceptance criteria."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for item in value:
            normalized_item = item.strip()
            if not normalized_item:
                raise ValueError("acceptance_criteria items cannot be empty.")

            if normalized_item in seen_items:
                continue

            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)

        return normalized_items

    @field_validator("depends_on_task_ids", mode="before")
    @classmethod
    def default_dependency_ids(
        cls,
        value: list[UUID] | None,
    ) -> list[UUID]:
        """Normalize missing dependency IDs to an empty list."""

        return value or []

    @field_validator("depends_on_task_ids")
    @classmethod
    def normalize_dependency_ids(cls, value: list[UUID]) -> list[UUID]:
        """Deduplicate dependency IDs while preserving order."""

        normalized_ids: list[UUID] = []
        seen_ids: set[UUID] = set()

        for dependency_id in value:
            if dependency_id in seen_ids:
                continue

            normalized_ids.append(dependency_id)
            seen_ids.add(dependency_id)

        return normalized_ids

    @field_validator("paused_reason")
    @classmethod
    def normalize_paused_reason(cls, value: str | None) -> str | None:
        """Collapse blank pause reasons into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None
