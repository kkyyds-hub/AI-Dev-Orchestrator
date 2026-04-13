"""SQLite table definitions used by the orchestrator."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Uuid as SqlUuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain._base import utc_now
from app.domain.approval import ApprovalDecisionAction, ApprovalStatus
from app.domain.change_batch import ChangeBatchStatus
from app.domain.commit_candidate import CommitCandidateStatus
from app.domain.change_session import (
    ChangeSessionGuardStatus,
    ChangeSessionWorkspaceStatus,
)
from app.domain.change_plan import ChangePlanStatus
from app.domain.deliverable import DeliverableContentFormat, DeliverableType
from app.domain.project import ProjectStage, ProjectStatus
from app.domain.project_role import ProjectRoleCode
from app.domain.repository_snapshot import RepositorySnapshotStatus
from app.domain.repository_verification import RepositoryVerificationCategory
from app.domain.repository_workspace import RepositoryAccessMode
from app.domain.run import RunFailureCategory, RunStatus
from app.domain.skill import SkillBindingSource
from app.domain.task import (
    TaskHumanStatus,
    TaskPriority,
    TaskRiskLevel,
    TaskStatus,
)
from app.domain.verification_run import (
    VerificationRunCommandSource,
    VerificationRunFailureCategory,
    VerificationRunStatus,
)


def _enum_values(enum_type: type) -> list[str]:
    """Return enum values for SQLAlchemy's non-native enum storage."""

    return [member.value for member in enum_type]


class ORMBase(DeclarativeBase):
    """Base class for ORM tables."""


