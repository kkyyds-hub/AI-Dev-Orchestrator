"""SOP template selection, stage checklist and task-generation helpers for V3 Day06."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.project import (
    Project,
    ProjectMilestone,
    ProjectMilestoneCode,
    ProjectStage,
    ProjectStageBlockingTask,
)
from app.domain.project_role import ProjectRoleCode, ProjectRoleConfig
from app.domain.task import Task, TaskPriority, TaskRiskLevel
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.services.context_builder_service import ContextBuilderService
from app.services.role_catalog_service import RoleCatalogService
from app.services.task_service import TaskService
from app.services.task_state_machine_service import TaskStateMachineService


@dataclass(slots=True, frozen=True)
class SopTaskTemplate:
    """One stable SOP task blueprint inside a stage."""

    code: str
    title: str
    input_summary: str
    acceptance_criteria: tuple[str, ...]
    priority: TaskPriority = TaskPriority.NORMAL
    risk_level: TaskRiskLevel = TaskRiskLevel.NORMAL
    owner_role_codes: tuple[ProjectRoleCode, ...] = ()
    depends_on_codes: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class SopStageTemplate:
    """One stage definition inside a SOP template."""

    stage: ProjectStage
    title: str
    summary: str
    required_inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    guard_conditions: tuple[str, ...]
    owner_role_codes: tuple[ProjectRoleCode, ...]
    task_templates: tuple[SopTaskTemplate, ...]


@dataclass(slots=True, frozen=True)
class SopTemplate:
    """One reusable project SOP template."""

    code: str
    name: str
    summary: str
    description: str
    is_default: bool
    stage_templates: tuple[SopStageTemplate, ...]

    def get_stage(self, stage: ProjectStage) -> SopStageTemplate:
        """Return the matching stage definition or raise for developer misuse."""

        for stage_template in self.stage_templates:
            if stage_template.stage == stage:
                return stage_template

        raise ValueError(f"SOP template {self.code} does not define stage {stage}.")


@dataclass(slots=True, frozen=True)
class SopTemplateStagePreview:
    """Lightweight stage preview exposed to the UI."""

    stage: ProjectStage
    title: str
    owner_role_codes: tuple[ProjectRoleCode, ...]


@dataclass(slots=True, frozen=True)
class SopTemplateSummary:
    """Serializable summary returned by the catalog endpoint."""

    code: str
    name: str
    summary: str
    description: str
    is_default: bool
    stages: tuple[SopTemplateStagePreview, ...]


@dataclass(slots=True, frozen=True)
class ProjectSopOwnerRole:
    """Resolved owner role shown in the project SOP snapshot."""

    role_code: ProjectRoleCode
    name: str
    summary: str
    enabled: bool


@dataclass(slots=True, frozen=True)
class ProjectSopStageTask:
    """One current-stage task resolved from a SOP template."""

    task_id: UUID
    task_code: str
    title: str
    status: str
    owner_role_codes: tuple[ProjectRoleCode, ...]
    owner_role_names: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class ProjectSopSnapshot:
    """Current SOP snapshot returned on project detail."""

    project_id: UUID
    has_template: bool
    available_template_count: int
    selected_template_code: str | None
    selected_template_name: str | None
    selected_template_summary: str | None
    current_stage: ProjectStage
    current_stage_title: str | None
    current_stage_summary: str | None
    next_stage: ProjectStage | None
    can_advance: bool | None
    blocking_reasons: list[str]
    required_inputs: list[str]
    expected_outputs: list[str]
    guard_conditions: list[str]
    owner_roles: list[ProjectSopOwnerRole]
    stage_tasks: list[ProjectSopStageTask]
    current_stage_task_count: int
    current_stage_completed_task_count: int
    all_current_stage_tasks_completed: bool
    context_summary: str


@dataclass(slots=True, frozen=True)
class SopStageGuardEvaluation:
    """SOP-specific stage guard result consumed by ProjectStageService."""

    milestones: list[ProjectMilestone]
    blocking_tasks: list[ProjectStageBlockingTask]
    current_stage_task_count: int
    current_stage_completed_task_count: int


@dataclass(slots=True, frozen=True)
class ProjectSopSyncResult:
    """Outcome returned after syncing one stage's SOP tasks."""

    project: Project
    stage: ProjectStage
    created_tasks: list[Task]


@dataclass(slots=True, frozen=True)
class ProjectSopSelectionResult:
    """Outcome returned after binding one project to a SOP template."""

    project: Project
    template: SopTemplate
    created_tasks: list[Task]
    snapshot: ProjectSopSnapshot
    message: str


_SOP_SOURCE_PREFIX = "sop"
_DEFAULT_TEMPLATE_CODE = "std_delivery"

