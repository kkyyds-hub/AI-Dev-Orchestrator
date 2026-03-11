"""SQLite table definitions used by the orchestrator."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid as SqlUuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain._base import utc_now
from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import (
    TaskHumanStatus,
    TaskPriority,
    TaskRiskLevel,
    TaskStatus,
)


def _enum_values(enum_type: type) -> list[str]:
    """Return enum values for SQLAlchemy's non-native enum storage."""

    return [member.value for member in enum_type]


class ORMBase(DeclarativeBase):
    """Base class for ORM tables."""


class TaskTable(ORMBase):
    """Task rows."""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=TaskStatus.PENDING,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(
            TaskPriority,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=TaskPriority.NORMAL,
    )
    input_summary: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_criteria: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    depends_on_task_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    risk_level: Mapped[TaskRiskLevel] = mapped_column(
        Enum(
            TaskRiskLevel,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=TaskRiskLevel.NORMAL,
    )
    human_status: Mapped[TaskHumanStatus] = mapped_column(
        Enum(
            TaskHumanStatus,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=TaskHumanStatus.NONE,
    )
    paused_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    runs: Mapped[list["RunTable"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )


class RunTable(ORMBase):
    """Execution attempt rows."""

    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(
            RunStatus,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=RunStatus.QUEUED,
    )
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    route_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    routing_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    routing_score_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    log_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_mode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verification_template: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verification_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_category: Mapped[RunFailureCategory | None] = mapped_column(
        Enum(
            RunFailureCategory,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=True,
    )
    quality_gate_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    task: Mapped[TaskTable] = relationship(back_populates="runs")