class ProjectTable(ORMBase):
    """Project rows."""

    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(
            ProjectStatus,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ProjectStatus.ACTIVE,
    )
    stage: Mapped[ProjectStage] = mapped_column(
        Enum(
            ProjectStage,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ProjectStage.INTAKE,
    )
    sop_template_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stage_history_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
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

    tasks: Mapped[list["TaskTable"]] = relationship(back_populates="project")
    project_roles: Mapped[list["ProjectRoleTable"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    deliverables: Mapped[list["DeliverableTable"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    repository_workspace: Mapped["RepositoryWorkspaceTable | None"] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,
    )
    repository_snapshot: Mapped["RepositorySnapshotTable | None"] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,
    )


class RepositoryWorkspaceTable(ORMBase):
    """Project-bound local repository workspace rows."""

    __tablename__ = "repository_workspaces"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            name="uq_repository_workspaces_project",
        ),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    access_mode: Mapped[RepositoryAccessMode] = mapped_column(
        Enum(
            RepositoryAccessMode,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=RepositoryAccessMode.READ_ONLY,
    )
    default_base_branch: Mapped[str] = mapped_column(String(200), nullable=False)
    ignore_rule_summary_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    allowed_workspace_root: Mapped[str] = mapped_column(Text, nullable=False)
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

    project: Mapped[ProjectTable] = relationship(back_populates="repository_workspace")
    repository_snapshot: Mapped["RepositorySnapshotTable | None"] = relationship(
        back_populates="repository_workspace",
        uselist=False,
    )


class RepositorySnapshotTable(ORMBase):
    """Latest structured workspace scan rows attached to repository bindings."""

    __tablename__ = "repository_snapshots"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_repository_snapshots_project"),
        UniqueConstraint(
            "repository_workspace_id",
            name="uq_repository_snapshots_workspace",
        ),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_workspace_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("repository_workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_root_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RepositorySnapshotStatus] = mapped_column(
        Enum(
            RepositorySnapshotStatus,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=RepositorySnapshotStatus.SUCCESS,
    )
    directory_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ignored_directory_names_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    language_breakdown_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    tree_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    scan_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
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

    project: Mapped[ProjectTable] = relationship(back_populates="repository_snapshot")
    repository_workspace: Mapped[RepositoryWorkspaceTable] = relationship(
        back_populates="repository_snapshot"
    )


class ChangeSessionTable(ORMBase):
    """Latest Day03 branch/workspace status rows attached to repository bindings."""

    __tablename__ = "change_sessions"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_change_sessions_project"),
        UniqueConstraint(
            "repository_workspace_id",
            name="uq_change_sessions_workspace",
        ),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_workspace_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("repository_workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_root_path: Mapped[str] = mapped_column(Text, nullable=False)
    current_branch: Mapped[str] = mapped_column(String(200), nullable=False)
    head_ref: Mapped[str] = mapped_column(Text, nullable=False)
    head_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    baseline_branch: Mapped[str] = mapped_column(String(200), nullable=False)
    baseline_ref: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workspace_status: Mapped[ChangeSessionWorkspaceStatus] = mapped_column(
        Enum(
            ChangeSessionWorkspaceStatus,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ChangeSessionWorkspaceStatus.CLEAN,
    )
    guard_status: Mapped[ChangeSessionGuardStatus] = mapped_column(
        Enum(
            ChangeSessionGuardStatus,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ChangeSessionGuardStatus.READY,
    )
    guard_summary: Mapped[str] = mapped_column(Text, nullable=False)
    blocking_reasons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    dirty_file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dirty_files_truncated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    dirty_files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
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

    project: Mapped[ProjectTable] = relationship()
    repository_workspace: Mapped[RepositoryWorkspaceTable] = relationship()


class ProjectRoleTable(ORMBase):
    """Project-owned role configuration rows."""

    __tablename__ = "project_roles"
    __table_args__ = (
        UniqueConstraint("project_id", "role_code", name="uq_project_roles_project_role"),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_code: Mapped[ProjectRoleCode] = mapped_column(
        Enum(
            ProjectRoleCode,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    responsibilities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    input_boundary_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    output_boundary_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    default_skill_slots_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    custom_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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

    project: Mapped[ProjectTable] = relationship(back_populates="project_roles")


class SkillTable(ORMBase):
    """Registered Skill rows owned by the Day13 registry."""

    __tablename__ = "skills"

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    applicable_role_codes_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    current_version: Mapped[str] = mapped_column(String(40), nullable=False)
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

    versions: Mapped[list["SkillVersionTable"]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
    )
    role_bindings: Mapped[list["ProjectRoleSkillBindingTable"]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
    )


class SkillVersionTable(ORMBase):
    """Version snapshot rows stored for each Skill."""

    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_id", "version", name="uq_skill_versions_skill_version"),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    skill_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    applicable_role_codes_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    skill: Mapped[SkillTable] = relationship(back_populates="versions")


class ProjectRoleSkillBindingTable(ORMBase):
    """Project-role to Skill binding rows."""

    __tablename__ = "project_role_skill_bindings"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "role_code",
            "skill_id",
            name="uq_project_role_skill_bindings_role_skill",
        ),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_code: Mapped[ProjectRoleCode] = mapped_column(
        Enum(
            ProjectRoleCode,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    skill_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
    )
    skill_code: Mapped[str] = mapped_column(String(80), nullable=False)
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bound_version: Mapped[str] = mapped_column(String(40), nullable=False)
    binding_source: Mapped[SkillBindingSource] = mapped_column(
        Enum(
            SkillBindingSource,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=SkillBindingSource.MANUAL,
    )
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

    skill: Mapped[SkillTable] = relationship(back_populates="role_bindings")


class TaskTable(ORMBase):
    """Task rows."""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID | None] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
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
    owner_role_code: Mapped[ProjectRoleCode | None] = mapped_column(
        Enum(
            ProjectRoleCode,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=True,
    )
    upstream_role_code: Mapped[ProjectRoleCode | None] = mapped_column(
        Enum(
            ProjectRoleCode,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=True,
    )
    downstream_role_code: Mapped[ProjectRoleCode | None] = mapped_column(
        Enum(
            ProjectRoleCode,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=True,
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
    source_draft_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
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
    project: Mapped[ProjectTable | None] = relationship(back_populates="tasks")
    deliverable_versions: Mapped[list["DeliverableVersionTable"]] = relationship(
        back_populates="source_task",
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
    strategy_decision_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_role_code: Mapped[ProjectRoleCode | None] = mapped_column(
        Enum(
            ProjectRoleCode,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=True,
    )
    upstream_role_code: Mapped[ProjectRoleCode | None] = mapped_column(
        Enum(
            ProjectRoleCode,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=True,
    )
    downstream_role_code: Mapped[ProjectRoleCode | None] = mapped_column(
        Enum(
            ProjectRoleCode,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=True,
    )
    handoff_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatch_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_template_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_template_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    prompt_char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_accounting_mode: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_receipt_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_pricing_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
    deliverable_versions: Mapped[list["DeliverableVersionTable"]] = relationship(
        back_populates="source_run",
    )


class DeliverableTable(ORMBase):
    """Project artifact rows."""

    __tablename__ = "deliverables"

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[DeliverableType] = mapped_column(
        Enum(
            DeliverableType,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    stage: Mapped[ProjectStage] = mapped_column(
        Enum(
            ProjectStage,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    created_by_role_code: Mapped[ProjectRoleCode] = mapped_column(
        Enum(
            ProjectRoleCode,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    current_version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
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

    project: Mapped[ProjectTable] = relationship(back_populates="deliverables")
    versions: Mapped[list["DeliverableVersionTable"]] = relationship(
        back_populates="deliverable",
        cascade="all, delete-orphan",
    )
    approval_requests: Mapped[list["ApprovalRequestTable"]] = relationship(
        back_populates="deliverable",
        cascade="all, delete-orphan",
    )


class DeliverableVersionTable(ORMBase):
    """Immutable deliverable snapshot rows."""

    __tablename__ = "deliverable_versions"
    __table_args__ = (
        UniqueConstraint(
            "deliverable_id",
            "version_number",
            name="uq_deliverable_versions_deliverable_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    deliverable_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("deliverables.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    author_role_code: Mapped[ProjectRoleCode] = mapped_column(
        Enum(
            ProjectRoleCode,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_format: Mapped[DeliverableContentFormat] = mapped_column(
        Enum(
            DeliverableContentFormat,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=DeliverableContentFormat.MARKDOWN,
    )
    source_task_id: Mapped[UUID | None] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_run_id: Mapped[UUID | None] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    deliverable: Mapped[DeliverableTable] = relationship(back_populates="versions")
    source_task: Mapped[TaskTable | None] = relationship(
        back_populates="deliverable_versions"
    )
    source_run: Mapped[RunTable | None] = relationship(
        back_populates="deliverable_versions"
    )
    approval_requests: Mapped[list["ApprovalRequestTable"]] = relationship(
        back_populates="deliverable_version",
    )


class ChangePlanTable(ORMBase):
    """Day06 change-plan head rows."""

    __tablename__ = "change_plans"

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    primary_deliverable_id: Mapped[UUID | None] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("deliverables.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[ChangePlanStatus] = mapped_column(
        Enum(
            ChangePlanStatus,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ChangePlanStatus.DRAFT,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    current_version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
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

    versions: Mapped[list["ChangePlanVersionTable"]] = relationship(
        back_populates="change_plan",
        cascade="all, delete-orphan",
    )


class ChangePlanVersionTable(ORMBase):
    """Immutable Day06 change-plan draft version rows."""

    __tablename__ = "change_plan_versions"
    __table_args__ = (
        UniqueConstraint(
            "change_plan_id",
            "version_number",
            name="uq_change_plan_versions_plan_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    change_plan_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("change_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    intent_summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_summary: Mapped[str] = mapped_column(Text, nullable=False)
    focus_terms_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    target_files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    expected_actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    risk_notes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    verification_commands_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    verification_templates_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    related_deliverable_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    context_pack_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    change_plan: Mapped[ChangePlanTable] = relationship(back_populates="versions")


class RepositoryVerificationTemplateTable(ORMBase):
    """Day09 repository verification-template rows."""

    __tablename__ = "repository_verification_templates"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "category",
            name="uq_repository_verification_templates_project_category",
        ),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[RepositoryVerificationCategory] = mapped_column(
        Enum(
            RepositoryVerificationCategory,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    working_directory: Mapped[str] = mapped_column(String(500), nullable=False, default=".")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    enabled_by_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class ChangeBatchTable(ORMBase):
    """Day07 execution-preparation batch rows."""

    __tablename__ = "change_batches"

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_workspace_id: Mapped[UUID | None] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("repository_workspaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[ChangeBatchStatus] = mapped_column(
        Enum(
            ChangeBatchStatus,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ChangeBatchStatus.PREPARING,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    plan_snapshots_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    preflight_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
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


class CommitCandidateTable(ORMBase):
    """Day13 commit-candidate draft rows."""

    __tablename__ = "commit_candidates"
    __table_args__ = (
        UniqueConstraint(
            "change_batch_id",
            name="uq_commit_candidates_change_batch",
        ),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    change_batch_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("change_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    change_batch_title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[CommitCandidateStatus] = mapped_column(
        Enum(
            CommitCandidateStatus,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=CommitCandidateStatus.DRAFT,
    )
    current_version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    versions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
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


class VerificationRunTable(ORMBase):
    """Day10 repository verification-run rows."""

    __tablename__ = "verification_runs"

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_workspace_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("repository_workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    change_plan_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("change_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    change_batch_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("change_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    verification_template_id: Mapped[UUID | None] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("repository_verification_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    verification_template_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verification_template_category: Mapped[RepositoryVerificationCategory | None] = (
        mapped_column(
            Enum(
                RepositoryVerificationCategory,
                native_enum=False,
                values_callable=_enum_values,
                validate_strings=True,
            ),
            nullable=True,
        )
    )
    command_source: Mapped[VerificationRunCommandSource] = mapped_column(
        Enum(
            VerificationRunCommandSource,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    command: Mapped[str] = mapped_column(Text, nullable=False)
    working_directory: Mapped[str] = mapped_column(String(500), nullable=False, default=".")
    status: Mapped[VerificationRunStatus] = mapped_column(
        Enum(
            VerificationRunStatus,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    failure_category: Mapped[VerificationRunFailureCategory | None] = mapped_column(
        Enum(
            VerificationRunFailureCategory,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=True,
    )
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_summary: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class ApprovalRequestTable(ORMBase):
    """Boss-approval request rows bound to deliverable versions."""

    __tablename__ = "approval_requests"

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    deliverable_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("deliverables.id", ondelete="CASCADE"),
        nullable=False,
    )
    deliverable_version_id: Mapped[UUID | None] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("deliverable_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    deliverable_title: Mapped[str] = mapped_column(String(200), nullable=False)
    deliverable_type: Mapped[DeliverableType] = mapped_column(
        Enum(
            DeliverableType,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    deliverable_stage: Mapped[ProjectStage] = mapped_column(
        Enum(
            ProjectStage,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    deliverable_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    requester_role_code: Mapped[ProjectRoleCode] = mapped_column(
        Enum(
            ProjectRoleCode,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    request_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(
            ApprovalStatus,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=ApprovalStatus.PENDING_APPROVAL,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    latest_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    deliverable: Mapped[DeliverableTable] = relationship(
        back_populates="approval_requests"
    )
    deliverable_version: Mapped[DeliverableVersionTable | None] = relationship(
        back_populates="approval_requests"
    )
    decisions: Mapped[list["ApprovalDecisionTable"]] = relationship(
        back_populates="approval",
        cascade="all, delete-orphan",
    )


class ApprovalDecisionTable(ORMBase):
    """Structured boss-decision rows stored under one approval request."""

    __tablename__ = "approval_decisions"

    id: Mapped[UUID] = mapped_column(SqlUuid(as_uuid=True), primary_key=True, default=uuid4)
    approval_id: Mapped[UUID] = mapped_column(
        SqlUuid(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[ApprovalDecisionAction] = mapped_column(
        Enum(
            ApprovalDecisionAction,
            native_enum=False,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
    )
    actor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    highlighted_risks_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    requested_changes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    approval: Mapped[ApprovalRequestTable] = relationship(back_populates="decisions")
