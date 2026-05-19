"""AI Project Director Plan Version service.

BCG-02 Phase1: deterministic plan generation from confirmed sessions.
No AI, no Provider, no task creation, no worker dispatch.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.project_director_plan_version import (
    PlanPhase,
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
    ProposedTask,
)
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)


# ── Deterministic plan generation ────────────────────────────────────

_DEFAULT_FORBIDDEN_ACTIONS = [
    "不自动创建任务",
    "不自动调用 Worker",
    "不写仓库",
    "不把计划确认等同于执行完成",
    "不调用 planning/apply",
]


def _generate_plan_from_session(
    session: "ProjectDirectorSession",  # noqa: F821
) -> tuple[str, list[PlanPhase], list[ProposedTask], list[str], list[str]]:
    """Generate a deterministic plan from a confirmed session.

    Returns: (plan_summary, phases, proposed_tasks, acceptance_criteria, risks)
    """

    from app.domain.project_director_session import ProjectDirectorSession

    goal = session.goal_text
    constraints = session.constraints
    answers = {a.question_id: a.answer for a in session.clarifying_answers}

    # Build plan summary from goal + constraints + answers
    summary_lines = [
        "## 作战计划摘要\n",
        f"**目标**: {goal}",
    ]
    if constraints:
        summary_lines.append(f"\n**约束**: {constraints}")

    # Extract key answers for the plan
    answer_lines = ["\n## 关键决策依据\n"]
    for q in session.clarifying_questions:
        answer = answers.get(q.id, "（未回答）")
        answer_lines.append(f"- **{q.question}** → {answer}")

    plan_summary = "\n".join(summary_lines + answer_lines)

    # ── Generate phases deterministically ──
    # Phase count driven by goal complexity (character length proxy)
    char_count = len(goal)
    phase_count = 2 if char_count < 60 else 3 if char_count < 200 else 4

    phases: list[PlanPhase] = []
    phase_templates = [
        ("分析与设计", "理清需求、技术选型、架构设计，产出设计文档"),
        ("核心实现", "实现核心功能逻辑，编写主要代码"),
        ("验证与测试", "测试、验证、修复问题，确保质量"),
        ("交付与收尾", "文档、部署、审批、交付物整理"),
    ]

    for i in range(phase_count):
        template = phase_templates[i] if i < len(phase_templates) else (
            f"阶段 {i + 1}",
            f"扩展性工作与优化",
        )
        phases.append(
            PlanPhase(
                sequence=i + 1,
                name=template[0],
                goal=template[1],
                task_count_hint=max(1, 4 - i),
            )
        )

    # ── Generate proposed tasks ──
    has_tech = any(
        kw in goal.lower()
        for kw in ["代码", "code", "开发", "build", "api", "实现", "implement"]
    )
    has_frontend = any(
        kw in goal.lower() for kw in ["前端", "frontend", "ui", "页面", "界面"]
    )

    proposed_tasks: list[ProposedTask] = [
        ProposedTask(
            title="需求分析与范围确认",
            description="整理并确认所有需求、范围边界、验收标准",
            suggested_role_code="architect",
            priority_hint="high",
        ),
        ProposedTask(
            title="技术方案设计",
            description="设计技术方案、数据模型、接口定义",
            suggested_role_code="architect",
            priority_hint="high",
        ),
    ]

    if has_frontend:
        proposed_tasks.append(
            ProposedTask(
                title="前端界面开发",
                description="实现前端页面和交互逻辑",
                suggested_role_code="frontend_developer",
                priority_hint="normal",
            )
        )

    if has_tech:
        proposed_tasks.append(
            ProposedTask(
                title="后端核心逻辑实现",
                description="实现核心业务逻辑、API 接口",
                suggested_role_code="developer",
                priority_hint="normal",
            )
        )

    proposed_tasks.extend([
        ProposedTask(
            title="测试与验证",
            description="编写和运行测试，验证功能正确性",
            suggested_role_code="tester",
            priority_hint="normal",
        ),
        ProposedTask(
            title="文档与交付物整理",
            description="整理代码文档、部署说明、交付物",
            suggested_role_code="developer",
            priority_hint="low",
        ),
    ])

    # ── Acceptance criteria from session answers ──
    acceptance_criteria: list[str] = []
    for q in session.clarifying_questions:
        answer = answers.get(q.id, "")
        if answer and "验收" in q.question:
            acceptance_criteria.append(f"根据用户回答: {answer[:200]}")

    if not acceptance_criteria:
        acceptance_criteria = [
            "所有 proposed_tasks 通过测试验证",
            "交付物符合目标描述",
            "用户验收通过",
        ]

    # ── Risks ──
    risks: list[str] = []
    for q in session.clarifying_questions:
        answer = answers.get(q.id, "")
        if answer and ("风险" in q.question or "依赖" in q.question):
            risks.append(f"用户提及: {answer[:200]}")

    if not risks:
        risks = [
            "范围蔓延：需求在实现过程中扩大",
            "技术复杂度超出预期",
            "依赖项延迟或不可用",
        ]

    return plan_summary, phases, proposed_tasks, acceptance_criteria, risks


# ── Service ──────────────────────────────────────────────────────────


class ProjectDirectorPlanService:
    """Business logic for Plan Version generation and confirmation."""

    def __init__(
        self,
        *,
        plan_version_repository: ProjectDirectorPlanVersionRepository,
        session_repository: ProjectDirectorSessionRepository,
    ) -> None:
        self._plan_repo = plan_version_repository
        self._session_repo = session_repository

    def create_plan_version(
        self, *, session_id: UUID
    ) -> ProjectDirectorPlanVersion:
        """Generate a deterministic plan version from a confirmed session.

        Requires the session to be in `confirmed` status.
        """

        session_obj = self._session_repo.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Session {session_id} not found")

        if session_obj.status != ProjectDirectorSessionStatus.CONFIRMED:
            raise ValueError(
                f"Session is in '{session_obj.status}' status. "
                f"Only confirmed sessions can generate plan versions. "
                f"Please confirm the goal first."
            )

        version_no = self._plan_repo.get_next_version_no(session_id)

        plan_summary, phases, proposed_tasks, acceptance_criteria, risks = (
            _generate_plan_from_session(session_obj)
        )

        now = datetime.now(timezone.utc)
        plan_version = ProjectDirectorPlanVersion(
            id=uuid4(),
            session_id=session_id,
            project_id=session_obj.project_id,
            version_no=version_no,
            status=PlanVersionStatus.PENDING_CONFIRMATION,
            plan_summary=plan_summary,
            phases=phases,
            proposed_tasks=proposed_tasks,
            acceptance_criteria=acceptance_criteria,
            risks=risks,
            forbidden_actions=list(_DEFAULT_FORBIDDEN_ACTIONS),
            confirmed_at=None,
            created_at=now,
            updated_at=now,
        )

        return self._plan_repo.create(plan_version)

    def get_plan_version(
        self, plan_version_id: UUID
    ) -> ProjectDirectorPlanVersion | None:
        """Return the plan version or None."""
        return self._plan_repo.get_by_id(plan_version_id)

    def list_plan_versions(
        self, session_id: UUID
    ) -> list[ProjectDirectorPlanVersion]:
        """List all plan versions for a session, newest first."""
        # Verify session exists
        if self._session_repo.get_by_id(session_id) is None:
            raise ValueError(f"Session {session_id} not found")
        return self._plan_repo.list_by_session_id(session_id)

    def confirm_plan_version(
        self, plan_version_id: UUID
    ) -> ProjectDirectorPlanVersion:
        """Confirm a plan version.

        Transitions: pending_confirmation → confirmed.
        Supersedes any previously confirmed plan version for the same session.
        Does NOT create tasks or call planning/apply.
        """

        plan_version = self._plan_repo.get_by_id(plan_version_id)
        if plan_version is None:
            raise ValueError(f"Plan version {plan_version_id} not found")

        if plan_version.status == PlanVersionStatus.CONFIRMED:
            return plan_version  # idempotent

        if plan_version.status != PlanVersionStatus.PENDING_CONFIRMATION:
            raise ValueError(
                f"Plan version is in '{plan_version.status}' status. "
                f"Only 'pending_confirmation' plan versions can be confirmed."
            )

        # Supersede any existing confirmed plan version for this session
        existing_confirmed = self._plan_repo.get_active_confirmed(
            plan_version.session_id
        )
        if existing_confirmed is not None:
            superseded = ProjectDirectorPlanVersion(
                id=existing_confirmed.id,
                session_id=existing_confirmed.session_id,
                project_id=existing_confirmed.project_id,
                version_no=existing_confirmed.version_no,
                status=PlanVersionStatus.SUPERSEDED,
                plan_summary=existing_confirmed.plan_summary,
                phases=existing_confirmed.phases,
                proposed_tasks=existing_confirmed.proposed_tasks,
                acceptance_criteria=existing_confirmed.acceptance_criteria,
                risks=existing_confirmed.risks,
                forbidden_actions=existing_confirmed.forbidden_actions,
                confirmed_at=existing_confirmed.confirmed_at,
                created_at=existing_confirmed.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            self._plan_repo.update(superseded)

        updated = ProjectDirectorPlanVersion(
            id=plan_version.id,
            session_id=plan_version.session_id,
            project_id=plan_version.project_id,
            version_no=plan_version.version_no,
            status=PlanVersionStatus.CONFIRMED,
            plan_summary=plan_version.plan_summary,
            phases=plan_version.phases,
            proposed_tasks=plan_version.proposed_tasks,
            acceptance_criteria=plan_version.acceptance_criteria,
            risks=plan_version.risks,
            forbidden_actions=plan_version.forbidden_actions,
            confirmed_at=datetime.now(timezone.utc),
            created_at=plan_version.created_at,
            updated_at=datetime.now(timezone.utc),
        )

        return self._plan_repo.update(updated)
