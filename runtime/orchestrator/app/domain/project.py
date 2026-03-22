"""Project 领域模型定义。"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now
from app.domain.repository_snapshot import RepositorySnapshot
from app.domain.repository_workspace import RepositoryWorkspace
from app.domain.task import TaskStatus


class ProjectStatus(StrEnum):
    """项目整体状态。"""

    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectStage(StrEnum):
    """项目当前生命周期阶段。"""

    INTAKE = "intake"
    PLANNING = "planning"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    DELIVERY = "delivery"


class ProjectStageHistoryOutcome(StrEnum):
    """阶段推进动作的审计结果。"""

    APPLIED = "applied"
    BLOCKED = "blocked"


class ProjectMilestoneCode(StrEnum):
    """稳定的项目里程碑代码。"""

    PROJECT_ACTIVE = "project_active"
    PROJECT_BRIEF_READY = "project_brief_ready"
    TASKS_MAPPED = "tasks_mapped"
    READY_PATH_AVAILABLE = "ready_path_available"
    PLANNING_GUARDS_CLEARED = "planning_guards_cleared"
    ALL_TASKS_COMPLETED = "all_tasks_completed"
    SOP_TEMPLATE_SELECTED = "sop_template_selected"
    SOP_REQUIRED_ROLES_ENABLED = "sop_required_roles_enabled"
    SOP_STAGE_TASKS_COMPLETED = "sop_stage_tasks_completed"


class ProjectTaskStats(DomainModel):
    """项目下任务的最小聚合统计。"""

    total_tasks: int = Field(default=0, ge=0)
    pending_tasks: int = Field(default=0, ge=0)
    running_tasks: int = Field(default=0, ge=0)
    paused_tasks: int = Field(default=0, ge=0)
    waiting_human_tasks: int = Field(default=0, ge=0)
    completed_tasks: int = Field(default=0, ge=0)
    failed_tasks: int = Field(default=0, ge=0)
    blocked_tasks: int = Field(default=0, ge=0)
    last_task_updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_consistency(self) -> "ProjectTaskStats":
        """Ensure the aggregate totals stay self-consistent."""

        object.__setattr__(
            self,
            "last_task_updated_at",
            ensure_utc_datetime(self.last_task_updated_at),
        )

        status_total = (
            self.pending_tasks
            + self.running_tasks
            + self.paused_tasks
            + self.waiting_human_tasks
            + self.completed_tasks
            + self.failed_tasks
            + self.blocked_tasks
        )
        if self.total_tasks != status_total:
            raise ValueError(
                "Project task stats total does not match the status breakdown."
            )

        return self


class ProjectStageHistoryEntry(DomainModel):
    """一条项目阶段推进审计记录。"""

    id: UUID = Field(default_factory=uuid4)
    from_stage: ProjectStage | None = None
    to_stage: ProjectStage
    outcome: ProjectStageHistoryOutcome = Field(
        default=ProjectStageHistoryOutcome.APPLIED
    )
    note: str | None = Field(default=None, max_length=500)
    reasons: list[str] = Field(default_factory=list, max_length=10)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        """Trim optional note fields."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("reasons")
    @classmethod
    def normalize_reasons(cls, value: list[str]) -> list[str]:
        """Trim, drop blanks and deduplicate reasons while preserving order."""

        normalized_reasons: list[str] = []
        seen_reasons: set[str] = set()

        for item in value:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_reasons:
                continue

            normalized_reasons.append(normalized_item)
            seen_reasons.add(normalized_item)

        return normalized_reasons

    @model_validator(mode="after")
    def validate_created_at(self) -> "ProjectStageHistoryEntry":
        """Normalize transition timestamps."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        return self


class ProjectStageBlockingTask(DomainModel):
    """一个阻塞当前阶段推进的任务摘要。"""

    task_id: UUID
    title: str
    status: TaskStatus
    blocking_reasons: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """Trim blocking-task titles."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Project stage blocking task title cannot be blank.")

        return normalized_value

    @field_validator("blocking_reasons")
    @classmethod
    def normalize_blocking_reasons(cls, value: list[str]) -> list[str]:
        """Trim and deduplicate blocking-reason text."""

        normalized_reasons: list[str] = []
        seen_reasons: set[str] = set()

        for item in value:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_reasons:
                continue

            normalized_reasons.append(normalized_item)
            seen_reasons.add(normalized_item)

        return normalized_reasons