_TEMPLATES: tuple[SopTemplate, ...] = (
    SopTemplate(
        code="std_delivery",
        name="标准产品交付",
        summary="适用于从需求澄清、方案规划到交付上线的常规研发项目。",
        description="通过清晰的阶段清单、角色责任和模板任务，把项目推进从自由对话切换为 SOP 驱动。",
        is_default=True,
        stage_templates=(
            SopStageTemplate(
                stage=ProjectStage.INTAKE,
                title="需求澄清",
                summary="明确项目目标、边界与验收口径，为后续规划建立统一入口。",
                required_inputs=(
                    "老板 brief / 项目摘要",
                    "范围边界或优先级说明",
                    "初始验收口径与关键约束",
                ),
                expected_outputs=(
                    "统一的项目目标与成功标准",
                    "明确的范围边界与风险提示",
                    "可进入规划阶段的输入摘要",
                ),
                guard_conditions=(
                    "项目保持 active 状态",
                    "本阶段 SOP 任务全部完成",
                    "需求目标、范围和验收口径已经明确",
                ),
                owner_role_codes=(ProjectRoleCode.PRODUCT_MANAGER,),
                task_templates=(
                    SopTaskTemplate(
                        code="brief_sync",
                        title="澄清项目目标与边界",
                        input_summary="整理老板 brief，输出统一的目标、范围边界与成功标准。",
                        acceptance_criteria=(
                            "明确项目目标、核心价值与非目标项",
                            "记录关键约束、风险与待确认假设",
                            "形成可进入规划阶段的书面摘要",
                        ),
                        priority=TaskPriority.HIGH,
                        owner_role_codes=(ProjectRoleCode.PRODUCT_MANAGER,),
                    ),
                    SopTaskTemplate(
                        code="accept_gate",
                        title="整理验收口径与关键约束",
                        input_summary="把验收标准、上线边界和不可突破的约束整理成阶段输入。",
                        acceptance_criteria=(
                            "列出核心验收口径",
                            "记录资源/时间/依赖约束",
                            "补齐进入规划所需的关键问题清单",
                        ),
                        priority=TaskPriority.HIGH,
                        owner_role_codes=(ProjectRoleCode.PRODUCT_MANAGER,),
                        depends_on_codes=("brief_sync",),
                    ),
                ),
            ),
            SopStageTemplate(
                stage=ProjectStage.PLANNING,
                title="方案规划",
                summary="把目标转成可执行方案、任务拆解和阶段路径。",
                required_inputs=(
                    "已澄清的目标、范围和验收口径",
                    "当前代码/系统约束",
                    "角色目录与默认职责边界",
                ),
                expected_outputs=(
                    "实施方案或技术路径摘要",
                    "任务拆解、依赖与优先级建议",
                    "进入执行阶段的最小启动包",
                ),
                guard_conditions=(
                    "项目保持 active 状态",
                    "本阶段 SOP 任务全部完成",
                    "方案、任务拆解与依赖关系已经确认",
                ),
                owner_role_codes=(
                    ProjectRoleCode.PRODUCT_MANAGER,
                    ProjectRoleCode.ARCHITECT,
                ),
                task_templates=(
                    SopTaskTemplate(
                        code="plan_path",
                        title="输出实施方案与阶段路径",
                        input_summary="结合需求和现状约束，形成可执行的阶段方案、边界说明与风险提示。",
                        acceptance_criteria=(
                            "给出阶段目标、关键路径与实施边界",
                            "说明主要技术/流程风险",
                            "形成进入执行所需的启动说明",
                        ),
                        priority=TaskPriority.HIGH,
                        risk_level=TaskRiskLevel.HIGH,
                        owner_role_codes=(
                            ProjectRoleCode.PRODUCT_MANAGER,
                            ProjectRoleCode.ARCHITECT,
                        ),
                    ),
                    SopTaskTemplate(
                        code="map_work",
                        title="拆解任务与依赖",
                        input_summary="把阶段方案拆成可交付任务，明确依赖、优先级和验收口径。",
                        acceptance_criteria=(
                            "任务拆解覆盖当前阶段的核心工作",
                            "关键依赖和前置条件已记录",
                            "每个任务具备最小验收标准",
                        ),
                        priority=TaskPriority.HIGH,
                        owner_role_codes=(
                            ProjectRoleCode.PRODUCT_MANAGER,
                            ProjectRoleCode.ARCHITECT,
                        ),
                        depends_on_codes=("plan_path",),
                    ),
                ),
            ),
            SopStageTemplate(
                stage=ProjectStage.EXECUTION,
                title="执行落地",
                summary="完成核心实现、局部验证和交付说明沉淀。",
                required_inputs=(
                    "已确认的实施方案与任务拆解",
                    "当前代码上下文与运行约束",
                    "验收标准、风险提示与依赖条件",
                ),
                expected_outputs=(
                    "核心实现结果",
                    "局部验证/自测记录",
                    "变更说明与遗留项摘要",
                ),
                guard_conditions=(
                    "项目保持 active 状态",
                    "本阶段 SOP 任务全部完成",
                    "核心实现、自测记录和变更说明已补齐",
                ),
                owner_role_codes=(ProjectRoleCode.ENGINEER,),
                task_templates=(
                    SopTaskTemplate(
                        code="build_core",
                        title="完成核心实现与本地验证",
                        input_summary="基于实施方案完成核心改动，并补齐最小自测或本地验证记录。",
                        acceptance_criteria=(
                            "核心改动已经落地",
                            "关键路径具备最小验证结果",
                            "保留失败/风险说明和待跟进项",
                        ),
                        priority=TaskPriority.HIGH,
                        risk_level=TaskRiskLevel.HIGH,
                        owner_role_codes=(ProjectRoleCode.ENGINEER,),
                    ),
                    SopTaskTemplate(
                        code="write_notes",
                        title="整理变更说明与遗留项",
                        input_summary="沉淀本阶段实现说明、已知限制与建议的后续跟进项。",
                        acceptance_criteria=(
                            "交付说明可供评审继续接手",
                            "已知风险和限制被明确记录",
                            "必要时给出回退或补救建议",
                        ),
                        owner_role_codes=(ProjectRoleCode.ENGINEER,),
                        depends_on_codes=("build_core",),
                    ),
                ),
            ),
            SopStageTemplate(
                stage=ProjectStage.VERIFICATION,
                title="评审验证",
                summary="围绕验收标准复核交付结果，并形成通过/阻塞结论。",
                required_inputs=(
                    "实现结果与变更说明",
                    "验收标准与阶段守卫要求",
                    "已知风险、限制与验证记录",
                ),
                expected_outputs=(
                    "验收结论",
                    "缺口/风险列表",
                    "可进入交付阶段的评审摘要",
                ),
                guard_conditions=(
                    "项目保持 active 状态",
                    "本阶段 SOP 任务全部完成",
                    "验收结论和风险意见已经形成",
                ),
                owner_role_codes=(ProjectRoleCode.REVIEWER,),
                task_templates=(
                    SopTaskTemplate(
                        code="verify_gate",
                        title="执行验收检查与回归确认",
                        input_summary="根据验收口径复核交付结果，确认是否满足当前阶段的质量门槛。",
                        acceptance_criteria=(
                            "覆盖关键验收口径",
                            "记录未通过项和风险说明",
                            "形成通过/阻塞的初步结论",
                        ),
                        priority=TaskPriority.HIGH,
                        risk_level=TaskRiskLevel.HIGH,
                        owner_role_codes=(ProjectRoleCode.REVIEWER,),
                    ),
                    SopTaskTemplate(
                        code="review_notes",
                        title="形成评审结论与风险说明",
                        input_summary="沉淀评审意见、风险摘要和是否允许进入交付阶段的结论。",
                        acceptance_criteria=(
                            "形成结构化评审结论",
                            "说明主要风险与回退建议",
                            "输出可供老板/下游继续处理的摘要",
                        ),
                        owner_role_codes=(ProjectRoleCode.REVIEWER,),
                        depends_on_codes=("verify_gate",),
                    ),
                ),
            ),
            SopStageTemplate(
                stage=ProjectStage.DELIVERY,
                title="交付收口",
                summary="整理交付摘要、上线说明和遗留项跟进，为项目收口留痕。",
                required_inputs=(
                    "通过评审的交付结果",
                    "评审结论与风险说明",
                    "上线/交接相关信息",
                ),
                expected_outputs=(
                    "交付摘要或上线说明",
                    "遗留项与后续跟进清单",
                    "可回放的项目收口记录",
                ),
                guard_conditions=(
                    "项目处于最终交付阶段",
                    "本阶段 SOP 任务全部完成",
                    "交付摘要和后续跟进项已经记录",
                ),
                owner_role_codes=(
                    ProjectRoleCode.PRODUCT_MANAGER,
                    ProjectRoleCode.REVIEWER,
                ),
                task_templates=(
                    SopTaskTemplate(
                        code="delivery_pkg",
                        title="整理交付摘要与上线说明",
                        input_summary="沉淀交付范围、上线注意事项、关键风险和老板可直接查看的摘要。",
                        acceptance_criteria=(
                            "交付范围与结果清晰可回放",
                            "上线或发布注意事项已记录",
                            "关键风险和限制被明确提示",
                        ),
                        priority=TaskPriority.HIGH,
                        owner_role_codes=(
                            ProjectRoleCode.PRODUCT_MANAGER,
                            ProjectRoleCode.REVIEWER,
                        ),
                    ),
                    SopTaskTemplate(
                        code="followups",
                        title="确认遗留项与后续跟进",
                        input_summary="整理需要继续跟进的遗留项、负责人建议与后续动作。",
                        acceptance_criteria=(
                            "列出遗留项和建议跟进方向",
                            "说明是否需要继续观察或复盘",
                            "为 Day09+ 交付件与审批扩展预留摘要",
                        ),
                        owner_role_codes=(
                            ProjectRoleCode.PRODUCT_MANAGER,
                            ProjectRoleCode.REVIEWER,
                        ),
                        depends_on_codes=("delivery_pkg",),
                    ),
                ),
            ),
        ),
    ),
    SopTemplate(
        code="hotfix_flow",
        name="缺陷热修复",
        summary="适用于线上缺陷、紧急补丁与快速回归场景。",
        description="通过更紧凑的阶段清单和风险关注点，把修复链路控制在最小必要闭环内。",
        is_default=False,
        stage_templates=(
            SopStageTemplate(
                stage=ProjectStage.INTAKE,
                title="故障确认",
                summary="确认缺陷影响面、紧急等级与修复边界。",
                required_inputs=(
                    "缺陷描述、影响范围与严重程度",
                    "相关日志、监控或复现路径",
                    "回滚窗口与值班信息",
                ),
                expected_outputs=(
                    "明确的修复边界",
                    "风险与回滚约束",
                    "可进入修复规划的最小输入",
                ),
                guard_conditions=(
                    "项目保持 active 状态",
                    "本阶段 SOP 任务全部完成",
                    "故障影响与回滚窗口已经确认",
                ),
                owner_role_codes=(
                    ProjectRoleCode.PRODUCT_MANAGER,
                    ProjectRoleCode.ENGINEER,
                ),
                task_templates=(
                    SopTaskTemplate(
                        code="scope_issue",
                        title="确认故障影响与修复边界",
                        input_summary="整理缺陷现象、影响范围和修复目标，避免热修复范围继续扩大。",
                        acceptance_criteria=(
                            "明确影响用户/模块/场景",
                            "记录本次修复不覆盖的范围",
                            "形成可执行的问题摘要",
                        ),
                        priority=TaskPriority.HIGH,
                        risk_level=TaskRiskLevel.HIGH,
                        owner_role_codes=(
                            ProjectRoleCode.PRODUCT_MANAGER,
                            ProjectRoleCode.ENGINEER,
                        ),
                    ),
                    SopTaskTemplate(
                        code="freeze_risk",
                        title="记录回滚窗口与高风险项",
                        input_summary="明确发布窗口、回滚方式和需要重点防守的高风险点。",
                        acceptance_criteria=(
                            "记录回滚方式与窗口限制",
                            "列出高风险模块或依赖",
                            "补齐进入规划所需的风险摘要",
                        ),
                        priority=TaskPriority.HIGH,
                        risk_level=TaskRiskLevel.HIGH,
                        owner_role_codes=(
                            ProjectRoleCode.PRODUCT_MANAGER,
                            ProjectRoleCode.ENGINEER,
                        ),
                        depends_on_codes=("scope_issue",),
                    ),
                ),
            ),
            SopStageTemplate(
                stage=ProjectStage.PLANNING,
                title="修复规划",
                summary="确定热修复方案、影响范围与最小验证面。",
                required_inputs=(
                    "故障边界与风险摘要",
                    "关键代码/系统上下文",
                    "回滚和监控要求",
                ),
                expected_outputs=(
                    "热修复方案",
                    "受影响模块与验证点清单",
                    "最小发布与回退路径",
                ),
                guard_conditions=(
                    "项目保持 active 状态",
                    "本阶段 SOP 任务全部完成",
                    "方案、影响面和验证点已经确认",
                ),
                owner_role_codes=(
                    ProjectRoleCode.ARCHITECT,
                    ProjectRoleCode.ENGINEER,
                ),
                task_templates=(
                    SopTaskTemplate(
                        code="fix_plan",
                        title="确定热修复方案",
                        input_summary="给出热修复思路、改动边界和必要的风险控制点。",
                        acceptance_criteria=(
                            "方案覆盖根因与修复路径",
                            "说明潜在副作用与回退方式",
                            "形成可直接执行的修复说明",
                        ),
                        priority=TaskPriority.HIGH,
                        risk_level=TaskRiskLevel.HIGH,
                        owner_role_codes=(
                            ProjectRoleCode.ARCHITECT,
                            ProjectRoleCode.ENGINEER,
                        ),
                    ),
                    SopTaskTemplate(
                        code="impact_scan",
                        title="列出受影响模块与验证点",
                        input_summary="明确热修复涉及的模块、关键回归点和需要重点观察的指标。",
                        acceptance_criteria=(
                            "列出受影响模块与关键依赖",
                            "形成最小验证点清单",
                            "补齐上线前的监控关注项",
                        ),
                        priority=TaskPriority.HIGH,
                        owner_role_codes=(
                            ProjectRoleCode.ARCHITECT,
                            ProjectRoleCode.ENGINEER,
                        ),
                        depends_on_codes=("fix_plan",),
                    ),
                ),
            ),
            SopStageTemplate(
                stage=ProjectStage.EXECUTION,
                title="修复实施",
                summary="完成补丁落地与最小自测留痕。",
                required_inputs=(
                    "已确认的热修复方案",
                    "受影响模块与验证点清单",
                    "发布窗口与回退要求",
                ),
                expected_outputs=(
                    "修复实现结果",
                    "最小自测记录",
                    "待重点观察的风险摘要",
                ),
                guard_conditions=(
                    "项目保持 active 状态",
                    "本阶段 SOP 任务全部完成",
                    "修复实现与自测记录已经补齐",
                ),
                owner_role_codes=(ProjectRoleCode.ENGINEER,),
                task_templates=(
                    SopTaskTemplate(
                        code="ship_fix",
                        title="完成修复实现",
                        input_summary="落地热修复改动，确保修复范围与规划保持一致。",
                        acceptance_criteria=(
                            "修复代码或配置已完成",
                            "与规划边界保持一致",
                            "记录潜在剩余风险",
                        ),
                        priority=TaskPriority.HIGH,
                        risk_level=TaskRiskLevel.HIGH,
                        owner_role_codes=(ProjectRoleCode.ENGINEER,),
                    ),
                    SopTaskTemplate(
                        code="self_check",
                        title="执行最小自测与日志留痕",
                        input_summary="完成关键路径自测，并留存能够支撑评审和发布的最小证据。",
                        acceptance_criteria=(
                            "关键验证点已覆盖",
                            "保留最小自测/日志记录",
                            "说明仍需关注的风险",
                        ),
                        priority=TaskPriority.HIGH,
                        owner_role_codes=(ProjectRoleCode.ENGINEER,),
                        depends_on_codes=("ship_fix",),
                    ),
                ),
            ),
            SopStageTemplate(
                stage=ProjectStage.VERIFICATION,
                title="发布前验证",
                summary="确认缺陷已关闭、关键风险受控且具备回滚准备。",
                required_inputs=(
                    "修复实现结果与自测记录",
                    "验证点与监控关注项",
                    "回滚窗口与应急方案",
                ),
                expected_outputs=(
                    "验证结论",
                    "回滚/监控准备确认",
                    "是否允许发布的结论",
                ),
                guard_conditions=(
                    "项目保持 active 状态",
                    "本阶段 SOP 任务全部完成",
                    "验证结论和回滚准备已经确认",
                ),
                owner_role_codes=(ProjectRoleCode.REVIEWER,),
                task_templates=(
                    SopTaskTemplate(
                        code="verify_fix",
                        title="验证缺陷已关闭",
                        input_summary="复核修复结果是否真正关闭故障，并确认没有明显引入新问题。",
                        acceptance_criteria=(
                            "核心故障场景复核通过",
                            "关键回归点已确认",
                            "形成是否放行的初步结论",
                        ),
                        priority=TaskPriority.HIGH,
                        risk_level=TaskRiskLevel.HIGH,
                        owner_role_codes=(ProjectRoleCode.REVIEWER,),
                    ),
                    SopTaskTemplate(
                        code="guard_roll",
                        title="确认回滚与监控方案",
                        input_summary="确认发布窗口、监控看护点和需要预备的回滚动作。",
                        acceptance_criteria=(
                            "监控和看护点已记录",
                            "回滚动作清晰可执行",
                            "形成发布前的风险摘要",
                        ),
                        priority=TaskPriority.HIGH,
                        risk_level=TaskRiskLevel.HIGH,
                        owner_role_codes=(ProjectRoleCode.REVIEWER,),
                        depends_on_codes=("verify_fix",),
                    ),
                ),
            ),
            SopStageTemplate(
                stage=ProjectStage.DELIVERY,
                title="发布收口",
                summary="输出热修复发布说明、值班同步和后续观察点。",
                required_inputs=(
                    "允许发布的验证结论",
                    "回滚与监控准备",
                    "受影响团队或值班信息",
                ),
                expected_outputs=(
                    "发布说明",
                    "值班/运营同步摘要",
                    "后续观察与复盘项",
                ),
                guard_conditions=(
                    "项目处于最终交付阶段",
                    "本阶段 SOP 任务全部完成",
                    "发布说明和值班同步已经留痕",
                ),
                owner_role_codes=(
                    ProjectRoleCode.PRODUCT_MANAGER,
                    ProjectRoleCode.REVIEWER,
                ),
                task_templates=(
                    SopTaskTemplate(
                        code="release_note",
                        title="输出热修复发布说明",
                        input_summary="沉淀本次热修复的发布范围、注意事项和关键风险说明。",
                        acceptance_criteria=(
                            "发布范围和影响面清晰",
                            "关键风险与注意事项已记录",
                            "可供老板和值班团队直接查看",
                        ),
                        priority=TaskPriority.HIGH,
                        owner_role_codes=(
                            ProjectRoleCode.PRODUCT_MANAGER,
                            ProjectRoleCode.REVIEWER,
                        ),
                    ),
                    SopTaskTemplate(
                        code="ops_sync",
                        title="同步值班/运营后续动作",
                        input_summary="整理上线后观察点、值班协同说明和是否需要继续复盘的事项。",
                        acceptance_criteria=(
                            "值班和运营需关注的事项已记录",
                            "后续观察点和复盘项已补齐",
                            "形成完整的发布收口说明",
                        ),
                        owner_role_codes=(
                            ProjectRoleCode.PRODUCT_MANAGER,
                            ProjectRoleCode.REVIEWER,
                        ),
                        depends_on_codes=("release_note",),
                    ),
                ),
            ),
        ),
    ),
)


