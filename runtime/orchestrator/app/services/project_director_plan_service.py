"""AI Project Director Plan Version service.

Stage 7-A4: provider-first plan draft generation with explicit rule fallback.
Draft generation remains review-only: no task creation, no worker dispatch, no
planning/apply, and no repository writes.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
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
from app.services.project_director_output_guardrails import (
    ProjectDirectorOutputGuardrailError,
    detect_provider_execution_claims,
    validate_plan_output,
)
from app.services.provider_config_service import ProviderConfigService


# ── Plan generation contracts ────────────────────────────────────────

PlanDraftSource = str
ProviderTextGenerator = Callable[[str, str, str], tuple[str, str | None]]


@dataclass(frozen=True, slots=True)
class PlanGenerationResult:
    """Review-only plan draft content plus provenance."""

    plan_summary: str
    phases: list[PlanPhase]
    proposed_tasks: list[ProposedTask]
    acceptance_criteria: list[str]
    risks: list[str]
    project_scope: ProjectScopeSummary
    agent_team_suggestions: list[AgentTeamSuggestion]
    skill_binding_suggestions: list[SkillBindingSuggestion]
    verification_mechanisms: list[VerificationMechanismSuggestion]
    repository_binding_suggestions: list[RepositoryBindingSuggestion]
    deliverable_boundaries: list[DeliverableBoundary]
    complexity_assessment: ComplexityAssessment
    source: PlanDraftSource
    source_detail: str
    provider_receipt_id: str | None = None
    normalization_warnings: list[str] = field(default_factory=list)


class ProjectDirectorPlanGenerationError(ValueError):
    """Raised when configured AI plan generation cannot produce a safe draft."""


# ── Deterministic fallback generation ────────────────────────────────

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
            "不调用真实 provider；不调用 Worker Pool；不调用 planning/apply",
            "不调用 apply-local；不执行 git-commit；不提交代码变更",
            "不写入仓库、不绑定真实远端仓库",
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
            requires_user_confirmation=True,
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
            safety_note=(
                "草案审核阶段只提示绑定建议；不执行目录扫描；不写仓库；"
                "不调用 apply-local；不执行 git-commit"
            ),
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


def _generate_rule_fallback_plan(
    session: "ProjectDirectorSession",  # noqa: F821
    *,
    revision_notes: str = "",
    reason: str,
) -> PlanGenerationResult:
    """Generate an explicit deterministic fallback plan draft."""

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
        session,
        revision_notes=revision_notes,
    )
    source_detail = f"deterministic_plan_generation; reason={reason[:220]}"
    return PlanGenerationResult(
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
        source="rule_fallback",
        source_detail=source_detail,
    )


def _build_plan_prompt(
    session: "ProjectDirectorSession",  # noqa: F821
    *,
    revision_notes: str = "",
) -> str:
    """Prompt the provider to produce a complete review-only JSON plan draft."""

    answers = {a.question_id: a.answer for a in session.clarifying_answers}
    answer_lines = []
    for question in session.clarifying_questions:
        answer_lines.append(
            {
                "question": question.question,
                "answer": answers.get(question.id, "（未回答）"),
            }
        )
    revision_block = revision_notes.strip() or "（无整改反馈）"
    return "\n".join(
        [
            "你是 AI-Dev-Orchestrator 的 AI 项目主管。",
            "请基于已确认目标、约束和澄清回答生成一份“可审核的项目作战计划草案”。",
            "草案只用于用户审核，不得承诺自动创建任务、调用 Worker、调用 planning/apply、写仓库或提交代码。",
            "只返回 JSON，不要 Markdown，不要解释。",
            "JSON 结构必须包含：",
            "{",
            '  "plan_summary": "string",',
            '  "phases": [{"sequence":1,"name":"string","goal":"string","task_count_hint":2}],',
            '  "proposed_tasks": [{"title":"string","description":"string","suggested_role_code":"architect|engineer|reviewer|product_manager","priority_hint":"high|normal|low"}],',
            '  "acceptance_criteria": ["string"],',
            '  "risks": ["string"],',
            '  "project_scope": {"in_scope":["string"],"out_of_scope":["string"],"assumptions":["string"]},',
            '  "agent_team_suggestions": [{"role_code":"product_manager|architect|engineer|reviewer","role_name":"string","responsibility":"string","collaboration_notes":["string"]}],',
            '  "skill_binding_suggestions": [{"skill_code":"string","owner_role_code":"product_manager|architect|engineer|reviewer","usage":"string","activation_stage":"string","binding_mode":"suggested","reason":"string"}],',
            '  "verification_mechanisms": [{"name":"string","command_or_method":"string","evidence_required":"string","owner_role_code":"reviewer","purpose":"string","risk_level":"low|normal|high","requires_user_confirmation":true}],',
            '  "repository_binding_suggestions": [{"binding_type":"review_only","binding_mode":"suggested","target":"string","branch":"未指定","focus_paths":["string"],"usage":"string","safety_note":"string"}],',
            '  "deliverable_boundaries": [{"name":"string","description":"string","owner_role_code":"product_manager|architect|engineer|reviewer","required_contents":["string"],"done_definition":"string","acceptance_signal":"string"}],',
            '  "complexity_assessment": {"level":"simple|medium|complex|large","label":"string","score":1,"recommended_agent_count":2,"drivers":["string"],"mitigation_suggestions":["string"]}',
            "}",
            "",
            "硬性要求：",
            "- suggested_role_code / role_code / owner_role_code 只能使用 product_manager、architect、engineer、reviewer。",
            "- 必须明确保留用户确认闸门，并在 out_of_scope 或 assumptions 里说明草案不会自动执行。",
            "- plan_summary 应结合用户目标和澄清回答，不要套用固定模板。",
            "",
            "用户目标：",
            session.goal_text.strip(),
            "",
            "用户约束：",
            session.constraints.strip() or "（用户未提供额外约束）",
            "",
            "澄清回答：",
            json.dumps(answer_lines, ensure_ascii=False),
            "",
            "整改反馈：",
            revision_block,
        ]
    )


def _extract_json_object(output_text: str) -> dict:
    """Extract one JSON object from plain text or fenced JSON output."""

    text = output_text.strip()
    if text.startswith("```"):
        lines = [
            line for line in text.splitlines()
            if not line.strip().startswith("```")
        ]
        text = "\n".join(lines).strip()
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("provider plan output must be a JSON object")
    return payload


def _parse_provider_plan_output(
    output_text: str,
    *,
    source_detail: str,
    provider_receipt_id: str | None,
    normalization_template: PlanGenerationResult,
) -> PlanGenerationResult:
    """Parse provider JSON into the plan contract with lenient non-core fill.

    Core conversational draft fields stay strict: the provider must return a
    JSON object with non-empty ``plan_summary``, ``phases`` and
    ``proposed_tasks``. Review-assist fields are normalized from the local
    deterministic template so a slightly incomplete provider response can still
    become a discussable, review-only draft.
    """

    payload = _extract_json_object(output_text)
    warnings: list[str] = []
    warnings.extend(
        detect_provider_execution_claims(output_text, context="plan_draft")
    )

    def _payload_value(key: str, aliases: tuple[str, ...] = ()) -> tuple[object, bool]:
        for candidate in (key, *aliases):
            if candidate in payload:
                return payload.get(candidate), candidate != key
        return None, False

    def _string_list(
        key: str,
        fallback: list[str],
        *,
        aliases: tuple[str, ...] = (),
    ) -> list[str]:
        raw, used_alias = _payload_value(key, aliases)
        if used_alias:
            warnings.append(f"{key}:mapped_from_provider_alias")
        if not isinstance(raw, list):
            warnings.append(f"{key}:filled_from_backend_template")
            return list(fallback)
        values = [str(item).strip() for item in raw if str(item).strip()]
        if not values:
            warnings.append(f"{key}:filled_from_backend_template")
            return list(fallback)
        return values

    def _model_list(
        key: str,
        model_type,
        fallback,
        *,
        aliases: tuple[str, ...] = (),
        normalizer=None,
    ):
        raw, used_alias = _payload_value(key, aliases)
        if used_alias:
            warnings.append(f"{key}:mapped_from_provider_alias")
        if not isinstance(raw, list):
            warnings.append(f"{key}:filled_from_backend_template")
            return list(fallback)
        try:
            prepared = [
                normalizer(item, index, fallback, warnings)
                if normalizer is not None
                else _normalize_role_fields(item, warnings)
                for index, item in enumerate(raw)
            ]
            items = [model_type(**item) for item in prepared]
        except (TypeError, ValueError):
            warnings.append(f"{key}:filled_from_backend_template")
            return list(fallback)
        if not items:
            warnings.append(f"{key}:filled_from_backend_template")
            return list(fallback)
        return items

    raw_plan_summary, summary_used_alias = _payload_value(
        "plan_summary",
        ("summary", "overview", "plan", "plan_overview"),
    )
    if summary_used_alias:
        warnings.append("plan_summary:mapped_from_provider_alias")
    plan_summary = str(raw_plan_summary or "").strip()
    if not plan_summary:
        raise ValueError("provider plan JSON missing plan_summary")

    raw_phases, phases_used_alias = _payload_value(
        "phases",
        ("stages", "plan_phases", "milestones"),
    )
    if phases_used_alias:
        warnings.append("phases:mapped_from_provider_alias")
    phases = [PlanPhase(**item) for item in raw_phases or []]

    raw_tasks, tasks_used_alias = _payload_value(
        "proposed_tasks",
        ("tasks", "task_list", "proposed_task_list"),
    )
    if tasks_used_alias:
        warnings.append("proposed_tasks:mapped_from_provider_alias")
    proposed_task_payloads = [
        _normalize_proposed_task(item, index, normalization_template.proposed_tasks, warnings)
        for index, item in enumerate(raw_tasks or [])
    ]
    proposed_tasks = [ProposedTask(**item) for item in proposed_task_payloads]
    if not phases:
        raise ValueError("provider plan JSON returned no phases")
    if not proposed_tasks:
        raise ValueError("provider plan JSON returned no proposed_tasks")

    project_scope, normalized_project_scope = _parse_project_scope(
        payload.get("project_scope"),
        fallback=normalization_template.project_scope,
    )
    if normalized_project_scope:
        warnings.append("project_scope:filled_safety_boundaries")

    agent_team_suggestions = _model_list(
        "agent_team_suggestions",
        AgentTeamSuggestion,
        normalization_template.agent_team_suggestions,
        aliases=("agent_team", "team", "roles"),
    )
    skill_binding_suggestions = _model_list(
        "skill_binding_suggestions",
        SkillBindingSuggestion,
        normalization_template.skill_binding_suggestions,
        aliases=("skill_bindings", "skills"),
    )
    verification_mechanisms = _model_list(
        "verification_mechanisms",
        VerificationMechanismSuggestion,
        normalization_template.verification_mechanisms,
        aliases=("verification", "validations", "test_plan"),
    )
    repository_binding_suggestions = _model_list(
        "repository_binding_suggestions",
        RepositoryBindingSuggestion,
        normalization_template.repository_binding_suggestions,
        aliases=("repository_bindings", "repository_suggestions"),
    )
    deliverable_boundaries = _model_list(
        "deliverable_boundaries",
        DeliverableBoundary,
        normalization_template.deliverable_boundaries,
        aliases=("deliverables", "delivery_boundaries"),
    )
    complexity_assessment, normalized_complexity = _parse_complexity_assessment(
        payload.get("complexity_assessment"),
        fallback=normalization_template.complexity_assessment,
    )
    if normalized_complexity:
        warnings.append("complexity_assessment:normalized_by_backend")
    acceptance_criteria = _string_list(
        "acceptance_criteria",
        normalization_template.acceptance_criteria,
        aliases=("acceptance", "criteria", "acceptanceCriteria"),
    )
    risks = _string_list(
        "risks",
        normalization_template.risks,
        aliases=("risk_list", "risk_assessment"),
    )
    normalized_source_detail = _append_normalization_source_detail(
        source_detail,
        warnings,
    )

    return PlanGenerationResult(
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
        source="ai",
        source_detail=normalized_source_detail,
        provider_receipt_id=provider_receipt_id,
        normalization_warnings=warnings,
    )


_ROLE_ALIAS_TO_CODE: dict[str, ProjectRoleCode] = {
    "pm": ProjectRoleCode.PRODUCT_MANAGER,
    "product": ProjectRoleCode.PRODUCT_MANAGER,
    "product_owner": ProjectRoleCode.PRODUCT_MANAGER,
    "product owner": ProjectRoleCode.PRODUCT_MANAGER,
    "product-manager": ProjectRoleCode.PRODUCT_MANAGER,
    "product manager": ProjectRoleCode.PRODUCT_MANAGER,
    "产品": ProjectRoleCode.PRODUCT_MANAGER,
    "产品经理": ProjectRoleCode.PRODUCT_MANAGER,
    "产品负责人": ProjectRoleCode.PRODUCT_MANAGER,
    "architecture": ProjectRoleCode.ARCHITECT,
    "solution_architect": ProjectRoleCode.ARCHITECT,
    "solution architect": ProjectRoleCode.ARCHITECT,
    "tech_lead": ProjectRoleCode.ARCHITECT,
    "tech lead": ProjectRoleCode.ARCHITECT,
    "架构": ProjectRoleCode.ARCHITECT,
    "架构师": ProjectRoleCode.ARCHITECT,
    "developer": ProjectRoleCode.ENGINEER,
    "dev": ProjectRoleCode.ENGINEER,
    "coder": ProjectRoleCode.ENGINEER,
    "programmer": ProjectRoleCode.ENGINEER,
    "backend": ProjectRoleCode.ENGINEER,
    "backend_engineer": ProjectRoleCode.ENGINEER,
    "frontend": ProjectRoleCode.ENGINEER,
    "frontend_developer": ProjectRoleCode.ENGINEER,
    "frontend engineer": ProjectRoleCode.ENGINEER,
    "fullstack": ProjectRoleCode.ENGINEER,
    "full_stack_engineer": ProjectRoleCode.ENGINEER,
    "engineer": ProjectRoleCode.ENGINEER,
    "工程师": ProjectRoleCode.ENGINEER,
    "开发": ProjectRoleCode.ENGINEER,
    "qa": ProjectRoleCode.REVIEWER,
    "tester": ProjectRoleCode.REVIEWER,
    "test": ProjectRoleCode.REVIEWER,
    "quality": ProjectRoleCode.REVIEWER,
    "quality_assurance": ProjectRoleCode.REVIEWER,
    "review": ProjectRoleCode.REVIEWER,
    "reviewer": ProjectRoleCode.REVIEWER,
    "评审": ProjectRoleCode.REVIEWER,
    "评审者": ProjectRoleCode.REVIEWER,
    "测试": ProjectRoleCode.REVIEWER,
}


def _normalize_proposed_task(
    raw_item: object,
    index: int,
    fallback_tasks: list[ProposedTask],
    warnings: list[str],
) -> dict:
    """Normalize one provider task item without making the task list optional."""

    fallback = fallback_tasks[min(index, len(fallback_tasks) - 1)] if fallback_tasks else None
    if isinstance(raw_item, str):
        warnings.append("proposed_tasks.item:mapped_from_string")
        data: dict[str, object] = {"title": raw_item}
    elif isinstance(raw_item, dict):
        data = dict(raw_item)
    else:
        warnings.append("proposed_tasks.item:filled_from_backend_template")
        return fallback.model_dump() if fallback is not None else {
            "title": f"任务 {index + 1}",
            "description": "Provider 返回的任务项结构不完整，由后端补齐为可审核草案任务。",
            "suggested_role_code": ProjectRoleCode.ENGINEER,
            "priority_hint": "normal",
        }

    title = _first_non_empty_text(
        data,
        "title",
        "name",
        "task",
        "task_name",
        "summary",
        "goal",
    )
    if not title and fallback is not None:
        title = fallback.title
        warnings.append("proposed_tasks.title:filled_from_backend_template")
    elif "title" not in data:
        warnings.append("proposed_tasks.title:mapped_from_provider_alias")

    description = _first_non_empty_text(
        data,
        "description",
        "details",
        "detail",
        "body",
        "goal",
    )
    if not description:
        description = (
            fallback.description
            if fallback is not None and fallback.description
            else "Provider 未提供任务描述；后端补齐为可审核草案占位描述。"
        )
        warnings.append("proposed_tasks.description:filled_from_backend_template")

    role_raw = _first_value(
        data,
        "suggested_role_code",
        "role_code",
        "role",
        "owner_role_code",
        "assignee_role",
    )
    role_code, role_normalized = _normalize_role_code(
        role_raw,
        fallback=(
            fallback.suggested_role_code
            if fallback is not None
            else ProjectRoleCode.ENGINEER
        ),
    )
    if role_normalized:
        warnings.append("proposed_tasks.suggested_role_code:normalized_role_enum")

    priority = _first_non_empty_text(
        data,
        "priority_hint",
        "priority",
        "importance",
    )
    if not priority:
        priority = fallback.priority_hint if fallback is not None else "normal"
        warnings.append("proposed_tasks.priority_hint:filled_from_backend_template")

    return {
        "title": title or f"任务 {index + 1}",
        "description": description,
        "suggested_role_code": role_code,
        "priority_hint": _normalize_priority_hint(priority),
    }


def _normalize_role_fields(raw_item: object, warnings: list[str]) -> dict:
    """Normalize role enum fields in non-core suggestion objects."""

    if not isinstance(raw_item, dict):
        raise TypeError("provider suggestion item must be an object")
    data = dict(raw_item)
    for field_name, fallback in (
        ("role_code", ProjectRoleCode.ENGINEER),
        ("owner_role_code", ProjectRoleCode.ENGINEER),
        ("suggested_role_code", ProjectRoleCode.ENGINEER),
    ):
        if field_name not in data:
            continue
        role_code, normalized = _normalize_role_code(
            data.get(field_name),
            fallback=fallback,
        )
        if normalized:
            warnings.append(f"{field_name}:normalized_role_enum")
        data[field_name] = role_code
    return data


def _normalize_role_code(
    raw_role: object,
    *,
    fallback: ProjectRoleCode,
) -> tuple[ProjectRoleCode, bool]:
    if isinstance(raw_role, ProjectRoleCode):
        return raw_role, False
    normalized = str(raw_role or "").strip()
    if not normalized:
        return fallback, True
    lowered = normalized.lower().replace("-", "_")
    try:
        return ProjectRoleCode(lowered), lowered != normalized
    except ValueError:
        pass
    compact = lowered.replace("_", " ")
    alias = _ROLE_ALIAS_TO_CODE.get(lowered) or _ROLE_ALIAS_TO_CODE.get(compact)
    if alias is not None:
        return alias, True
    return fallback, True


def _first_value(data: dict, *keys: str) -> object:
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def _first_non_empty_text(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _normalize_priority_hint(raw_priority: object) -> str:
    value = str(raw_priority or "normal").strip().lower()
    if value in {"urgent", "critical", "p0", "p1", "高", "最高", "高优先级"}:
        return "high"
    if value in {"low", "p3", "p4", "低", "低优先级"}:
        return "low"
    if value in {"high", "normal"}:
        return value
    return "normal"


def _parse_project_scope(
    raw_scope: object,
    *,
    fallback: ProjectScopeSummary,
) -> tuple[ProjectScopeSummary, bool]:
    """Parse project scope while preserving review-only safety boundaries."""

    if not isinstance(raw_scope, dict):
        return fallback, True

    data = dict(raw_scope)
    normalized = False
    fallback_data = fallback.model_dump()
    for key, value in fallback_data.items():
        if key not in data or not isinstance(data.get(key), list) or not data.get(key):
            data[key] = value
            normalized = True

    return ProjectScopeSummary(**data), normalized


def _parse_complexity_assessment(
    raw_complexity: object,
    *,
    fallback: ComplexityAssessment,
) -> tuple[ComplexityAssessment, bool]:
    """Parse provider complexity, normalizing only low-risk incomplete values."""

    if not isinstance(raw_complexity, dict):
        return fallback, True

    normalized = False
    data = dict(raw_complexity)
    fallback_data = fallback.model_dump()
    for key, value in fallback_data.items():
        if key not in data or data.get(key) in (None, "", []):
            data[key] = value
            normalized = True

    raw_score = data.get("score")
    if isinstance(raw_score, bool):
        data["score"] = fallback.score
        normalized = True
    else:
        score = _coerce_numeric_score(raw_score)
        if score is not None:
            clamped_score = min(5, max(1, score))
            if clamped_score != raw_score:
                data["score"] = clamped_score
                normalized = True

    return ComplexityAssessment(**data), normalized


def _append_normalization_source_detail(
    source_detail: str,
    warnings: list[str],
) -> str:
    """Append compact normalization provenance into existing source_detail."""

    if not warnings:
        return source_detail
    normalization_warnings = [
        item
        for item in warnings
        if not item.startswith("provider_execution_claim:")
    ]
    markers = []
    if normalization_warnings:
        markers.append("normalized_by_backend:plan_draft_schema")
    if any(item.startswith("complexity_assessment:") for item in warnings):
        markers.append("normalized_by_backend:complexity_assessment")
    if any(item.startswith("provider_execution_claim:") for item in warnings):
        markers.append("provider_execution_claim_detected")
    warning_text = ",".join(warnings)
    return (
        f"{source_detail}; {'; '.join(markers)};"
        f" normalization_warnings={warning_text}"
    )[:1000]


def _coerce_numeric_score(raw_score: object) -> int | None:
    if isinstance(raw_score, int):
        return raw_score
    if isinstance(raw_score, float) and raw_score.is_integer():
        return int(raw_score)
    if isinstance(raw_score, str):
        stripped = raw_score.strip()
        if stripped.isdigit() or (
            stripped.startswith("-") and stripped[1:].isdigit()
        ):
            return int(stripped)
    return None


# ── Service ──────────────────────────────────────────────────────────


class ProjectDirectorPlanService:
    """Business logic for Plan Version generation and confirmation."""

    def __init__(
        self,
        *,
        plan_version_repository: ProjectDirectorPlanVersionRepository,
        session_repository: ProjectDirectorSessionRepository,
        provider_config_service: ProviderConfigService | None = None,
        provider_text_generator: ProviderTextGenerator | None = None,
    ) -> None:
        self._plan_repo = plan_version_repository
        self._session_repo = session_repository
        self._provider_config_service = provider_config_service
        self._provider_text_generator = provider_text_generator

    def create_plan_version(
        self, *, session_id: UUID, revision_notes: str = ""
    ) -> ProjectDirectorPlanVersion:
        """Generate a provider-first plan version from a confirmed session.

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

        plan_draft = self._generate_plan_draft(
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
            plan_summary=plan_draft.plan_summary,
            phases=plan_draft.phases,
            proposed_tasks=plan_draft.proposed_tasks,
            acceptance_criteria=plan_draft.acceptance_criteria,
            risks=plan_draft.risks,
            project_scope=plan_draft.project_scope,
            agent_team_suggestions=plan_draft.agent_team_suggestions,
            skill_binding_suggestions=plan_draft.skill_binding_suggestions,
            verification_mechanisms=plan_draft.verification_mechanisms,
            repository_binding_suggestions=plan_draft.repository_binding_suggestions,
            deliverable_boundaries=plan_draft.deliverable_boundaries,
            complexity_assessment=plan_draft.complexity_assessment,
            source=plan_draft.source,
            source_detail=plan_draft.source_detail,
            forbidden_actions=list(_DEFAULT_FORBIDDEN_ACTIONS),
            confirmed_at=None,
            created_at=now,
            updated_at=now,
        )

        return self._plan_repo.create(plan_version)

    def _generate_plan_draft(
        self,
        session_obj: "ProjectDirectorSession",  # noqa: F821
        *,
        revision_notes: str = "",
    ) -> PlanGenerationResult:
        """Generate a review-only draft with narrow deterministic fallback.

        Fallback is allowed only before a provider attempt is possible: provider
        config cannot be read or no API key is configured. Once a configured
        provider is called, parsing, contract, guardrail, and provider-call
        failures are surfaced to the user instead of silently persisting a
        deterministic template draft.
        """

        provider_config_service = (
            self._provider_config_service or ProviderConfigService()
        )
        try:
            runtime_config = provider_config_service.resolve_openai_runtime_config()
        except Exception as exc:  # noqa: BLE001 - config failures must fallback
            return _generate_rule_fallback_plan(
                session_obj,
                revision_notes=revision_notes,
                reason=f"provider_config_unavailable:{exc}",
            )

        if not runtime_config.api_key:
            return _generate_rule_fallback_plan(
                session_obj,
                revision_notes=revision_notes,
                reason="provider_not_configured",
            )

        model_name = runtime_config.model_names.get(
            "balanced",
            next(iter(runtime_config.model_names.values()), "gpt-5.5"),
        )
        prompt_text = _build_plan_prompt(session_obj, revision_notes=revision_notes)
        request_id = f"project-director-plan-{uuid4().hex[:12]}"

        try:
            if self._provider_text_generator is not None:
                output_text, receipt_id = self._provider_text_generator(
                    model_name,
                    prompt_text,
                    request_id,
                )
            else:
                output_text, receipt_id = self._call_provider_text(
                    runtime_config=runtime_config,
                    model_name=model_name,
                    prompt_text=prompt_text,
                    request_id=request_id,
                )

            source_detail = (
                f"provider={runtime_config.detected_provider_type}; "
                f"model={model_name}; receipt={receipt_id or 'missing'}"
            )
            normalization_template = _generate_rule_fallback_plan(
                session_obj,
                revision_notes=revision_notes,
                reason="provider_schema_normalization_template",
            )
            plan_draft = _parse_provider_plan_output(
                output_text,
                source_detail=source_detail,
                provider_receipt_id=receipt_id,
                normalization_template=normalization_template,
            )
            validate_plan_output(
                goal_text=session_obj.goal_text,
                constraints=session_obj.constraints,
                plan_summary=plan_draft.plan_summary,
                phases=plan_draft.phases,
                proposed_tasks=plan_draft.proposed_tasks,
                acceptance_criteria=plan_draft.acceptance_criteria,
                risks=plan_draft.risks,
                project_scope=plan_draft.project_scope,
                agent_team_suggestions=plan_draft.agent_team_suggestions,
                skill_binding_suggestions=plan_draft.skill_binding_suggestions,
                verification_mechanisms=plan_draft.verification_mechanisms,
                repository_binding_suggestions=plan_draft.repository_binding_suggestions,
                deliverable_boundaries=plan_draft.deliverable_boundaries,
                complexity_assessment=plan_draft.complexity_assessment,
            )
            return plan_draft
        except ProjectDirectorOutputGuardrailError as exc:
            raise ProjectDirectorPlanGenerationError(
                "AI 项目主管已返回计划草案，但未通过安全边界校验；"
                f"请调整目标/约束后重试。原因：provider_guardrail_blocked:{exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001 - provider output/call failures are user-visible
            raise ProjectDirectorPlanGenerationError(
                "AI 项目主管计划草案生成失败，未创建系统规则模板草案；"
                f"请稍后重试或检查 Provider 输出。原因：provider_generation_failed:{exc}"
            ) from exc

    @staticmethod
    def _call_provider_text(
        *,
        runtime_config: object,
        model_name: str,
        prompt_text: str,
        request_id: str,
    ) -> tuple[str, str | None]:
        """Invoke the configured OpenAI-compatible provider."""

        from app.services.openai_provider_executor_service import (
            OpenAIProviderExecutorService,
        )

        executor = OpenAIProviderExecutorService(
            api_key=runtime_config.api_key,
            base_url=runtime_config.base_url,
            timeout_seconds=runtime_config.timeout_seconds,
        )
        response = executor.generate_text(
            model_name=model_name,
            prompt_text=prompt_text,
            request_id=request_id,
            prompt_key="project_director_plan_generation",
            provider_key=runtime_config.detected_provider_type,
        )
        receipt_id = None
        if response.provider_usage_receipt is not None:
            receipt_id = response.provider_usage_receipt.receipt_id
        return response.output_text or response.summary, receipt_id

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
            source=plan_version.source,
            source_detail=plan_version.source_detail,
            forbidden_actions=plan_version.forbidden_actions,
            confirmed_at=None,
            created_at=plan_version.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        return self._plan_repo.update(updated)

    def request_changes(
        self, *, plan_version_id: UUID, feedback: str
    ) -> tuple[ProjectDirectorPlanVersion, ProjectDirectorPlanVersion]:
        """Generate a replacement draft, then reject the original draft.

        If AI replacement generation fails, the original pending draft remains
        reviewable; no deterministic template replacement is created.
        """

        normalized_feedback = feedback.strip()
        if not normalized_feedback:
            raise ValueError(
                "feedback must not be empty when action=request_changes"
            )

        original = self._require_pending_plan_version(plan_version_id)
        replacement = self.create_plan_version(
            session_id=original.session_id,
            revision_notes=normalized_feedback,
        )
        rejected = self.reject_plan_version(plan_version_id)
        return rejected, replacement

    def _require_pending_plan_version(
        self,
        plan_version_id: UUID,
    ) -> ProjectDirectorPlanVersion:
        plan_version = self._plan_repo.get_by_id(plan_version_id)
        if plan_version is None:
            raise ValueError(f"Plan version {plan_version_id} not found")
        if plan_version.status != PlanVersionStatus.PENDING_CONFIRMATION:
            raise ValueError(
                f"Plan version is in '{plan_version.status}' status. "
                f"Only 'pending_confirmation' plan versions can be rejected."
            )
        return plan_version

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
                source=existing_confirmed.source,
                source_detail=existing_confirmed.source_detail,
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
            source=plan_version.source,
            source_detail=plan_version.source_detail,
            forbidden_actions=plan_version.forbidden_actions,
            confirmed_at=datetime.now(timezone.utc),
            created_at=plan_version.created_at,
            updated_at=datetime.now(timezone.utc),
        )

        return self._plan_repo.update(updated)