class ProjectMilestone(DomainModel):
    """一个阶段推进里程碑检查项。"""

    code: ProjectMilestoneCode
    title: str = Field(min_length=1, max_length=120)
    satisfied: bool
    summary: str = Field(min_length=1, max_length=500)
    blocking_reasons: list[str] = Field(default_factory=list, max_length=10)
    related_task_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @field_validator("title", "summary")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        """Trim milestone text fields."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Project milestone text fields cannot be blank.")

        return normalized_value

    @field_validator("blocking_reasons")
    @classmethod
    def normalize_milestone_reasons(cls, value: list[str]) -> list[str]:
        """Trim and deduplicate milestone blocking reasons."""

        normalized_reasons: list[str] = []
        seen_reasons: set[str] = set()

        for item in value:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_reasons:
                continue

            normalized_reasons.append(normalized_item)
            seen_reasons.add(normalized_item)

        return normalized_reasons

    @field_validator("related_task_ids")
    @classmethod
    def normalize_related_task_ids(cls, value: list[UUID]) -> list[UUID]:
        """Deduplicate related task IDs while preserving order."""

        normalized_ids: list[UUID] = []
        seen_ids: set[UUID] = set()

        for task_id in value:
            if task_id in seen_ids:
                continue

            normalized_ids.append(task_id)
            seen_ids.add(task_id)

        return normalized_ids


class ProjectStageGuard(DomainModel):
    """下一阶段推进前的守卫评估结果。"""

    current_stage: ProjectStage
    target_stage: ProjectStage | None = None
    can_advance: bool
    milestones: list[ProjectMilestone] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list, max_length=20)
    blocking_tasks: list[ProjectStageBlockingTask] = Field(default_factory=list)
    total_tasks: int = Field(default=0, ge=0)
    ready_task_count: int = Field(default=0, ge=0)
    completed_task_count: int = Field(default=0, ge=0)
    current_stage_task_count: int = Field(default=0, ge=0)
    current_stage_completed_task_count: int = Field(default=0, ge=0)

    @field_validator("blocking_reasons")
    @classmethod
    def normalize_guard_reasons(cls, value: list[str]) -> list[str]:
        """Trim and deduplicate project-stage blocking reasons."""

        normalized_reasons: list[str] = []
        seen_reasons: set[str] = set()

        for item in value:
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_reasons:
                continue

            normalized_reasons.append(normalized_item)
            seen_reasons.add(normalized_item)

        return normalized_reasons

    @model_validator(mode="after")
    def validate_guard(self) -> "ProjectStageGuard":
        """Keep milestone and aggregate counts aligned."""

        if self.can_advance and self.blocking_reasons:
            raise ValueError(
                "Project stage guard cannot be advanceable while still carrying blockers."
            )

        return self


class Project(DomainModel):
    """V3 Day01/Day04 的项目对象。"""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2_000)
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE)
    stage: ProjectStage = Field(default=ProjectStage.INTAKE)
    sop_template_code: str | None = Field(default=None, max_length=100)
    task_stats: ProjectTaskStats = Field(default_factory=ProjectTaskStats)
    repository_workspace: RepositoryWorkspace | None = None
    latest_repository_snapshot: RepositorySnapshot | None = None
    stage_history: list[ProjectStageHistoryEntry] = Field(default_factory=list, max_length=100)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("name", "summary")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        """Trim text fields and reject blank values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Project text fields cannot be blank.")

        return normalized_value

    @field_validator("sop_template_code")
    @classmethod
    def normalize_sop_template_code(cls, value: str | None) -> str | None:
        """Collapse blank template codes into `None`."""

        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None

    @model_validator(mode="after")
    def validate_time_range(self) -> "Project":
        """Ensure timestamps are UTC-aware, ordered and stage history is usable."""

        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", ensure_utc_datetime(self.updated_at))

        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")

        normalized_history = list(self.stage_history)
        if not normalized_history:
            normalized_history = [
                ProjectStageHistoryEntry(
                    from_stage=None,
                    to_stage=self.stage,
                    outcome=ProjectStageHistoryOutcome.APPLIED,
                    note="Project was created with its initial stage.",
                    created_at=self.created_at,
                )
            ]

        latest_applied_entry = next(
            (
                entry
                for entry in reversed(normalized_history)
                if entry.outcome == ProjectStageHistoryOutcome.APPLIED
            ),
            None,
        )
        if latest_applied_entry is None:
            normalized_history.insert(
                0,
                ProjectStageHistoryEntry(
                    from_stage=None,
                    to_stage=self.stage,
                    outcome=ProjectStageHistoryOutcome.APPLIED,
                    note="Project stage history was backfilled from persisted data.",
                    created_at=self.created_at,
                ),
            )
            latest_applied_entry = normalized_history[0]

        if latest_applied_entry.to_stage != self.stage:
            raise ValueError(
                "Project stage history is inconsistent with the persisted project stage."
            )

        object.__setattr__(self, "stage_history", normalized_history)
        return self