class SopEngineService:
    """Bind projects to SOP templates and keep current-stage tasks in sync."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        task_repository: TaskRepository,
        task_service: TaskService,
        role_catalog_service: RoleCatalogService,
        context_builder_service: ContextBuilderService,
        task_state_machine_service: TaskStateMachineService,
    ) -> None:
        self.project_repository = project_repository
        self.task_repository = task_repository
        self.task_service = task_service
        self.role_catalog_service = role_catalog_service
        self.context_builder_service = context_builder_service
        self.task_state_machine_service = task_state_machine_service
        self._template_map = {template.code: template for template in _TEMPLATES}

    def list_template_summaries(self) -> list[SopTemplateSummary]:
        """Return the built-in Day06 template catalog."""

        return [
            SopTemplateSummary(
                code=template.code,
                name=template.name,
                summary=template.summary,
                description=template.description,
                is_default=template.is_default,
                stages=tuple(
                    SopTemplateStagePreview(
                        stage=stage.stage,
                        title=stage.title,
                        owner_role_codes=stage.owner_role_codes,
                    )
                    for stage in template.stage_templates
                ),
            )
            for template in _TEMPLATES
        ]

    def get_template(self, template_code: str | None) -> SopTemplate | None:
        """Resolve one template by code."""

        if template_code is None:
            return None
        return self._template_map.get(template_code)

    def select_project_template(
        self,
        *,
        project_id: UUID,
        template_code: str,
    ) -> ProjectSopSelectionResult | None:
        """Bind one project to a SOP template and generate current-stage tasks."""

        project = self.project_repository.get_by_id(project_id)
        if project is None:
            return None

        template = self.get_template(template_code)
        if template is None:
            raise ValueError(f"Unknown SOP template: {template_code}")

        existing_tasks = self.task_repository.list_by_project_id(project_id)
        if (
            project.sop_template_code is not None
            and project.sop_template_code != template.code
            and any(self._is_sop_managed_task(task) for task in existing_tasks)
        ):
            raise ValueError(
                "Current project already has generated SOP tasks. "
                "Day06 does not support switching to another template after generation."
            )

        updated_project = (
            project
            if project.sop_template_code == template.code
            else self.project_repository.update_sop_template(
                project_id,
                sop_template_code=template.code,
            )
        )
        sync_result = self.ensure_current_stage_tasks(
            project=updated_project,
            tasks=self.task_repository.list_by_project_id(project_id),
        )
        snapshot = self.get_project_sop_snapshot(
            project=sync_result.project,
            tasks=self.task_repository.list_by_project_id(project_id),
            next_stage=None,
            can_advance=None,
            blocking_reasons=[],
        )

        created_task_count = len(sync_result.created_tasks)
        message = (
            f"已为项目绑定 SOP 模板「{template.name}」，"
            f"并同步当前阶段 {created_task_count} 个模板任务。"
        )
        if created_task_count == 0:
            message = (
                f"项目已使用 SOP 模板「{template.name}」，当前阶段没有缺失的模板任务。"
            )

        return ProjectSopSelectionResult(
            project=sync_result.project,
            template=template,
            created_tasks=sync_result.created_tasks,
            snapshot=snapshot,
            message=message,
        )

    def ensure_current_stage_tasks(
        self,
        *,
        project: Project,
        tasks: list[Task] | None = None,
    ) -> ProjectSopSyncResult:
        """Generate any missing SOP tasks for the project's current stage."""

        template = self.get_template(project.sop_template_code)
        if template is None:
            return ProjectSopSyncResult(project=project, stage=project.stage, created_tasks=[])

        stage_template = template.get_stage(project.stage)
        stage_template_order = {
            item.stage: index for index, item in enumerate(template.stage_templates)
        }
        stage_index = stage_template_order.get(project.stage, 0)
        previous_stage_template = (
            template.stage_templates[stage_index - 1] if stage_index > 0 else None
        )
        next_stage_template = (
            template.stage_templates[stage_index + 1]
            if stage_index < len(template.stage_templates) - 1
            else None
        )
        existing_tasks = tasks or self.task_repository.list_by_project_id(project.id)
        existing_by_source = {
            task.source_draft_id: task
            for task in existing_tasks
            if task.source_draft_id is not None
        }
        stage_task_id_by_code: dict[str, UUID] = {}
        for task_template in stage_template.task_templates:
            source_draft_id = self._build_source_draft_id(
                template_code=template.code,
                stage=project.stage,
                task_code=task_template.code,
            )
            existing_task = existing_by_source.get(source_draft_id)
            if existing_task is not None:
                stage_task_id_by_code[task_template.code] = existing_task.id

        created_tasks: list[Task] = []
        for task_template in stage_template.task_templates:
            source_draft_id = self._build_source_draft_id(
                template_code=template.code,
                stage=project.stage,
                task_code=task_template.code,
            )
            if source_draft_id in existing_by_source:
                continue

            dependency_ids = [
                stage_task_id_by_code[dependency_code]
                for dependency_code in task_template.depends_on_codes
                if dependency_code in stage_task_id_by_code
            ]
            owner_role_code = (
                task_template.owner_role_codes[0]
                if task_template.owner_role_codes
                else (
                    stage_template.owner_role_codes[0]
                    if stage_template.owner_role_codes
                    else None
                )
            )
            dependency_owner_role_code = next(
                (
                    dependency_template.owner_role_codes[0]
                    for dependency_template in stage_template.task_templates
                    if dependency_template.code in task_template.depends_on_codes
                    and dependency_template.owner_role_codes
                ),
                None,
            )
            downstream_role_code = next(
                (
                    child_template.owner_role_codes[0]
                    for child_template in stage_template.task_templates
                    if task_template.code in child_template.depends_on_codes
                    and child_template.owner_role_codes
                ),
                None,
            )
            if downstream_role_code is None and next_stage_template is not None:
                downstream_role_code = (
                    next_stage_template.owner_role_codes[0]
                    if next_stage_template.owner_role_codes
                    else None
                )
            upstream_role_code = dependency_owner_role_code
            if upstream_role_code is None and previous_stage_template is not None:
                upstream_role_code = (
                    previous_stage_template.owner_role_codes[-1]
                    if previous_stage_template.owner_role_codes
                    else None
                )
            created_task = self.task_service.create_task(
                project_id=project.id,
                title=task_template.title,
                input_summary=task_template.input_summary,
                priority=task_template.priority,
                acceptance_criteria=list(task_template.acceptance_criteria),
                depends_on_task_ids=dependency_ids,
                risk_level=task_template.risk_level,
                owner_role_code=owner_role_code,
                upstream_role_code=upstream_role_code,
                downstream_role_code=downstream_role_code,
                source_draft_id=source_draft_id,
            )
            created_tasks.append(created_task)
            existing_by_source[source_draft_id] = created_task
            stage_task_id_by_code[task_template.code] = created_task.id

        refreshed_project = self.project_repository.get_by_id(project.id) or project
        return ProjectSopSyncResult(
            project=refreshed_project,
            stage=project.stage,
            created_tasks=created_tasks,
        )

    def build_stage_guard_evaluation(
        self,
        *,
        project: Project,
        tasks: list[Task],
    ) -> SopStageGuardEvaluation | None:
        """Build SOP-specific milestones that gate the current stage exit."""

        template = self.get_template(project.sop_template_code)
        if template is None:
            return None

        stage_template = template.get_stage(project.stage)
        stage_tasks = self._list_stage_tasks(
            tasks=tasks,
            template_code=template.code,
            stage=project.stage,
        )
        owner_roles = self._resolve_owner_roles(project=project, stage_template=stage_template)

        milestones = [
            ProjectMilestone(
                code=ProjectMilestoneCode.SOP_TEMPLATE_SELECTED,
                title="已绑定 SOP 模板",
                satisfied=True,
                summary=f"当前项目使用模板「{template.name}」，阶段推进将遵循模板清单。",
            ),
            self._build_required_roles_milestone(
                stage_template=stage_template,
                owner_roles=owner_roles,
            ),
            self._build_stage_tasks_completed_milestone(
                stage_template=stage_template,
                stage_tasks=stage_tasks,
            ),
        ]
        blocking_tasks = [
            ProjectStageBlockingTask(
                task_id=task.id,
                title=task.title,
                status=task.status,
                blocking_reasons=[
                    self.task_state_machine_service.build_project_stage_block_message(
                        task.status
                    )
                ],
            )
            for task in stage_tasks
            if not self.task_state_machine_service.is_project_stage_complete(task.status)
        ]
        completed_stage_task_count = sum(
            1
            for task in stage_tasks
            if self.task_state_machine_service.is_project_stage_complete(task.status)
        )
        return SopStageGuardEvaluation(
            milestones=milestones,
            blocking_tasks=blocking_tasks,
            current_stage_task_count=len(stage_tasks),
            current_stage_completed_task_count=completed_stage_task_count,
        )

    def get_project_sop_snapshot(
        self,
        *,
        project: Project,
        tasks: list[Task] | None = None,
        next_stage: ProjectStage | None,
        can_advance: bool | None,
        blocking_reasons: list[str],
    ) -> ProjectSopSnapshot:
        """Build the current project's SOP snapshot for the detail API."""

        available_template_count = len(_TEMPLATES)
        template = self.get_template(project.sop_template_code)
        if template is None:
            return ProjectSopSnapshot(
                project_id=project.id,
                has_template=False,
                available_template_count=available_template_count,
                selected_template_code=None,
                selected_template_name=None,
                selected_template_summary=None,
                current_stage=project.stage,
                current_stage_title=None,
                current_stage_summary=None,
                next_stage=next_stage,
                can_advance=can_advance,
                blocking_reasons=list(blocking_reasons),
                required_inputs=[],
                expected_outputs=[],
                guard_conditions=[],
                owner_roles=[],
                stage_tasks=[],
                current_stage_task_count=0,
                current_stage_completed_task_count=0,
                all_current_stage_tasks_completed=False,
                context_summary=(
                    "当前项目尚未选择 SOP 模板。请选择一个模板后，系统会生成当前阶段任务、"
                    "展示角色责任与阶段清单，并在后续阶段推进时继续按模板补齐任务。"
                ),
            )

        stage_template = template.get_stage(project.stage)
        project_tasks = tasks or self.task_repository.list_by_project_id(project.id)
        stage_tasks = self._list_stage_tasks(
            tasks=project_tasks,
            template_code=template.code,
            stage=project.stage,
        )
        owner_roles = self._resolve_owner_roles(project=project, stage_template=stage_template)
        context_package = self.context_builder_service.build_project_stage_context(
            project=project,
            template_code=template.code,
            template_name=template.name,
            stage_title=stage_template.title,
            owner_roles=owner_roles,
            required_inputs=list(stage_template.required_inputs),
            expected_outputs=list(stage_template.expected_outputs),
            guard_conditions=list(stage_template.guard_conditions),
            stage_tasks=stage_tasks,
            can_advance=can_advance,
            blocking_reasons=blocking_reasons,
        )
        stage_task_items = self._build_stage_task_items(
            stage_template=stage_template,
            stage_tasks=stage_tasks,
            owner_roles=owner_roles,
        )
        completed_stage_task_count = sum(
            1
            for task in stage_tasks
            if self.task_state_machine_service.is_project_stage_complete(task.status)
        )

        return ProjectSopSnapshot(
            project_id=project.id,
            has_template=True,
            available_template_count=available_template_count,
            selected_template_code=template.code,
            selected_template_name=template.name,
            selected_template_summary=template.summary,
            current_stage=project.stage,
            current_stage_title=stage_template.title,
            current_stage_summary=stage_template.summary,
            next_stage=next_stage,
            can_advance=can_advance,
            blocking_reasons=list(blocking_reasons),
            required_inputs=list(stage_template.required_inputs),
            expected_outputs=list(stage_template.expected_outputs),
            guard_conditions=list(stage_template.guard_conditions),
            owner_roles=[
                ProjectSopOwnerRole(
                    role_code=role.role_code,
                    name=role.name,
                    summary=role.summary,
                    enabled=role.enabled,
                )
                for role in owner_roles
            ],
            stage_tasks=stage_task_items,
            current_stage_task_count=len(stage_tasks),
            current_stage_completed_task_count=completed_stage_task_count,
            all_current_stage_tasks_completed=(
                len(stage_tasks) > 0 and completed_stage_task_count == len(stage_tasks)
            ),
            context_summary=context_package.context_summary,
        )

    def _resolve_owner_roles(
        self,
        *,
        project: Project,
        stage_template: SopStageTemplate,
    ) -> list[ProjectRoleConfig]:
        """Resolve the configured role cards for one stage."""

        project_role_catalog = self.role_catalog_service.get_project_role_catalog(project.id)
        role_map = (
            {role.role_code: role for role in project_role_catalog.roles}
            if project_role_catalog is not None
            else {}
        )
        return [
            role_map[role_code]
            for role_code in stage_template.owner_role_codes
            if role_code in role_map
        ]

    def _build_required_roles_milestone(
        self,
        *,
        stage_template: SopStageTemplate,
        owner_roles: list[ProjectRoleConfig],
    ) -> ProjectMilestone:
        """Check whether the current stage's owner roles are enabled."""

        enabled_role_codes = {role.role_code for role in owner_roles if role.enabled}
        missing_or_disabled_roles = [
            role_code
            for role_code in stage_template.owner_role_codes
            if role_code not in enabled_role_codes
        ]
        if not missing_or_disabled_roles:
            role_names = "、".join(role.name for role in owner_roles) or "默认角色"
            return ProjectMilestone(
                code=ProjectMilestoneCode.SOP_REQUIRED_ROLES_ENABLED,
                title="阶段责任角色已启用",
                satisfied=True,
                summary=f"当前阶段责任角色为「{role_names}」，均已处于启用状态。",
            )

        role_names = "、".join(role_code.value for role_code in missing_or_disabled_roles)
        return ProjectMilestone(
            code=ProjectMilestoneCode.SOP_REQUIRED_ROLES_ENABLED,
            title="阶段责任角色已启用",
            satisfied=False,
            summary=f"当前阶段仍有责任角色未启用：{role_names}。",
            blocking_reasons=[f"请先启用当前阶段的责任角色：{role_names}。"],
        )

    def _build_stage_tasks_completed_milestone(
        self,
        *,
        stage_template: SopStageTemplate,
        stage_tasks: list[Task],
    ) -> ProjectMilestone:
        """Check whether all current-stage SOP tasks are complete."""

        if not stage_tasks:
            return ProjectMilestone(
                code=ProjectMilestoneCode.SOP_STAGE_TASKS_COMPLETED,
                title="当前阶段 SOP 任务已完成",
                satisfied=False,
                summary=f"当前阶段「{stage_template.title}」尚未生成模板任务。",
                blocking_reasons=["请先同步当前阶段的 SOP 模板任务。"],
            )

        completed_count = sum(
            1
            for task in stage_tasks
            if self.task_state_machine_service.is_project_stage_complete(task.status)
        )
        if completed_count == len(stage_tasks):
            return ProjectMilestone(
                code=ProjectMilestoneCode.SOP_STAGE_TASKS_COMPLETED,
                title="当前阶段 SOP 任务已完成",
                satisfied=True,
                summary=(
                    f"当前阶段「{stage_template.title}」的 {len(stage_tasks)} 个模板任务已全部完成。"
                ),
                related_task_ids=[task.id for task in stage_tasks],
            )

        return ProjectMilestone(
            code=ProjectMilestoneCode.SOP_STAGE_TASKS_COMPLETED,
            title="当前阶段 SOP 任务已完成",
            satisfied=False,
            summary=(
                f"当前阶段「{stage_template.title}」还有 "
                f"{len(stage_tasks) - completed_count} 个模板任务未完成。"
            ),
            blocking_reasons=["请先完成当前阶段的 SOP 模板任务，再推进到下一阶段。"],
            related_task_ids=[task.id for task in stage_tasks],
        )

    def _build_stage_task_items(
        self,
        *,
        stage_template: SopStageTemplate,
        stage_tasks: list[Task],
        owner_roles: list[ProjectRoleConfig],
    ) -> list[ProjectSopStageTask]:
        """Attach template metadata to each current-stage task."""

        task_template_map = {
            task_template.code: task_template
            for task_template in stage_template.task_templates
        }
        role_name_map = {role.role_code: role.name for role in owner_roles}
        task_order = {
            task_template.code: index
            for index, task_template in enumerate(stage_template.task_templates)
        }
        items: list[ProjectSopStageTask] = []
        for task in stage_tasks:
            task_code = self._extract_task_code(task.source_draft_id)
            task_template = task_template_map.get(task_code or "")
            owner_role_codes = (
                task_template.owner_role_codes
                if task_template is not None
                else ()
            )
            items.append(
                ProjectSopStageTask(
                    task_id=task.id,
                    task_code=task_code or "",
                    title=task.title,
                    status=task.status.value,
                    owner_role_codes=owner_role_codes,
                    owner_role_names=tuple(
                        role_name_map.get(role_code, role_code.value)
                        for role_code in owner_role_codes
                    ),
                )
            )

        return sorted(
            items,
            key=lambda item: (task_order.get(item.task_code, 99), item.title),
        )

    def _list_stage_tasks(
        self,
        *,
        tasks: list[Task],
        template_code: str,
        stage: ProjectStage,
    ) -> list[Task]:
        """Filter one project's tasks down to the current SOP stage."""

        prefix = self._build_source_prefix(template_code=template_code, stage=stage)
        return [
            task
            for task in tasks
            if task.source_draft_id is not None and task.source_draft_id.startswith(prefix)
        ]

    @staticmethod
    def _build_source_prefix(*, template_code: str, stage: ProjectStage) -> str:
        """Build the stable prefix used by all tasks inside one SOP stage."""

        return f"{_SOP_SOURCE_PREFIX}:{template_code}:{stage.value}:"

    @classmethod
    def _build_source_draft_id(
        cls,
        *,
        template_code: str,
        stage: ProjectStage,
        task_code: str,
    ) -> str:
        """Build the stable source draft identifier for one SOP task."""

        return cls._build_source_prefix(template_code=template_code, stage=stage) + task_code

    @staticmethod
    def _extract_task_code(source_draft_id: str | None) -> str | None:
        """Extract the stable task code from one SOP-managed source draft ID."""

        if not source_draft_id:
            return None
        parts = source_draft_id.split(":")
        if len(parts) < 4 or parts[0] != _SOP_SOURCE_PREFIX:
            return None
        return parts[-1]

    @staticmethod
    def _is_sop_managed_task(task: Task) -> bool:
        """Return whether one task was generated by the SOP engine."""

        return bool(
            task.source_draft_id and task.source_draft_id.startswith(f"{_SOP_SOURCE_PREFIX}:")
        )
