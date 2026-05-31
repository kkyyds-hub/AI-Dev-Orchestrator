"""AI Project Director Plan Version service.

BCG-02 Phase1: deterministic plan generation from confirmed sessions.
No AI, no Provider, no task creation, no worker dispatch.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.project_director_plan_version import (
    AgentTeamSuggestion,
    ComplexityAssessment,
    DeliverableBoundary,
    PlanPhase,
    PlanVersionStatus,
    ProjectDirectorPlanVersion,
    ProjectScopeSummary,
    ProposedTask,
    RepositoryBindingSuggestion,
    SkillBindingSuggestion,
    VerificationMechanismSuggestion,
)
from app.domain.project_director_session import ProjectDirectorSessionStatus
from app.domain.project_role import ProjectRoleCode
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

_ROLE_NAMES = {
    ProjectRoleCode.PRODUCT_MANAGER: "产品负责人",
    ProjectRoleCode.ARCHITECT: "架构师",
    ProjectRoleCode.ENGINEER: "工程师",
    ProjectRoleCode.REVIEWER: "评审者",
}


def _generate_plan_from_session(
    session: "ProjectDirectorSession",  # noqa: F821
    *,
    revision_notes: str = "",
) -> tuple[
    str,
    list[PlanPhase],
    list[ProposedTask],
    list[str],
    list[str],
    ProjectScopeSummary,
    list[AgentTeamSuggestion],
    list[SkillBindingSuggestion],
    list[VerificationMechanismSuggestion],
    list[RepositoryBindingSuggestion],
    list[DeliverableBoundary],
    ComplexityAssessment,
]:
    """Generate a deterministic plan from a confirmed session.

    Returns review-only draft content. It does not create projects, tasks,
    agent sessions, skill bindings, repository bindings, provider calls,
    Worker runs, planning/apply calls, apply-local writes, or git commits.
    """

    from app.domain.project_director_session import ProjectDirectorSession

    goal = session.goal_text
    constraints = session.constraints
    answers = {a.question_id: a.answer for a in session.clarifying_answers}
    revision_note_text = revision_notes.strip()

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

    if revision_note_text:
        answer_lines.extend(
            [
                "\n## 整改说明\n",
                revision_note_text,
            ]
        )

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
            suggested_role_code=ProjectRoleCode.ARCHITECT,
            priority_hint="high",
        ),
        ProposedTask(
            title="技术方案设计",
            description="设计技术方案、数据模型、接口定义",
            suggested_role_code=ProjectRoleCode.ARCHITECT,
            priority_hint="high",
        ),
    ]

    if has_frontend:
        proposed_tasks.append(
            ProposedTask(
                title="前端界面开发",
                description="实现前端页面和交互逻辑",
                suggested_role_code=ProjectRoleCode.ENGINEER,
                priority_hint="normal",
            )
        )

    if has_tech:
        proposed_tasks.append(
            ProposedTask(
                title="后端核心逻辑实现",
                description="实现核心业务逻辑、API 接口",
                suggested_role_code=ProjectRoleCode.ENGINEER,
                priority_hint="normal",
            )
        )

    proposed_tasks.extend([
        ProposedTask(
            title="测试与验证",
            description="编写和运行测试，验证功能正确性",
            suggested_role_code=ProjectRoleCode.REVIEWER,
            priority_hint="normal",
        ),
        ProposedTask(
            title="文档与交付物整理",
            description="整理代码文档、部署说明、交付物",
            suggested_role_code=ProjectRoleCode.ENGINEER,
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

    if revision_note_text:
        risks.insert(
            0,
            f"整改反馈需重点处理：{revision_note_text[:200]}",
        )

    # ── Review-only enriched draft content ──
    scope_sources = [goal]
    if constraints:
        scope_sources.append(constraints)
    scope_sources.extend(answer for answer in answers.values() if answer)
    scope_text = " ".join(scope_sources).lower()

    project_scope = ProjectScopeSummary(
        in_scope=[
            "澄清并固化项目目标、关键约束、验收口径与阶段边界",
            "生成可审核的阶段拆分、拟议任务、角色分工、交付件与验证建议",
            "保留用户确认闸门：草案通过前只读展示，不进入真实执行链路",
        ],
        out_of_scope=[
            "不自动创建 Project、Task、Agent Session 或 Skill 绑定",
            "不调用真实 provider、Worker Pool、planning/apply、apply-local 或 git-commit",
            "不写入仓库、不绑定真实远端仓库、不提交代码变更",
        ],
        assumptions=[
            "用户确认草案后，后续任务创建、Worker 调度、仓库写入仍需单独显式触发",
            "当前草案基于 Project Director 会话目标、约束和澄清答案的本地确定性规则生成",
            *(
                [f"整改反馈已纳入草案增强字段：{revision_note_text[:200]}"]
                if revision_note_text
                else []
            ),
        ],
    )

    agent_team_suggestions = [
        AgentTeamSuggestion(
            role_code=ProjectRoleCode.PRODUCT_MANAGER,
            role_name=_ROLE_NAMES[ProjectRoleCode.PRODUCT_MANAGER],
            responsibility="持续确认目标、范围、不做范围、交付件验收口径与用户反馈优先级",
            collaboration_notes=["作为需求入口", "在每轮 request_changes 后重新核对范围漂移"],
        ),
        AgentTeamSuggestion(
            role_code=ProjectRoleCode.ARCHITECT,
            role_name=_ROLE_NAMES[ProjectRoleCode.ARCHITECT],
            responsibility="负责阶段拆分、技术边界、依赖识别、仓库影响面和复杂度判断",
            collaboration_notes=["先输出设计与风险", "再交给 engineer 拆执行任务"],
        ),
        AgentTeamSuggestion(
            role_code=ProjectRoleCode.ENGINEER,
            role_name=_ROLE_NAMES[ProjectRoleCode.ENGINEER],
            responsibility="在草案确认并单独创建任务后，承接实现、联调和交付件更新",
            collaboration_notes=["仅在任务队列创建后执行", "不得由草案审核自动启动 Worker"],
        ),
        AgentTeamSuggestion(
            role_code=ProjectRoleCode.REVIEWER,
            role_name=_ROLE_NAMES[ProjectRoleCode.REVIEWER],
            responsibility="负责验证策略、证据完整性、回归检查和审批前质量闸门",
            collaboration_notes=["定义最小测试命令", "检查 evidence 与交付件是否一致"],
        ),
    ]

    skill_binding_suggestions = [
        SkillBindingSuggestion(
            skill_code="manage-v5-plan-and-freeze-docs",
            owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
            usage="用于冻结目标、范围、不做范围、交付件边界和阶段记录；本草案只建议绑定，不创建绑定记录",
            activation_stage="规划/澄清",
            binding_mode="suggested",
            reason="需要产品负责人先确认范围、验收口径和 request_changes 反馈是否被吸收",
        ),
        SkillBindingSuggestion(
            skill_code="write-v5-runtime-backend",
            owner_role_code=ProjectRoleCode.ENGINEER,
            usage="后端领域、服务、路由、仓储或 schema 变更时由实现任务显式调用",
            activation_stage="实现",
            binding_mode="suggested",
            reason="只有在用户确认草案并单独创建实现任务后，才建议由工程师使用后端实现 skill",
        ),
        SkillBindingSuggestion(
            skill_code="write-v5-web-control-surface",
            owner_role_code=ProjectRoleCode.ENGINEER,
            usage="前端控制面、弹窗、类型合同和页面展示变更时由实现任务显式调用",
            activation_stage="实现/展示",
            binding_mode="suggested",
            reason="当前只是展示建议；真实前端执行需后续显式任务承接",
        ),
        SkillBindingSuggestion(
            skill_code="verify-v5-runtime-and-regression",
            owner_role_code=ProjectRoleCode.REVIEWER,
            usage="用于运行后端测试、前端 build、API/页面最小回归并记录事实结果",
            activation_stage="验证",
            binding_mode="suggested",
            reason="验证 skill 应在实现任务完成后显式触发，不能由草案审核自动执行",
        ),
    ]

    verification_mechanisms = [
        VerificationMechanismSuggestion(
            name="后端合同测试",
            command_or_method="pytest runtime/orchestrator/tests/test_project_director_plan_versions.py",
            evidence_required="响应中包含项目范围、Agent 编队、Skill 建议、验证机制、仓库建议、交付件边界和复杂度评估字段",
            owner_role_code=ProjectRoleCode.REVIEWER,
            purpose="验证后端 API 合同、持久化读回和 request_changes 新版本字段完整性",
            risk_level="high",
            requires_user_confirmation=False,
        ),
        VerificationMechanismSuggestion(
            name="前端构建检查",
            command_or_method="npm --prefix apps/web run build",
            evidence_required="TypeScript 类型与计划审核弹窗展示通过构建检查",
            owner_role_code=ProjectRoleCode.REVIEWER,
            purpose="验证 Project Director 计划审核弹窗能展示增强字段且类型合同未破坏",
            risk_level="normal",
            requires_user_confirmation=False,
        ),
    ]

    if has_tech:
        verification_mechanisms.append(
            VerificationMechanismSuggestion(
                name="实现后最小回归",
                command_or_method="按任务类型补充单元测试、接口 smoke 或页面 build；命令需在后续执行任务中明确",
                evidence_required="测试命令、退出码、关键输出和未覆盖范围说明",
                owner_role_code=ProjectRoleCode.REVIEWER,
                purpose="在真实实现任务完成后再确认执行结果，不把草案确认误判为运行通过",
                risk_level="normal",
                requires_user_confirmation=False,
            )
        )

    repository_binding_suggestions = [
        RepositoryBindingSuggestion(
            binding_type="review_only",
            binding_mode="suggested",
            target="当前项目关联仓库（如后续由用户显式绑定）",
            branch="未指定",
            focus_paths=[
                "runtime/orchestrator/app/",
                "runtime/orchestrator/tests/",
                "apps/web/src/features/project-director/",
                "apps/web/src/pages/workbench/components/",
            ],
            usage="用于后续文件定位、变更计划和交付件证据读取；本草案不创建 repository binding",
            safety_note="草案审核阶段只提示绑定建议，不执行目录扫描、仓库写入、apply-local 或 git-commit",
        )
    ]

    deliverable_boundaries = [
        DeliverableBoundary(
            name="范围与不做范围说明",
            description="用于让用户确认本轮项目草案覆盖什么、明确排除什么，以及哪些假设仍需保留",
            owner_role_code=ProjectRoleCode.PRODUCT_MANAGER,
            required_contents=["目标", "范围内", "范围外", "关键假设", "验收口径"],
            done_definition="用户能据此判断草案是否覆盖本轮 Project Director 目标",
            acceptance_signal="用户确认范围和不做范围无缺口；request_changes 反馈已在 assumptions 或风险中可见",
        ),
        DeliverableBoundary(
            name="阶段计划与拟议任务清单",
            description="用于把目标拆成可审核阶段、拟议任务和建议角色，但不直接创建真实任务队列",
            owner_role_code=ProjectRoleCode.ARCHITECT,
            required_contents=["阶段", "任务标题", "建议角色", "优先级", "依赖/风险"],
            done_definition="通过审核后可作为后续显式创建任务队列的输入依据，但不会自动创建任务",
            acceptance_signal="用户能看清每个阶段产出、任务责任和后续显式创建任务边界",
        ),
        DeliverableBoundary(
            name="验证与交付证据包",
            description="用于定义后续实现完成后的测试、构建、风险复核和未覆盖范围说明",
            owner_role_code=ProjectRoleCode.REVIEWER,
            required_contents=["测试命令", "构建结果", "风险复核", "未覆盖范围"],
            done_definition="实现任务完成后能独立复核质量，不把草案确认误判为总闭环 Pass",
            acceptance_signal="测试命令、构建结果和风险复核均有可回放证据，且未覆盖范围被明确列出",
        ),
    ]

    complexity_score = 1
    complexity_drivers: list[str] = ["基础目标拆分"]
    if char_count >= 60:
        complexity_score += 1
        complexity_drivers.append("目标描述较长，需要多阶段拆解")
    if char_count >= 200:
        complexity_score += 1
        complexity_drivers.append("目标较复杂，可能涉及较多依赖与交付件")
    if has_frontend:
        complexity_score += 1
        complexity_drivers.append("包含前端/UI 展示面")
    if has_tech:
        complexity_score += 1
        complexity_drivers.append("包含代码/API/实现工作")
    if any(
        token in scope_text
        for token in ["仓库", "repository", "git", "部署", "provider", "worker"]
    ):
        complexity_score += 1
        complexity_drivers.append("涉及仓库、部署、provider 或 Worker 等高风险边界词")
    if revision_note_text:
        complexity_drivers.append(f"request_changes 整改反馈：{revision_note_text[:200]}")
    complexity_score = min(complexity_score, 5)
    complexity_level = (
        "simple"
        if complexity_score <= 2
        else "medium"
        if complexity_score == 3
        else "complex"
        if complexity_score == 4
        else "large"
    )
    complexity_label = {
        "simple": "简单",
        "medium": "中等复杂度",
        "complex": "复杂",
        "large": "大型复杂",
    }[complexity_level]
    recommended_agent_count = min(4, max(2, complexity_score))
    complexity_assessment = ComplexityAssessment(
        level=complexity_level,
        label=complexity_label,
        score=complexity_score,
        recommended_agent_count=recommended_agent_count,
        drivers=complexity_drivers,
        mitigation_suggestions=[
            "先确认范围/不做范围，再进入任务创建",
            "把真实执行、仓库写入和 Skill 绑定留到后续显式动作",
            "每个实现任务必须附带验证命令与可回放证据",
        ],
    )

    return (
        plan_summary,
        phases,
        proposed_tasks,
        acceptance_criteria,
        risks,
        project_scope,
        agent_team_suggestions,
        skill_binding_suggestions,
        verification_mechanisms,
        repository_binding_suggestions,
        deliverable_boundaries,
        complexity_assessment,
    )


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
        self, *, session_id: UUID, revision_notes: str = ""
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

        (
            plan_summary,
            phases,
            proposed_tasks,
            acceptance_criteria,
            risks,
            project_scope,
            agent_team_suggestions,
            skill_binding_suggestions,
            verification_mechanisms,
            repository_binding_suggestions,
            deliverable_boundaries,
            complexity_assessment,
        ) = _generate_plan_from_session(
            session_obj,
            revision_notes=revision_notes,
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
            project_scope=project_scope,
            agent_team_suggestions=agent_team_suggestions,
            skill_binding_suggestions=skill_binding_suggestions,
            verification_mechanisms=verification_mechanisms,
            repository_binding_suggestions=repository_binding_suggestions,
            deliverable_boundaries=deliverable_boundaries,
            complexity_assessment=complexity_assessment,
            forbidden_actions=list(_DEFAULT_FORBIDDEN_ACTIONS),
            confirmed_at=None,
            created_at=now,
            updated_at=now,
        )

        return self._plan_repo.create(plan_version)

    def reject_plan_version(
        self, plan_version_id: UUID
    ) -> ProjectDirectorPlanVersion:
        """Reject one pending_confirmation plan version."""

        plan_version = self._plan_repo.get_by_id(plan_version_id)
        if plan_version is None:
            raise ValueError(f"Plan version {plan_version_id} not found")

        if plan_version.status == PlanVersionStatus.REJECTED:
            return plan_version

        if plan_version.status != PlanVersionStatus.PENDING_CONFIRMATION:
            raise ValueError(
                f"Plan version is in '{plan_version.status}' status. "
                f"Only 'pending_confirmation' plan versions can be rejected."
            )

        updated = ProjectDirectorPlanVersion(
            id=plan_version.id,
            session_id=plan_version.session_id,
            project_id=plan_version.project_id,
            version_no=plan_version.version_no,
            status=PlanVersionStatus.REJECTED,
            plan_summary=plan_version.plan_summary,
            phases=plan_version.phases,
            proposed_tasks=plan_version.proposed_tasks,
            acceptance_criteria=plan_version.acceptance_criteria,
            risks=plan_version.risks,
            project_scope=plan_version.project_scope,
            agent_team_suggestions=plan_version.agent_team_suggestions,
            skill_binding_suggestions=plan_version.skill_binding_suggestions,
            verification_mechanisms=plan_version.verification_mechanisms,
            repository_binding_suggestions=plan_version.repository_binding_suggestions,
            deliverable_boundaries=plan_version.deliverable_boundaries,
            complexity_assessment=plan_version.complexity_assessment,
            forbidden_actions=plan_version.forbidden_actions,
            confirmed_at=None,
            created_at=plan_version.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        return self._plan_repo.update(updated)

    def request_changes(
        self, *, plan_version_id: UUID, feedback: str
    ) -> tuple[ProjectDirectorPlanVersion, ProjectDirectorPlanVersion]:
        """Reject one draft and generate a new pending_confirmation version."""

        normalized_feedback = feedback.strip()
        if not normalized_feedback:
            raise ValueError(
                "feedback must not be empty when action=request_changes"
            )

        rejected = self.reject_plan_version(plan_version_id)
        replacement = self.create_plan_version(
            session_id=rejected.session_id,
            revision_notes=normalized_feedback,
        )
        return rejected, replacement

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
                project_scope=existing_confirmed.project_scope,
                agent_team_suggestions=existing_confirmed.agent_team_suggestions,
                skill_binding_suggestions=existing_confirmed.skill_binding_suggestions,
                verification_mechanisms=existing_confirmed.verification_mechanisms,
                repository_binding_suggestions=existing_confirmed.repository_binding_suggestions,
                deliverable_boundaries=existing_confirmed.deliverable_boundaries,
                complexity_assessment=existing_confirmed.complexity_assessment,
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
            project_scope=plan_version.project_scope,
            agent_team_suggestions=plan_version.agent_team_suggestions,
            skill_binding_suggestions=plan_version.skill_binding_suggestions,
            verification_mechanisms=plan_version.verification_mechanisms,
            repository_binding_suggestions=plan_version.repository_binding_suggestions,
            deliverable_boundaries=plan_version.deliverable_boundaries,
            complexity_assessment=plan_version.complexity_assessment,
            forbidden_actions=plan_version.forbidden_actions,
            confirmed_at=datetime.now(timezone.utc),
            created_at=plan_version.created_at,
            updated_at=datetime.now(timezone.utc),
        )

        return self._plan_repo.update(updated)
