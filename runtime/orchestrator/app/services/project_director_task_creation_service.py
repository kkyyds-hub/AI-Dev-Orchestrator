"""AI Project Director formal project/task creation service.

Stage 4-B3-A adds an explicit user action that turns a confirmed
Project Director draft into a formal project plus a pending task queue.

Strict boundary:
- Does NOT call planning/apply.
- Does NOT dispatch workers.
- Does NOT write repositories.
- Does NOT call AI Providers.
- Does NOT auto-execute tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.domain.project import Project, ProjectStage, ProjectStatus
from app.domain.project_director_agent_team_config import (
    AgentTeamConfigStatus,
    ProjectDirectorAgentTeamConfig,
    ProjectDirectorAgentTeamMemberConfig,
)
from app.domain.project_director_repository_binding_config import (
    ProjectDirectorRepositoryBindingConfig,
    ProjectDirectorRepositoryBindingConfigItem,
    RepositoryBindingConfigStatus,
)
from app.domain.project_director_skill_binding_config import (
    ProjectDirectorSkillBindingConfig,
    ProjectDirectorSkillBindingConfigItem,
    SkillBindingConfigStatus,
)
from app.domain.project_director_verification_config import (
    ProjectDirectorVerificationConfig,
    ProjectDirectorVerificationConfigItem,
    VerificationConfigStatus,
)
from app.domain.project_director_plan_version import (
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
    ProposedTask,
)
from app.domain.project_director_task_creation import (
    ProjectDirectorTaskCreationRecord,
)
from app.domain.project_role import ProjectRoleCode
from app.domain.task import Task, TaskPriority
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_agent_team_config_repository import (
    ProjectDirectorAgentTeamConfigRepository,
)
from app.repositories.project_director_repository_binding_config_repository import (
    ProjectDirectorRepositoryBindingConfigRepository,
)
from app.repositories.project_director_skill_binding_config_repository import (
    ProjectDirectorSkillBindingConfigRepository,
)
from app.repositories.project_director_verification_config_repository import (
    ProjectDirectorVerificationConfigRepository,
)
from app.repositories.project_director_task_creation_repository import (
    ProjectDirectorTaskCreationRecordRepository,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository


_PRIORITY_MAP: dict[str, TaskPriority] = {
    "high": TaskPriority.HIGH,
    "urgent": TaskPriority.URGENT,
    "low": TaskPriority.LOW,
}

_BOUNDARY_ACTIONS = [
    "不自动调用 Worker",
    "不自动执行任务",
    "不调用 planning/apply",
    "不调用 apply-local",
    "不写入仓库文件",
    "不调用真实 AI provider",
    "不创建 Agent Session",
    "不创建真实 Skill 绑定",
    "不创建真实仓库绑定",
]

_FORMAL_PROJECT_CREATION_WARNINGS = [
    "Agent 编队建议仅作为草案快照展示，未创建 Agent Session，未自动启动 Worker。",
    "Skill 绑定建议仅作为草案快照展示，未创建真实 Skill 绑定。",
    "仓库绑定建议仅作为草案快照展示，未创建真实仓库绑定，未写入仓库。",
    "验证机制建议仅作为草案快照展示，未执行验证命令。",
]

_AGENT_TEAM_CONFIG_WARNINGS = [
    "当前仅为 Agent 编队配置，不创建真实 Agent Session。",
    "确认 Agent 编队不会自动启动 Worker。",
    "后续执行仍需要用户手动触发。",
]

_SKILL_BINDING_CONFIG_WARNINGS = [
    "当前仅为 Skill 绑定建议，不创建真实 Skill 绑定。",
    "确认 Skill 绑定建议不会启用 Skill，也不会影响 Worker 调度。",
    "后续是否真实绑定需要用户在治理配置中另行确认。",
]

_REPOSITORY_BINDING_CONFIG_WARNINGS = [
    "当前仅为仓库绑定建议，不创建真实 RepositoryWorkspace。",
    "确认仓库绑定建议不会写入仓库。",
    "不会调用 git-commit / apply-local / planning/apply。",
    "后续是否真实绑定仓库需要用户在仓库配置中另行确认。",
]

_VERIFICATION_CONFIG_WARNINGS = [
    "当前仅为验证机制建议，不会自动执行命令。",
    "确认验证机制建议不会创建 Run。",
    "高风险验证项仍需用户人工确认后另行执行。",
    "不会调用 subprocess / os.system / planning/apply / apply-local / git-commit。",
]


def _map_priority(priority_hint: str) -> TaskPriority:
    """Map plan version priority_hint to TaskPriority."""
    return _PRIORITY_MAP.get(priority_hint.lower(), TaskPriority.NORMAL)


@dataclass(slots=True)
class TaskCreationResult:
    """Immutable result of a plan-version formalization batch."""

    plan_version_id: UUID
    session_id: UUID
    project_id: UUID
    project_name: str | None
    created_task_ids: list[UUID]
    task_count: int
    status: str
    already_created: bool
    next_action: str
    warnings: list[str]
    forbidden_actions: list[str]
    gate_conclusion: str


class ProjectDirectorTaskCreationService:
    """Creates formal Projects and real tasks from confirmed draft plans."""

    def __init__(
        self,
        *,
        plan_repo: ProjectDirectorPlanVersionRepository,
        task_repo: TaskRepository,
        creation_repo: ProjectDirectorTaskCreationRecordRepository,
        project_repo: ProjectRepository,
        agent_team_config_repo: ProjectDirectorAgentTeamConfigRepository | None = None,
        skill_binding_config_repo: ProjectDirectorSkillBindingConfigRepository | None = None,
        repository_binding_config_repo: (
            ProjectDirectorRepositoryBindingConfigRepository | None
        ) = None,
        verification_config_repo: ProjectDirectorVerificationConfigRepository | None = None,
    ) -> None:
        self._plan_repo = plan_repo
        self._task_repo = task_repo
        self._creation_repo = creation_repo
        self._project_repo = project_repo
        self._agent_team_config_repo = agent_team_config_repo
        self._skill_binding_config_repo = skill_binding_config_repo
        self._repository_binding_config_repo = repository_binding_config_repo
        self._verification_config_repo = verification_config_repo

    def create_tasks_from_plan_version(
        self, plan_version_id: UUID
    ) -> TaskCreationResult:
        """Create tasks for a confirmed plan already bound to a Project.

        This preserves the existing BCG-04A API contract: duplicate calls
        still raise a conflict and unbound plan versions are rejected.
        """

        plan_version = self._require_confirmed_plan_version(
            plan_version_id,
            action_name="create tasks",
        )

        if plan_version.project_id is None:
            raise ValueError(
                "Plan version must have a project_id to create tasks. "
                "Please create the plan version from a session that is bound to a project."
            )

        existing = self._creation_repo.get_by_plan_version_id(plan_version_id)
        if existing is not None:
            raise ValueError(
                f"Tasks have already been created for plan version {plan_version_id}. "
                f"Existing creation record: {existing.id}. "
                f"Use GET /project-director/plan-versions/{plan_version_id}/created-tasks "
                f"to retrieve the previously created task IDs."
            )

        if not self._project_repo.exists(plan_version.project_id):
            raise ValueError(
                f"Project {plan_version.project_id} not found. "
                f"The project may have been deleted."
            )

        self._ensure_proposed_tasks_are_valid(plan_version)
        return self._create_task_queue_for_plan_version(plan_version)

    def create_formal_project_from_plan_version(
        self, plan_version_id: UUID
    ) -> TaskCreationResult:
        """Create/read formal project + task queue for a confirmed draft.

        This is the Stage 4-B3-A explicit user action. It is idempotent:
        repeated calls return the previous creation record and never duplicate
        the Project or Tasks.
        """

        plan_version = self._require_confirmed_plan_version(
            plan_version_id,
            action_name="create a formal project",
        )

        existing = self._creation_repo.get_by_plan_version_id(plan_version_id)
        if existing is not None:
            existing_plan_version = self._plan_repo.get_by_id(plan_version_id)
            if existing_plan_version is not None:
                self._ensure_agent_team_config_for_plan(existing_plan_version)
                self._ensure_skill_binding_config_for_plan(existing_plan_version)
                self._ensure_repository_binding_config_for_plan(existing_plan_version)
                self._ensure_verification_config_for_plan(existing_plan_version)
            return self._result_from_record(existing, already_created=True)

        self._ensure_proposed_tasks_are_valid(plan_version)

        if plan_version.project_id is None:
            project = self._project_repo.add_no_commit(
                self._build_project_from_plan_version(plan_version)
            )
            plan_version = self._plan_repo.bind_project_no_commit(
                plan_version.id,
                project.id,
            )
        elif not self._project_repo.exists(plan_version.project_id):
            raise ValueError(
                f"Project {plan_version.project_id} not found. "
                f"The project may have been deleted."
            )

        self._prepare_agent_team_config_for_plan(plan_version)
        self._prepare_skill_binding_config_for_plan(plan_version)
        self._prepare_repository_binding_config_for_plan(plan_version)
        self._prepare_verification_config_for_plan(plan_version)
        return self._create_task_queue_for_plan_version(plan_version)

    def get_created_tasks(
        self, plan_version_id: UUID
    ) -> TaskCreationResult | None:
        """Return the task/project creation result for a plan version, or None."""
        record = self._creation_repo.get_by_plan_version_id(plan_version_id)
        if record is None:
            return None
        return self._result_from_record(record, already_created=False)

    def _require_confirmed_plan_version(
        self,
        plan_version_id: UUID,
        *,
        action_name: str,
    ) -> ProjectDirectorPlanVersion:
        plan_version = self._plan_repo.get_by_id(plan_version_id)
        if plan_version is None:
            raise ValueError(f"Plan version {plan_version_id} not found")

        if plan_version.status != PlanVersionStatus.CONFIRMED:
            raise ValueError(
                f"Plan version is in '{plan_version.status}' status. "
                f"Only 'confirmed' plan versions can {action_name}."
            )
        return plan_version

    def _create_task_queue_for_plan_version(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> TaskCreationResult:
        """Create tasks + creation record for an already validated plan."""

        created_tasks = self._create_tasks_atomic(plan_version)
        record = ProjectDirectorTaskCreationRecord(
            id=uuid4(),
            plan_version_id=plan_version.id,
            session_id=plan_version.session_id,
            project_id=plan_version.project_id,
            version_no=plan_version.version_no,
            source_type="project_director_plan_version",
            task_ids=[t.id for t in created_tasks],
            task_count=len(created_tasks),
        )

        try:
            self._creation_repo.create(record)
        except Exception:
            # Roll back any uncommitted Project, plan-version binding, and Tasks.
            self._task_repo.session.rollback()
            raise ValueError(
                "Failed to persist task creation record. "
                "No project or tasks were created. Please try again."
            )

        for task in created_tasks:
            self._task_repo.publish_created(task)

        return TaskCreationResult(
            plan_version_id=plan_version.id,
            session_id=plan_version.session_id,
            project_id=plan_version.project_id,
            project_name=self._get_project_name(plan_version.project_id),
            created_task_ids=[t.id for t in created_tasks],
            task_count=len(created_tasks),
            status="created",
            already_created=False,
            next_action=(
                "正式项目与待执行任务队列已创建。"
                "后续如需执行任务，请在人工确认后单独触发 Worker 调度。"
            ),
            warnings=_FORMAL_PROJECT_CREATION_WARNINGS,
            forbidden_actions=_BOUNDARY_ACTIONS,
            gate_conclusion=(
                "部分通过（正式项目 + 任务队列创建已完成；Worker 执行未开始）"
            ),
        )

    def _prepare_agent_team_config_for_plan(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> None:
        """Add a pending project-level agent team config to the current transaction."""

        if self._agent_team_config_repo is None:
            return
        if plan_version.project_id is None:
            return
        if not plan_version.agent_team_suggestions:
            return
        if (
            self._agent_team_config_repo.get_by_plan_version_id(plan_version.id)
            is not None
        ):
            return
        if (
            self._agent_team_config_repo.get_by_project_id(plan_version.project_id)
            is not None
        ):
            return

        source_draft_id = f"pdv:{plan_version.id}:{plan_version.version_no}"
        config = ProjectDirectorAgentTeamConfig(
            project_id=plan_version.project_id,
            plan_version_id=plan_version.id,
            source_draft_id=source_draft_id,
            status=AgentTeamConfigStatus.PENDING_CONFIRMATION,
            agent_team=[
                ProjectDirectorAgentTeamMemberConfig(
                    role_code=item.role_code.value,
                    role_name=item.role_name or item.role_code.value,
                    responsibility=item.responsibility,
                    collaboration_notes=item.collaboration_notes,
                    review_status=AgentTeamConfigStatus.PENDING_CONFIRMATION.value,
                )
                for item in plan_version.agent_team_suggestions
            ],
            warnings=list(_AGENT_TEAM_CONFIG_WARNINGS),
        )
        self._agent_team_config_repo.add_no_commit(config)

    def _ensure_agent_team_config_for_plan(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> None:
        """Best-effort idempotent backfill for already-created formal projects."""

        before = (
            self._agent_team_config_repo.get_by_plan_version_id(plan_version.id)
            if self._agent_team_config_repo is not None
            else None
        )
        self._prepare_agent_team_config_for_plan(plan_version)
        after = (
            self._agent_team_config_repo.get_by_plan_version_id(plan_version.id)
            if self._agent_team_config_repo is not None
            else None
        )
        if before is None and after is not None:
            self._agent_team_config_repo.session.commit()

    def _prepare_skill_binding_config_for_plan(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> None:
        """Add a pending project-level Skill binding config to the transaction."""

        if self._skill_binding_config_repo is None:
            return
        if plan_version.project_id is None:
            return
        if not plan_version.skill_binding_suggestions:
            return
        if (
            self._skill_binding_config_repo.get_by_plan_version_id(plan_version.id)
            is not None
        ):
            return
        if (
            self._skill_binding_config_repo.get_by_project_id(plan_version.project_id)
            is not None
        ):
            return

        source_draft_id = f"pdv:{plan_version.id}:{plan_version.version_no}"
        config = ProjectDirectorSkillBindingConfig(
            project_id=plan_version.project_id,
            plan_version_id=plan_version.id,
            source_draft_id=source_draft_id,
            status=SkillBindingConfigStatus.PENDING_CONFIRMATION,
            skill_bindings=[
                ProjectDirectorSkillBindingConfigItem(
                    skill_code=item.skill_code,
                    owner_role_code=item.owner_role_code.value,
                    usage=item.usage,
                    activation_stage=item.activation_stage,
                    binding_mode=item.binding_mode,
                    reason=item.reason,
                    review_status=SkillBindingConfigStatus.PENDING_CONFIRMATION.value,
                )
                for item in plan_version.skill_binding_suggestions
            ],
            warnings=list(_SKILL_BINDING_CONFIG_WARNINGS),
        )
        self._skill_binding_config_repo.add_no_commit(config)

    def _ensure_skill_binding_config_for_plan(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> None:
        """Best-effort idempotent backfill for already-created formal projects."""

        before = (
            self._skill_binding_config_repo.get_by_plan_version_id(plan_version.id)
            if self._skill_binding_config_repo is not None
            else None
        )
        self._prepare_skill_binding_config_for_plan(plan_version)
        after = (
            self._skill_binding_config_repo.get_by_plan_version_id(plan_version.id)
            if self._skill_binding_config_repo is not None
            else None
        )
        if before is None and after is not None:
            self._skill_binding_config_repo.session.commit()

    def _prepare_repository_binding_config_for_plan(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> None:
        """Add a pending project-level repository binding config to the transaction."""

        if self._repository_binding_config_repo is None:
            return
        if plan_version.project_id is None:
            return
        if not plan_version.repository_binding_suggestions:
            return
        if (
            self._repository_binding_config_repo.get_by_plan_version_id(plan_version.id)
            is not None
        ):
            return
        if (
            self._repository_binding_config_repo.get_by_project_id(
                plan_version.project_id
            )
            is not None
        ):
            return

        source_draft_id = f"pdv:{plan_version.id}:{plan_version.version_no}"
        config = ProjectDirectorRepositoryBindingConfig(
            project_id=plan_version.project_id,
            plan_version_id=plan_version.id,
            source_draft_id=source_draft_id,
            status=RepositoryBindingConfigStatus.PENDING_CONFIRMATION,
            repository_bindings=[
                ProjectDirectorRepositoryBindingConfigItem(
                    binding_type=item.binding_type,
                    binding_mode=item.binding_mode,
                    target=item.target,
                    branch=item.branch,
                    focus_paths=item.focus_paths,
                    usage=item.usage,
                    safety_note=item.safety_note,
                    review_status=(
                        RepositoryBindingConfigStatus.PENDING_CONFIRMATION.value
                    ),
                )
                for item in plan_version.repository_binding_suggestions
            ],
            warnings=list(_REPOSITORY_BINDING_CONFIG_WARNINGS),
        )
        self._repository_binding_config_repo.add_no_commit(config)

    def _ensure_repository_binding_config_for_plan(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> None:
        """Best-effort idempotent backfill for already-created formal projects."""

        before = (
            self._repository_binding_config_repo.get_by_plan_version_id(
                plan_version.id
            )
            if self._repository_binding_config_repo is not None
            else None
        )
        self._prepare_repository_binding_config_for_plan(plan_version)
        after = (
            self._repository_binding_config_repo.get_by_plan_version_id(
                plan_version.id
            )
            if self._repository_binding_config_repo is not None
            else None
        )
        if before is None and after is not None:
            self._repository_binding_config_repo.session.commit()

    def _prepare_verification_config_for_plan(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> None:
        """Add a pending project-level verification config to the transaction."""

        if self._verification_config_repo is None:
            return
        if plan_version.project_id is None:
            return
        if not plan_version.verification_mechanisms:
            return
        if (
            self._verification_config_repo.get_by_plan_version_id(plan_version.id)
            is not None
        ):
            return
        if (
            self._verification_config_repo.get_by_project_id(plan_version.project_id)
            is not None
        ):
            return

        source_draft_id = f"pdv:{plan_version.id}:{plan_version.version_no}"
        config = ProjectDirectorVerificationConfig(
            project_id=plan_version.project_id,
            plan_version_id=plan_version.id,
            source_draft_id=source_draft_id,
            status=VerificationConfigStatus.PENDING_CONFIRMATION,
            verification_mechanisms=[
                ProjectDirectorVerificationConfigItem(
                    name=item.name,
                    command_or_method=item.command_or_method,
                    purpose=item.purpose,
                    evidence_required=item.evidence_required,
                    owner_role_code=item.owner_role_code.value,
                    risk_level=item.risk_level,
                    requires_user_confirmation=(
                        item.requires_user_confirmation
                        or item.risk_level.lower() == "high"
                    ),
                    review_status=VerificationConfigStatus.PENDING_CONFIRMATION.value,
                )
                for item in plan_version.verification_mechanisms
            ],
            warnings=list(_VERIFICATION_CONFIG_WARNINGS),
        )
        self._verification_config_repo.add_no_commit(config)

    def _ensure_verification_config_for_plan(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> None:
        """Best-effort idempotent backfill for already-created formal projects."""

        before = (
            self._verification_config_repo.get_by_plan_version_id(plan_version.id)
            if self._verification_config_repo is not None
            else None
        )
        self._prepare_verification_config_for_plan(plan_version)
        after = (
            self._verification_config_repo.get_by_plan_version_id(plan_version.id)
            if self._verification_config_repo is not None
            else None
        )
        if before is None and after is not None:
            self._verification_config_repo.session.commit()

    def _result_from_record(
        self,
        record: ProjectDirectorTaskCreationRecord,
        *,
        already_created: bool,
    ) -> TaskCreationResult:
        return TaskCreationResult(
            plan_version_id=record.plan_version_id,
            session_id=record.session_id,
            project_id=record.project_id,
            project_name=self._get_project_name(record.project_id),
            created_task_ids=record.task_ids,
            task_count=record.task_count,
            status="already_created" if already_created else "created",
            already_created=already_created,
            next_action=(
                "该已确认草案已经创建过正式项目与任务队列；"
                "本次仅返回既有记录，不会重复创建。"
                if already_created
                else "正式项目与待执行任务队列已创建。"
            ),
            warnings=_FORMAL_PROJECT_CREATION_WARNINGS,
            forbidden_actions=[*_BOUNDARY_ACTIONS, "不重复创建 Project/Tasks"],
            gate_conclusion=(
                "部分通过（正式项目 + 任务队列创建记录已存在）"
                if already_created
                else "部分通过（正式项目 + 任务队列创建已完成）"
            ),
        )

    def _build_project_from_plan_version(
        self,
        plan_version: ProjectDirectorPlanVersion,
    ) -> Project:
        summary = plan_version.plan_summary.strip()
        if not summary:
            summary = (
                f"由 AI 项目主管计划版本 {plan_version.id} 创建的正式项目。"
            )

        return Project(
            name=self._derive_project_name_from_plan_version(plan_version),
            summary=summary[:2000],
            status=ProjectStatus.ACTIVE,
            stage=ProjectStage.PLANNING,
        )

    @staticmethod
    def _derive_project_name_from_plan_version(
        plan_version: ProjectDirectorPlanVersion,
    ) -> str:
        summary = plan_version.plan_summary.strip()
        fallback_name = f"AI 项目主管计划 v{plan_version.version_no}"
        if not summary:
            return fallback_name

        for raw_line in summary.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            goal = ProjectDirectorTaskCreationService._extract_markdown_field(
                line,
                "目标",
            )
            if goal:
                return goal[:120]

        for raw_line in summary.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            candidate = ProjectDirectorTaskCreationService._clean_project_name_line(
                line
            )
            if candidate and candidate not in {"作战计划摘要", "关键决策依据", "整改说明"}:
                return candidate[:120]

        return fallback_name

    @staticmethod
    def _extract_markdown_field(line: str, field_name: str) -> str | None:
        prefixes = [
            f"**{field_name}**:",
            f"**{field_name}**：",
            f"{field_name}:",
            f"{field_name}：",
        ]
        for prefix in prefixes:
            if line.startswith(prefix):
                return ProjectDirectorTaskCreationService._clean_project_name_line(
                    line[len(prefix) :]
                )
        return None

    @staticmethod
    def _clean_project_name_line(line: str) -> str:
        cleaned = line.strip().strip("`*_ ")
        while cleaned.startswith(("-", "*", ">")):
            cleaned = cleaned[1:].strip()
        while cleaned.startswith("#"):
            cleaned = cleaned[1:].strip()
        cleaned = cleaned.replace("**", "").replace("__", "").strip()
        return cleaned or ""

    def _get_project_name(self, project_id: UUID | None) -> str | None:
        if project_id is None:
            return None
        project = self._project_repo.get_by_id(project_id)
        return project.name if project is not None else None

    @staticmethod
    def _build_input_summary(pt: ProposedTask) -> str:
        """Build input_summary from proposed_task, falling back for empty description."""
        if pt.description and pt.description.strip():
            return pt.description.strip()
        return f"由计划版本生成的任务: {pt.title}"

    @staticmethod
    def _validate_proposed_tasks(
        plan_version: ProjectDirectorPlanVersion,
    ) -> list[str]:
        """Pre-validate all proposed_tasks before any DB write."""
        errors: list[str] = []
        valid_role_codes = {r.value for r in ProjectRoleCode}

        for i, pt in enumerate(plan_version.proposed_tasks):
            if not pt.title or not pt.title.strip():
                errors.append(f"Proposed task {i} has empty title")
            if pt.suggested_role_code.value not in valid_role_codes:
                errors.append(
                    f"Proposed task {i} ('{pt.title}') has invalid "
                    f"role_code: {pt.suggested_role_code.value}"
                )
            hint = pt.priority_hint.lower()
            if hint not in _PRIORITY_MAP and hint != "normal":
                errors.append(
                    f"Proposed task {i} ('{pt.title}') has unmappable "
                    f"priority_hint: '{pt.priority_hint}'"
                )

        return errors

    @staticmethod
    def _ensure_proposed_tasks_are_valid(
        plan_version: ProjectDirectorPlanVersion,
    ) -> None:
        validation_errors = ProjectDirectorTaskCreationService._validate_proposed_tasks(
            plan_version
        )
        if validation_errors:
            raise ValueError(
                "Proposed task validation failed: "
                + "; ".join(validation_errors)
            )

    def _create_tasks_atomic(
        self, plan_version: ProjectDirectorPlanVersion
    ) -> list[Task]:
        """Convert proposed_tasks into real Tasks without committing."""
        created: list[Task] = []
        source_draft_id = f"pdv:{plan_version.id}:{plan_version.version_no}"

        try:
            for pt in plan_version.proposed_tasks:
                task = Task(
                    project_id=plan_version.project_id,
                    title=pt.title,
                    input_summary=self._build_input_summary(pt),
                    priority=_map_priority(pt.priority_hint),
                    owner_role_code=pt.suggested_role_code,
                    source_draft_id=source_draft_id,
                )
                created.append(self._task_repo.add_no_commit(task))
            return created
        except Exception:
            self._task_repo.session.rollback()
            raise
