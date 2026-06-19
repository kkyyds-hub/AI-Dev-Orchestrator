import {
  Briefcase,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  FileText,
  FolderOpen,
} from "lucide-react";
import { useState } from "react";
import type * as React from "react";

import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  ReadbackRows,
  Separator,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
} from "./ui";
import { mainPageMockContents, type MainPageContent } from "../mockInteractions";

const projectScopeRows = [
  ["项目目标", "构建营销数据分析平台，支持多维度洞察与增长决策"],
  ["当前边界", "聚焦接入、指标体系、可视化分析、报表导出"],
  ["关键约束", "数据合规、敏捷交付、上线时间"],
  ["交付标准", "功能可用、性能达标、文档完整、验收通过"],
] as const;

function CompactPageHeader({
  eyebrow,
  title,
  meta,
  description,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  meta?: React.ReactNode;
  description?: React.ReactNode;
}) {
  return (
    <section className="shrink-0 border-b border-[#2A2A2A] pb-4">
      {eyebrow ? (
        <div className="mb-1 text-xs font-medium leading-5 text-[#8A8A8A]">
          {eyebrow}
        </div>
      ) : null}
      <div className="flex flex-col gap-1.5 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
        <h1 className="text-2xl font-semibold leading-tight tracking-normal text-white md:text-[26px]">
          {title}
        </h1>
        {meta ? (
          <div className="text-xs leading-5 text-[#8A8A8A] sm:pb-0.5 sm:text-sm">
            {meta}
          </div>
        ) : null}
      </div>
      {description ? (
        <p className="mt-1.5 max-w-3xl text-sm leading-5 text-[#C7C7C7]">
          {description}
        </p>
      ) : null}
    </section>
  );
}

type ExecutionRunStatus = "idle" | "running" | "completed" | "blocked" | "failed";

type ExecutionStepState = "done" | "current" | "pending" | "blocked" | "failed";

type ExecutionStepViewModel = {
  id: string;
  title: string;
  detail: string;
  state: ExecutionStepState;
  rows: readonly (readonly [string, string])[];
  logs?: readonly string[];
  footer: string;
};

type ExecutionEvidenceTabViewModel = {
  key: string;
  label: string;
  title: string;
  description: string;
  rows: readonly (readonly [string, string])[];
  footer: string;
};

type ExecutionQueueItemViewModel = {
  id: string;
  state: "manual_required" | "queued" | "blocked" | "done";
  state_label: string;
  title: string;
  note: string;
  description: string;
  rows: readonly (readonly [string, string])[];
  footer: string;
  can_add_to_workbench: boolean;
};

type ExecutionRunViewModel = {
  id: string;
  title: string;
  status: ExecutionRunStatus;
  status_label: string;
  executor_label: string;
  worker_label: string;
  environment_label: string;
  budget_label: string;
  git_write_status: "disabled" | "preview_only";
  started_at: string;
  updated_at: string;
  current_summary: string;
  safety_note: string;
  status_rows: readonly (readonly [string, string])[];
  steps: readonly ExecutionStepViewModel[];
  evidence_tabs: readonly ExecutionEvidenceTabViewModel[];
  queue_items: readonly ExecutionQueueItemViewModel[];
  backend_status: "mock" | "unavailable";
};

type ExecutionPageViewState =
  | "ready"
  | "idle"
  | "loading"
  | "completed"
  | "blocked"
  | "error"
  | "no_project"
  | "no_permission";

const executionRun: ExecutionRunViewModel = {
  id: "run_7F3A",
  title: "AI 正在处理：数据接入模块联调",
  status: "running",
  status_label: "running · mock",
  executor_label: "Codex",
  worker_label: "Worker 1/3",
  environment_label: "运行环境就绪",
  budget_label: "预算正常",
  git_write_status: "disabled",
  started_at: "11:32:41",
  updated_at: "11:34:40",
  current_summary: "正在校验数据源连通性，并生成接入任务拆分建议。",
  safety_note: "当前仅展示处理进度，不执行提交、推送或写入操作。",
  status_rows: [
    ["运行", "running · run_7F3A"],
    ["运行环境", "ready"],
    ["工作区", "clean"],
    ["Git", "只读预检 · 写入关闭"],
    ["审批", "无需审批"],
    ["质量闸门", "等待结果"],
    ["预算", "正常"],
  ],
  steps: [
    {
      id: "step_claimed",
      title: "已领取任务",
      detail: "11:32:41 · 已领取并确认",
      state: "done",
      rows: [
        ["步骤", "已领取任务"],
        ["执行器", "Worker 1 / 3"],
        ["领取时间", "11:32:41"],
        ["任务", "数据接入模块联调"],
        ["领取结果", "已领取并确认"],
        ["下一步", "建立执行上下文"],
      ],
      logs: [
        "11:32:41 Worker 1 领取任务",
        "11:32:41 校验任务状态为 running",
        "11:32:42 准备加载项目上下文",
      ],
      footer: "仅展示步骤读回，不触发执行操作 · mock",
    },
    {
      id: "step_context",
      title: "上下文已建立",
      detail: "11:32:43 · 项目信息与上下文已加载",
      state: "done",
      rows: [
        ["步骤", "上下文已建立"],
        ["建立时间", "11:32:43"],
        ["项目上下文", "已加载"],
        ["依赖状态", "无阻塞依赖"],
        ["记忆召回", "命中 3 条项目背景"],
        ["下一步", "进入执行处理"],
      ],
      logs: [
        "11:32:43 加载项目目标与任务边界",
        "11:32:45 读取最近运行摘要",
        "11:32:47 确认 ready_for_execution true",
      ],
      footer: "上下文内容来自当前项目 mock 数据，不代表真实后端响应。",
    },
    {
      id: "step_executing",
      title: "执行中",
      detail: "11:34:08 · 正在处理当前任务",
      state: "current",
      rows: [
        ["步骤", "执行中"],
        ["执行器", "Codex · Worker 1 / 3"],
        ["Run ID", "run_7F3A"],
        ["开始时间", "11:34:08"],
        ["当前动作", "校验数据源连通性并生成接入任务拆分建议"],
        ["下一步", "等待结果回写"],
        ["预计完成", "11:40 前"],
      ],
      logs: [
        "11:34:08 读取当前项目上下文",
        "11:34:19 校验数据源连接参数",
        "11:34:37 生成接入任务拆分建议",
      ],
      footer: "仅展示当前步骤读回，不触发执行操作 · mock",
    },
    {
      id: "step_writeback",
      title: "等待结果回写",
      detail: "预计 11:40 前完成",
      state: "pending",
      rows: [
        ["步骤", "等待结果回写"],
        ["预计完成", "11:40 前"],
        ["等待内容", "执行结果摘要与任务拆分建议"],
        ["后续动作", "进入审批 / 交付检查"],
        ["Git 状态", "写入关闭"],
        ["风险", "暂无阻塞项"],
      ],
      logs: [
        "等待 Worker 返回结果摘要",
        "等待质量闸门更新",
        "等待页面刷新执行读回",
      ],
      footer: "仅展示等待状态，不执行提交、推送或写入操作 · mock",
    },
  ],
  evidence_tabs: [
    {
      key: "run",
      label: "运行记录",
      title: "运行记录",
      description: "当前任务运行摘要 · mock",
      rows: [
        ["任务", "数据接入模块联调"],
        ["Run ID", "run_7F3A"],
        ["Worker", "Worker 1 / 3"],
        ["状态", "running"],
        ["开始时间", "11:32:41"],
        ["预计完成", "11:40 前"],
        ["模型", "Codex · gpt-5.5"],
        ["成本预估", "$0.012"],
        ["Token", "4.8k"],
        ["Log", "logs/runs/run_7F3A.log"],
      ],
      footer: "仅展示运行读回，不触发执行操作 · mock",
    },
    {
      key: "context",
      label: "上下文",
      title: "上下文",
      description: "执行前上下文摘要 · mock",
      rows: [
        ["项目", "营销活动分析平台"],
        ["当前任务输入", "校验数据源连通性并拆分接入任务"],
        ["依赖", "无阻塞依赖"],
        ["记忆召回", "命中 3 条项目背景"],
        ["验收口径", "接入路径明确、验证命令完整、风险说明清晰"],
        ["上下文状态", "ready_for_execution true"],
      ],
      footer: "上下文来自当前项目 mock 数据，不代表真实后端响应。",
    },
    {
      key: "decision",
      label: "决策",
      title: "决策",
      description: "为什么由当前执行器处理 · mock",
      rows: [
        ["路由结果", "选择 Codex"],
        ["原因", "当前任务偏代码与联调，适合代码执行器处理"],
        ["未选择 DeepSeek", "本轮不是规划总结任务"],
        ["执行模式", "只读运行"],
        ["验证模式", "mock verification"],
        ["下一步", "等待结果回写后进入审批 / 交付检查"],
      ],
      footer: "该回放只解释调度决策，不代表真实模型调用。",
    },
    {
      key: "safety",
      label: "安全",
      title: "安全",
      description: "运行前安全边界读回 · mock",
      rows: [
        ["Runtime", "ready"],
        ["Workspace", "clean"],
        ["Git", "只读预检 · 写入关闭"],
        ["Approval", "无需审批"],
        ["Quality gate", "等待结果"],
        ["Budget", "正常"],
        ["风险", "未发现阻塞项"],
      ],
      footer: "当前仅预览安全状态，不执行 git add / commit / push。",
    },
  ],
  queue_items: [
    {
      id: "queue_1",
      state: "manual_required",
      state_label: "待人工",
      title: "数据源账号确认",
      note: "需产品负责人确认",
      description: "后续安排详情 · mock",
      rows: [
        ["状态", "待人工"],
        ["队列位置", "1"],
        ["为什么排在后面", "当前执行任务完成后需要确认数据源账号"],
        ["依赖", "数据接入模块联调"],
        ["下一步处理者", "产品负责人"],
        ["处理方式", "回到工作台讨论后确认"],
        ["风险", "账号未确认会阻塞后续接入验证"],
      ],
      footer: "仅展示队列任务读回，不触发执行操作 · mock",
      can_add_to_workbench: true,
    },
    {
      id: "queue_2",
      state: "queued",
      state_label: "待执行",
      title: "指标口径确认",
      note: "等待前置事项",
      description: "后续安排详情 · mock",
      rows: [
        ["状态", "待执行"],
        ["队列位置", "2"],
        ["为什么排在后面", "需要等待数据源账号确认后进入指标口径校验"],
        ["依赖", "数据源账号确认"],
        ["下一步处理者", "AI 主管"],
        ["处理方式", "AI 评估后自动执行"],
        ["风险", "口径未确认会影响报表验收"],
      ],
      footer: "仅展示队列任务读回，不触发执行操作 · mock",
      can_add_to_workbench: false,
    },
    {
      id: "queue_3",
      state: "queued",
      state_label: "待执行",
      title: "可视化报表联调",
      note: "预计 2 个任务后进行",
      description: "后续安排详情 · mock",
      rows: [
        ["状态", "待执行"],
        ["队列位置", "3"],
        ["为什么排在后面", "需要等待指标口径确认后再联调报表"],
        ["依赖", "指标口径确认"],
        ["下一步处理者", "Codex"],
        ["处理方式", "预计 2 个任务后进行"],
        ["风险", "暂无阻塞项"],
      ],
      footer: "仅展示队列任务读回，不执行提交、推送或写入操作 · mock",
      can_add_to_workbench: false,
    },
  ],
  backend_status: "mock",
};

const executionPageViewState: ExecutionPageViewState = "ready";

type GovernanceSkillRecommendation = "retain" | "merge" | "observe" | "deprecate";

type GovernanceSkillViewModel = {
  id: string;
  skill_id: string;
  skill_code: string;
  skill_name: string;
  summary: string;
  purpose: string;
  bound_version: string;
  registry_current_version: string | null;
  registry_enabled: boolean;
  upgrade_available: boolean;
  applicable_role_codes: readonly string[];
  binding_source: "default_seed" | "manual" | "project_governance";
  owner_role_code: string;
  owner_role_name: string;
  run_count: number;
  succeeded_run_count: number;
  failed_run_count: number;
  total_tokens: number;
  estimated_cost: number;
  latest_run_id: string | null;
  latest_run_status: string | null;
  latest_run_summary: string | null;
  latest_used_at: string | null;
  recommendation: GovernanceSkillRecommendation;
  recommendation_label: string;
  recommendation_reason: string;
  evidence_rows: readonly (readonly [string, string])[];
  version_rows: readonly (readonly [string, string])[];
  suggestion_rows: readonly (readonly [string, string])[];
};

type GovernanceSkillPageViewState =
  | "ready"
  | "loading"
  | "empty"
  | "error"
  | "no_project"
  | "no_permission";

type GovernanceCatalogMode = "skills" | "roles" | "permissions";

type GovernanceScopeMode = "project" | "all";

type GovernanceRoleViewModel = {
  role_code: string;
  enabled: boolean;
  name: string;
  summary: string;
  responsibilities: readonly string[];
  input_boundary: readonly string[];
  output_boundary: readonly string[];
  default_skill_slots: readonly string[];
  custom_notes: string | null;
  sort_order: number;
};

type GovernanceRegistrySkill = {
  id: string;
  code: string;
  name: string;
  summary: string;
  purpose: string;
  applicable_role_codes: readonly string[];
  enabled: boolean;
  current_version: string;
  version_history: readonly {
    id: string;
    version: string;
    name: string;
    summary: string;
    purpose: string;
    applicable_role_codes: readonly string[];
    enabled: boolean;
    change_note: string | null;
    created_at: string;
  }[];
};

type GovernanceSystemRole = {
  code: string;
  name: string;
  summary: string;
  responsibilities: readonly string[];
  input_boundary: readonly string[];
  output_boundary: readonly string[];
  default_skill_slots: readonly string[];
  enabled_by_default: boolean;
  sort_order: number;
};

type GovernancePermissionPolicy = {
  id: "auto" | "request" | "forbidden";
  title: string;
  summary: string;
  reason: string;
  items: readonly string[];
};

const governanceSkills: readonly GovernanceSkillViewModel[] = [
  {
    id: "gs_001",
    skill_id: "skill_project_director_governance",
    skill_code: "project_director_governance",
    skill_name: "AI Project Director 指令治理",
    summary: "负责目标澄清、任务拆分、证据审查与回报，输出治理链路的核心规则与口径。",
    purpose: "为 AI 项目主管提供结构化指令模板，确保目标澄清、任务拆分、证据审查与回报流程标准化。",
    bound_version: "v20260607",
    registry_current_version: "v20260607",
    registry_enabled: true,
    upgrade_available: false,
    applicable_role_codes: ["product_manager"],
    binding_source: "default_seed",
    owner_role_code: "product_manager",
    owner_role_name: "AI 项目主管",
    run_count: 128,
    succeeded_run_count: 121,
    failed_run_count: 7,
    total_tokens: 482600,
    estimated_cost: 12.36,
    latest_run_id: "run_7F3A",
    latest_run_status: "running",
    latest_run_summary: "正在校验数据源连通性并生成接入任务拆分建议。",
    latest_used_at: "2h 前",
    recommendation: "retain",
    recommendation_label: "建议保留",
    recommendation_reason: "该 Skill 持续参与目标澄清、任务拆分与审查回报，是治理链路的核心规则来源。运行成功率 94.5%，近期使用频率稳定。",
    evidence_rows: [
      ["最近运行次数", "128"],
      ["成功次数", "121"],
      ["失败次数", "7"],
      ["总 Token", "482,600"],
      ["预估成本", "$12.36"],
      ["最近 Run", "run_7F3A"],
      ["最近 Run 状态", "running"],
      ["最近摘要", "正在校验数据源连通性并生成接入任务拆分建议。"],
    ],
    version_rows: [
      ["当前绑定版本", "v20260607"],
      ["注册表版本", "v20260607"],
      ["是否启用", "是"],
      ["是否有升级", "否"],
      ["绑定来源", "默认映射"],
      ["版本记录", "v20260607 · v20260601 · v20260525"],
    ],
    suggestion_rows: [
      ["建议", "保留"],
      ["理由", "该 Skill 持续参与目标澄清、任务拆分与审查回报，是治理链路的核心规则来源。"],
      ["影响范围", "AI 项目主管角色 · 所有关联任务"],
      ["建议动作", "保持当前版本绑定，无需调整"],
      ["是否需要用户确认", "否"],
    ],
  },
  {
    id: "gs_002",
    skill_id: "skill_task_instruction_gen",
    skill_code: "task_instruction_generation",
    skill_name: "任务指令生成",
    summary: "与 AI Project Director 指令治理在职责上高度重叠，建议合并减少重复维护。",
    purpose: "根据项目目标和阶段计划，自动生成结构化任务指令供执行器消费。",
    bound_version: "v20260611",
    registry_current_version: "v20260611",
    registry_enabled: true,
    upgrade_available: false,
    applicable_role_codes: ["product_manager", "architect"],
    binding_source: "manual",
    owner_role_code: "product_manager",
    owner_role_name: "指令生成 Agent",
    run_count: 46,
    succeeded_run_count: 39,
    failed_run_count: 7,
    total_tokens: 124800,
    estimated_cost: 3.42,
    latest_run_id: "run_6E2B",
    latest_run_status: "completed",
    latest_run_summary: "已生成数据接入阶段 4 项子任务指令。",
    latest_used_at: "1d 前",
    recommendation: "merge",
    recommendation_label: "建议合并",
    recommendation_reason: "与 AI Project Director 指令治理在目标澄清与任务拆分职责上高度重叠。合并后可减少维护成本，避免指令冲突。",
    evidence_rows: [
      ["最近运行次数", "46"],
      ["成功次数", "39"],
      ["失败次数", "7"],
      ["总 Token", "124,800"],
      ["预估成本", "$3.42"],
      ["最近 Run", "run_6E2B"],
      ["最近 Run 状态", "completed"],
      ["最近摘要", "已生成数据接入阶段 4 项子任务指令。"],
    ],
    version_rows: [
      ["当前绑定版本", "v20260611"],
      ["注册表版本", "v20260611"],
      ["是否启用", "是"],
      ["是否有升级", "否"],
      ["绑定来源", "手动绑定"],
      ["版本记录", "v20260611 · v20260601"],
    ],
    suggestion_rows: [
      ["建议", "合并"],
      ["理由", "与 AI Project Director 指令治理在目标澄清与任务拆分职责上高度重叠，合并可减少维护成本。"],
      ["影响范围", "指令生成 Agent · AI 项目主管角色"],
      ["建议动作", "将本 Skill 的独有字段合并至 AI Project Director 指令治理，然后淘汰本 Skill"],
      ["是否需要用户确认", "是"],
    ],
  },
  {
    id: "gs_003",
    skill_id: "skill_frontend_production_verify",
    skill_code: "frontend_production_verification",
    skill_name: "前端生产化验收",
    summary: "覆盖范围明确，但近期使用较少，建议持续观察其对验收质量的实际贡献。",
    purpose: "对前端页面进行生产化验收检查，包括构建验证、组件一致性与状态兜底覆盖。",
    bound_version: "v20260610",
    registry_current_version: "v20260612",
    registry_enabled: true,
    upgrade_available: true,
    applicable_role_codes: ["reviewer"],
    binding_source: "project_governance",
    owner_role_code: "reviewer",
    owner_role_name: "前端体验 Agent",
    run_count: 18,
    succeeded_run_count: 16,
    failed_run_count: 2,
    total_tokens: 53200,
    estimated_cost: 1.48,
    latest_run_id: "run_5D1C",
    latest_run_status: "completed",
    latest_run_summary: "执行中心页面状态兜底验收通过，7 个状态分支均覆盖。",
    latest_used_at: "3d 前",
    recommendation: "observe",
    recommendation_label: "观察",
    recommendation_reason: "覆盖范围明确，但近 7 天使用频率下降。建议观察其在下一阶段验收中的实际贡献后再决定保留或淘汰。",
    evidence_rows: [
      ["最近运行次数", "18"],
      ["成功次数", "16"],
      ["失败次数", "2"],
      ["总 Token", "53,200"],
      ["预估成本", "$1.48"],
      ["最近 Run", "run_5D1C"],
      ["最近 Run 状态", "completed"],
      ["最近摘要", "执行中心页面状态兜底验收通过，7 个状态分支均覆盖。"],
    ],
    version_rows: [
      ["当前绑定版本", "v20260610"],
      ["注册表版本", "v20260612"],
      ["是否启用", "是"],
      ["是否有升级", "是"],
      ["绑定来源", "项目治理"],
      ["版本记录", "v20260612 · v20260610 · v20260605"],
    ],
    suggestion_rows: [
      ["建议", "观察"],
      ["理由", "覆盖范围明确，但近 7 天使用频率下降，需观察下一阶段验收中的实际贡献。"],
      ["影响范围", "前端体验 Agent · 验收流程"],
      ["建议动作", "暂不升级，观察下一轮验收结果后再决定"],
      ["是否需要用户确认", "否"],
    ],
  },
  {
    id: "gs_004",
    skill_id: "skill_legacy_plan_gen",
    skill_code: "legacy_plan_generation",
    skill_name: "旧版计划生成",
    summary: "已被新版计划生成 Skill 全面替代，近 30 天无实际使用，建议淘汰。",
    purpose: "根据项目目标生成阶段计划草案，已被新版计划生成 Skill 替代。",
    bound_version: "v20260521",
    registry_current_version: null,
    registry_enabled: false,
    upgrade_available: false,
    applicable_role_codes: ["product_manager"],
    binding_source: "default_seed",
    owner_role_code: "product_manager",
    owner_role_name: "计划生成 Agent",
    run_count: 0,
    succeeded_run_count: 0,
    failed_run_count: 0,
    total_tokens: 0,
    estimated_cost: 0,
    latest_run_id: null,
    latest_run_status: null,
    latest_run_summary: null,
    latest_used_at: "32d 前",
    recommendation: "deprecate",
    recommendation_label: "建议淘汰",
    recommendation_reason: "已被新版计划生成 Skill 全面替代，近 30 天无实际使用。注册表已禁用，绑定版本已过期。",
    evidence_rows: [
      ["最近运行次数", "0"],
      ["成功次数", "0"],
      ["失败次数", "0"],
      ["总 Token", "0"],
      ["预估成本", "$0.00"],
      ["最近 Run", "—"],
      ["最近 Run 状态", "—"],
      ["最近摘要", "近 30 天无运行记录。"],
    ],
    version_rows: [
      ["当前绑定版本", "v20260521"],
      ["注册表版本", "已下线"],
      ["是否启用", "否"],
      ["是否有升级", "否"],
      ["绑定来源", "默认映射"],
      ["版本记录", "v20260521"],
    ],
    suggestion_rows: [
      ["建议", "淘汰"],
      ["理由", "已被新版计划生成 Skill 全面替代，近 30 天无实际使用，注册表已禁用。"],
      ["影响范围", "计划生成 Agent · 历史遗留绑定"],
      ["建议动作", "移除绑定，归档版本记录"],
      ["是否需要用户确认", "是"],
    ],
  },
];

const governanceRegistrySkills: readonly GovernanceRegistrySkill[] = [
  {
    id: "registry_skill_task_instruction",
    code: "task_instruction_generation",
    name: "任务指令生成",
    summary: "根据项目目标和阶段计划生成结构化任务指令。",
    purpose: "将已确认的项目范围、阶段目标和验收口径整理为可执行的任务说明，供后续角色分工使用。",
    applicable_role_codes: ["ai_project_director", "product_manager"],
    enabled: true,
    current_version: "v20260611",
    version_history: [
      {
        id: "task_instruction_v20260611",
        version: "v20260611",
        name: "任务指令生成",
        summary: "补充阶段计划与验收口径字段。",
        purpose: "生成结构化任务指令。",
        applicable_role_codes: ["ai_project_director", "product_manager"],
        enabled: true,
        change_note: "强化阶段计划与验收边界表达。",
        created_at: "2026-06-11",
      },
      {
        id: "task_instruction_v20260601",
        version: "v20260601",
        name: "任务指令生成",
        summary: "初始任务指令模板。",
        purpose: "生成任务拆分说明。",
        applicable_role_codes: ["ai_project_director"],
        enabled: true,
        change_note: "建立基础模板。",
        created_at: "2026-06-01",
      },
    ],
  },
  {
    id: "registry_skill_code_review",
    code: "code_review",
    name: "代码审查",
    summary: "检查实现变更、风险点和交付边界。",
    purpose: "对代码改动进行结构、行为和风险审查，输出可执行的修正建议。",
    applicable_role_codes: ["reviewer", "engineer"],
    enabled: true,
    current_version: "v20260610",
    version_history: [
      {
        id: "code_review_v20260610",
        version: "v20260610",
        name: "代码审查",
        summary: "增加结构边界和回归风险检查。",
        purpose: "审查代码变更质量。",
        applicable_role_codes: ["reviewer", "engineer"],
        enabled: true,
        change_note: "补充结构边界检查。",
        created_at: "2026-06-10",
      },
      {
        id: "code_review_v20260530",
        version: "v20260530",
        name: "代码审查",
        summary: "基础审查清单。",
        purpose: "审查实现风险。",
        applicable_role_codes: ["reviewer"],
        enabled: true,
        change_note: "建立审查基线。",
        created_at: "2026-05-30",
      },
    ],
  },
  {
    id: "registry_skill_acceptance_check",
    code: "acceptance_check",
    name: "验收检查",
    summary: "核对交付内容、验证证据和遗留风险。",
    purpose: "对阶段交付进行事实核对，确认验收项、缺失证据和后续处理边界。",
    applicable_role_codes: ["reviewer", "ai_project_director"],
    enabled: true,
    current_version: "v20260612",
    version_history: [
      {
        id: "acceptance_check_v20260612",
        version: "v20260612",
        name: "验收检查",
        summary: "补充缺证识别与遗留项收口。",
        purpose: "完成阶段验收核对。",
        applicable_role_codes: ["reviewer", "ai_project_director"],
        enabled: true,
        change_note: "强化缺失证据识别。",
        created_at: "2026-06-12",
      },
      {
        id: "acceptance_check_v20260604",
        version: "v20260604",
        name: "验收检查",
        summary: "基础验收检查模板。",
        purpose: "核对交付与验证结果。",
        applicable_role_codes: ["reviewer"],
        enabled: true,
        change_note: "建立验收检查模板。",
        created_at: "2026-06-04",
      },
    ],
  },
  {
    id: "registry_skill_docs_closure",
    code: "docs_closure",
    name: "文档收口",
    summary: "整理交付说明、决策记录和阶段结论。",
    purpose: "把执行结果、关键决策和验收结论整理为稳定文档素材。",
    applicable_role_codes: ["product_manager", "reviewer"],
    enabled: false,
    current_version: "v20260605",
    version_history: [
      {
        id: "docs_closure_v20260605",
        version: "v20260605",
        name: "文档收口",
        summary: "增加阶段结论整理字段。",
        purpose: "整理交付文档素材。",
        applicable_role_codes: ["product_manager", "reviewer"],
        enabled: false,
        change_note: "暂不默认启用，保留为文档收口候选。",
        created_at: "2026-06-05",
      },
      {
        id: "docs_closure_v20260528",
        version: "v20260528",
        name: "文档收口",
        summary: "基础文档整理模板。",
        purpose: "整理执行摘要。",
        applicable_role_codes: ["product_manager"],
        enabled: false,
        change_note: "建立文档整理基线。",
        created_at: "2026-05-28",
      },
    ],
  },
];

const governanceSkillViewState: GovernanceSkillPageViewState = "ready";

const governanceRoles: readonly GovernanceRoleViewModel[] = [
  {
    role_code: "ai_project_director",
    enabled: true,
    name: "AI 项目主管",
    summary: "负责澄清目标、拆分任务、推进计划",
    responsibilities: [
      "把二手交易平台 MVP 的目标、范围和约束整理成可执行计划",
      "拆分阶段任务，并判断哪些问题需要先回到用户确认",
      "协调不同角色的输入与输出，保持交付边界清晰",
    ],
    input_boundary: [
      "用户提出的项目目标、约束、优先级和补充说明",
      "已有项目范围、阶段计划、验收口径和治理意见",
      "其他角色提交的方案摘要、风险说明和待确认事项",
    ],
    output_boundary: [
      "项目目标澄清结果和阶段推进建议",
      "面向执行的任务拆分、职责分派和下一步说明",
      "需要用户决策的问题清单与交付边界提醒",
    ],
    default_skill_slots: ["目标澄清", "任务拆分", "治理意见整理"],
    custom_notes: "默认作为项目协调角色出现，强调计划推进和边界收口。",
    sort_order: 10,
  },
  {
    role_code: "product_manager",
    enabled: true,
    name: "产品经理",
    summary: "负责需求范围、优先级与验收标准",
    responsibilities: [
      "定义商品发布、搜索、聊天和订单闭环的 MVP 范围",
      "整理用户路径、功能优先级和第一期不做的内容",
      "把需求转成普通用户能理解的验收标准",
    ],
    input_boundary: [
      "业务目标、目标用户、核心场景和约束条件",
      "用户反馈、需求疑问和阶段性取舍建议",
      "技术实现反馈中需要产品决策的事项",
    ],
    output_boundary: [
      "需求范围说明和优先级判断",
      "功能验收标准、边界说明和待确认问题",
      "交付前需要确认的产品风险与取舍建议",
    ],
    default_skill_slots: ["需求澄清", "优先级判断", "验收标准整理"],
    custom_notes: "默认聚焦普通用户体验和 MVP 范围，不承担技术实现细节。",
    sort_order: 20,
  },
  {
    role_code: "engineer",
    enabled: true,
    name: "工程师",
    summary: "负责实现、联调和变更说明",
    responsibilities: [
      "根据已确认的任务边界完成前后端实现方案拆解",
      "说明关键实现路径、依赖关系和联调注意事项",
      "交付变更说明，并标出需要验证的功能点",
    ],
    input_boundary: [
      "已确认的需求范围、任务拆分和验收标准",
      "产品经理或 AI 项目主管给出的边界约束",
      "评审者反馈的风险点和需要修正的问题",
    ],
    output_boundary: [
      "实现方案、变更说明和联调建议",
      "需要补充确认的技术问题和风险说明",
      "交付给评审者检查的实现摘要",
    ],
    default_skill_slots: ["实现拆解", "联调说明", "变更总结"],
    custom_notes: "默认只描述实现职责定义，不展示具体执行过程。",
    sort_order: 30,
  },
  {
    role_code: "reviewer",
    enabled: true,
    name: "评审者",
    summary: "负责审查风险、质量和交付边界",
    responsibilities: [
      "检查需求、实现和验收口径是否一致",
      "识别交付风险、遗漏项和需要补证的地方",
      "给出是否可以继续推进的审查建议",
    ],
    input_boundary: [
      "产品范围、实现摘要、变更说明和验收标准",
      "AI 项目主管整理的阶段目标与交付边界",
      "工程师提交的风险说明和待确认事项",
    ],
    output_boundary: [
      "审查结论、风险说明和改进建议",
      "缺失证据或边界不清的问题清单",
      "面向下一步推进的验收建议",
    ],
    default_skill_slots: ["风险审查", "质量检查", "验收建议"],
    custom_notes: "默认关注质量与边界，不替代产品决策或工程实现。",
    sort_order: 40,
  },
];

const governanceSystemRoles: readonly GovernanceSystemRole[] = [
  {
    code: "ai_project_director",
    name: "AI 项目主管",
    summary: "负责目标澄清、计划推进和治理边界收口",
    responsibilities: [
      "整理项目目标、范围、约束和阶段推进路径",
      "拆分任务并协调角色之间的输入与输出",
      "识别需要授权或补证的事项，维护治理边界",
    ],
    input_boundary: [
      "项目目标、约束、优先级和补充说明",
      "阶段计划、验收口径和治理意见",
      "其他角色提交的方案摘要和风险说明",
    ],
    output_boundary: [
      "项目目标澄清结果和阶段推进建议",
      "任务拆分、职责分派和下一步说明",
      "需要授权或补证的问题清单",
    ],
    default_skill_slots: ["目标澄清", "任务拆分", "治理意见整理"],
    enabled_by_default: true,
    sort_order: 10,
  },
  {
    code: "product_manager",
    name: "产品经理",
    summary: "负责需求范围、优先级和验收标准",
    responsibilities: [
      "定义产品范围、用户路径和阶段目标",
      "判断功能优先级和第一期不做的内容",
      "维护验收标准和产品侧风险说明",
    ],
    input_boundary: [
      "业务目标、目标用户和核心场景",
      "用户反馈、需求疑问和取舍建议",
      "实现反馈中需要产品决策的事项",
    ],
    output_boundary: [
      "需求范围说明和优先级判断",
      "功能验收标准、边界说明和待确认问题",
      "交付前需要确认的产品风险",
    ],
    default_skill_slots: ["需求澄清", "优先级判断", "验收标准整理"],
    enabled_by_default: true,
    sort_order: 20,
  },
  {
    code: "engineer",
    name: "工程师",
    summary: "负责实现拆解、联调说明和变更总结",
    responsibilities: [
      "根据任务边界完成实现方案拆解",
      "说明关键实现路径、依赖关系和联调注意事项",
      "交付变更说明，并标出需要验证的功能点",
    ],
    input_boundary: [
      "已确认的需求范围、任务拆分和验收标准",
      "产品经理或 AI 项目主管给出的边界约束",
      "评审者反馈的风险点和修正要求",
    ],
    output_boundary: [
      "实现方案、变更说明和联调建议",
      "需要补充确认的技术问题和风险说明",
      "交付给评审者检查的实现摘要",
    ],
    default_skill_slots: ["实现拆解", "联调说明", "变更总结"],
    enabled_by_default: true,
    sort_order: 30,
  },
  {
    code: "reviewer",
    name: "评审者",
    summary: "负责质量审查、风险识别和验收建议",
    responsibilities: [
      "检查需求、实现和验收口径是否一致",
      "识别交付风险、遗漏项和缺失证据",
      "给出是否可以继续推进的审查建议",
    ],
    input_boundary: [
      "产品范围、实现摘要、变更说明和验收标准",
      "阶段目标、交付边界和验证结果",
      "工程师提交的风险说明和待确认事项",
    ],
    output_boundary: [
      "审查结论、风险说明和改进建议",
      "缺失证据或边界不清的问题清单",
      "面向下一步推进的验收建议",
    ],
    default_skill_slots: ["风险审查", "质量检查", "验收建议"],
    enabled_by_default: true,
    sort_order: 40,
  },
];

const governancePermissionPolicies: readonly GovernancePermissionPolicy[] = [
  {
    id: "auto",
    title: "自动处理",
    summary: "低风险操作，可由系统自动完成。",
    items: ["任务调度", "运行状态读取", "交付物摘要生成", "成本数据读取"],
    reason: "这些操作主要涉及读取、整理和低风险调度，不直接改变关键资产。",
  },
  {
    id: "request",
    title: "需要申请权限",
    summary: "会影响项目计划、阶段或资产配置，执行前需要授权。",
    items: ["生成作战计划", "调整任务优先级", "角色 / Skill 沉淀建议", "项目阶段推进", "变更确认"],
    reason: "这些操作会改变项目推进路径或资产配置，需要保留人工授权边界。",
  },
  {
    id: "forbidden",
    title: "禁止自动处理",
    summary: "不可逆或高风险操作，系统不得自动执行。",
    items: [
      "生成本地提交",
      "推送远程仓库",
      "发布生产",
      "删除项目",
      "删除交付物",
      "覆盖 Provider Key",
      "删除运行证据",
      "永久删除稳定 Skill / 角色模板",
    ],
    reason: "这些操作具有不可逆影响或高风险边界，不能由系统自动完成。",
  },
];

function govShort(value: string | null | undefined, max = 40): string {
  if (!value) return "—";
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

type DeliverableStatus = "draft" | "pending_review" | "locked" | "archived" | "needs_more_evidence";

type DeliverableType =
  | "plan_draft"
  | "task_split"
  | "review_report"
  | "run_summary"
  | "verification_evidence"
  | "code_change_summary"
  | "delivery_doc";

type DeliverableViewModel = {
  id: string;
  project_id: string;
  title: string;
  type: DeliverableType;
  type_label: string;
  status: DeliverableStatus;
  status_label: string;
  stage: string;
  stage_label: string;
  version_no: number;
  total_versions: number;
  latest_version: boolean;
  summary: string;
  content_markdown: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  source_task_id?: string;
  source_run_id?: string;
  source_label: string;
  evidence_refs: string[];
  git_write_status: "disabled" | "preview_only";
  backend_status: "mock" | "unavailable";
  can_be_acceptance_evidence: boolean;
};

type DeliverablesDemoState = "ready" | "empty" | "loading" | "error" | "no_project";

const deliverablesItems: readonly DeliverableViewModel[] = [
  {
    id: "deliv_001",
    project_id: "proj_marketing_analytics",
    title: "项目规划草案 v1",
    type: "plan_draft",
    type_label: "规划草案",
    status: "locked",
    status_label: "已锁定",
    stage: "goal_clarification",
    stage_label: "目标澄清阶段",
    version_no: 1,
    total_versions: 1,
    latest_version: true,
    summary: "明确本阶段目标、范围与交付边界，建议先完成数据接入与指标口径确认，再进入报表联调。",
    content_markdown: `本成果明确了营销活动分析平台在当前阶段的目标、范围与交付边界。

- 目标：建立可复用的活动数据分析全链路
- 范围：数据接入、指标口径、报表联调、验收交付
- 边界：本阶段不进行复杂模型建设
- 建议：先完成数据源与指标口径确认，再进入报表联调

当前内容仅为 mock，不连接真实后端。`,
    created_by: "AI 主管",
    created_at: "今天 09:58",
    updated_at: "今天 09:58",
    source_task_id: "task_001",
    source_run_id: "run_7F39",
    source_label: "AI 主管 · 规划生成",
    evidence_refs: ["project-scope.md", "delivery-criteria.md"],
    git_write_status: "disabled",
    backend_status: "mock",
    can_be_acceptance_evidence: true,
  },
  {
    id: "deliv_002",
    project_id: "proj_marketing_analytics",
    title: "数据接入任务拆分",
    type: "task_split",
    type_label: "任务拆分",
    status: "pending_review",
    status_label: "待审查",
    stage: "data_ingestion",
    stage_label: "数据接入阶段",
    version_no: 1,
    total_versions: 1,
    latest_version: true,
    summary: "将数据接入拆分为源账号确认、连通性校验、字段映射和验收记录四个子任务，并标出依赖顺序。",
    content_markdown: `本成果将数据接入阶段拆分为四个子任务：

1. 源账号确认 — 需人工确认数据源账号权限
2. 连通性校验 — 验证数据源可访问性
3. 字段映射 — 确认字段对应关系
4. 验收记录 — 生成接入验证报告

依赖顺序：1 → 2 → 3 → 4，其中步骤 1 需人工介入。

当前内容仅为 mock，不连接真实后端。`,
    created_by: "AI 主管",
    created_at: "今天 10:22",
    updated_at: "今天 10:22",
    source_task_id: "task_002",
    source_run_id: "run_7F3A",
    source_label: "AI 主管 · 任务拆分",
    evidence_refs: ["data-ingestion-plan.md"],
    git_write_status: "disabled",
    backend_status: "mock",
    can_be_acceptance_evidence: false,
  },
  {
    id: "deliv_003",
    project_id: "proj_marketing_analytics",
    title: "当前运行摘要",
    type: "run_summary",
    type_label: "运行摘要",
    status: "draft",
    status_label: "草稿",
    stage: "execution",
    stage_label: "执行阶段",
    version_no: 1,
    total_versions: 1,
    latest_version: true,
    summary: "当前执行聚焦数据源连通性校验，已完成上下文建立，下一步等待结果回写与补充验证证据。",
    content_markdown: `本成果记录当前运行的执行摘要：

- 执行焦点：数据源连通性校验
- 已完成：上下文建立、任务领取
- 进行中：AI 正在处理当前任务
- 下一步：等待结果回写与补充验证证据

运行环境处于只读安全边界内，未触发 Git 写入。

当前内容仅为 mock，不连接真实后端。`,
    created_by: "AI 主管",
    created_at: "今天 11:16",
    updated_at: "今天 11:16",
    source_task_id: "task_003",
    source_run_id: "run_7F2E",
    source_label: "AI 主管 · 运行摘要",
    evidence_refs: ["execution-log.txt"],
    git_write_status: "disabled",
    backend_status: "mock",
    can_be_acceptance_evidence: false,
  },
];

function cleanMockMarkdown(content: string): string {
  return content
    .split("\n")
    .filter((line) => !line.includes("当前内容仅为 mock，不连接真实后端。"))
    .join("\n")
    .trim();
}

function formatDeliverableGitStatus(status: DeliverableViewModel["git_write_status"]): string {
  if (status === "disabled") return "未产生代码变更";
  return "待确认变更";
}

function formatDeliverableDataStatus(status: DeliverableViewModel["backend_status"]): string {
  if (status === "mock") return "示例数据";
  return "暂不可用";
}

type RepositoryLinkedDeliverable = {
  id: string;
  title: string;
  type_label: string;
  summary: string;
  linked_files: string[];
  can_be_acceptance_evidence: boolean;
};

type RepositoryBoundaryItem = {
  id: string;
  title: string;
  summary: string;
  items: string[];
  reason: string;
};

type RepositoryPageViewState = "ready" | "loading" | "empty" | "error" | "no_project" | "no_permission";

const repositoryLinkedDeliverables: readonly RepositoryLinkedDeliverable[] = [
  {
    id: "repo_deliv_plan",
    title: "规划草案",
    type_label: "规划草案",
    summary: "明确当前阶段目标、范围与交付边界。",
    linked_files: ["WorkbenchMockPages.tsx", "mockInteractions.ts"],
    can_be_acceptance_evidence: true,
  },
  {
    id: "repo_deliv_task_split",
    title: "数据接入任务拆分",
    type_label: "任务拆分",
    summary: "将数据接入拆分为账号确认、连通性校验、字段映射和验收记录。",
    linked_files: ["WorkbenchMockPages.tsx"],
    can_be_acceptance_evidence: false,
  },
  {
    id: "repo_deliv_run_summary",
    title: "当前运行摘要",
    type_label: "运行摘要",
    summary: "记录当前处理焦点、已完成事项和后续补充验证方向。",
    linked_files: ["SanshengLiubuUiLabPage.tsx", "WorkbenchMockPages.tsx"],
    can_be_acceptance_evidence: false,
  },
];

const repositoryBoundaryItems: readonly RepositoryBoundaryItem[] = [
  {
    id: "repo_boundary_view",
    title: "可查看",
    summary: "目录结构、变更草稿、关联成果、只读预览。",
    items: ["查看文件结构", "查看变更草稿", "查看关联成果", "查看写入边界"],
    reason: "这些内容用于理解当前项目代码空间，不改变代码或交付物。",
  },
  {
    id: "repo_boundary_confirm",
    title: "需要确认",
    summary: "影响代码或交付物的变更，需要人工确认。",
    items: ["确认变更草稿", "接受代码修改建议", "生成正式变更说明", "关联成果到变更记录"],
    reason: "这些动作会影响项目交付记录或后续修改路径，需要保留确认边界。",
  },
  {
    id: "repo_boundary_forbidden",
    title: "禁止自动处理",
    summary: "不可逆或高风险操作不得自动执行。",
    items: ["自动提交代码", "自动推送远程仓库", "自动合并分支", "自动发布生产", "覆盖密钥或删除证据"],
    reason: "这些动作具有不可逆影响或涉及关键资产，不能自动完成。",
  },
];

const projectContextDialogContent = {
  task: {
    title: "任务上下文",
    description: "展示当前项目最近任务与阻塞情况 · mock",
    metrics: [
      ["任务总数", "28"],
      ["当前阶段任务", "6"],
      ["阻塞任务", "1"],
    ],
    sections: [
      {
        title: "最近任务",
        rows: [
          ["拆分数据接入模块任务", "进行中", "32 分钟前"],
          ["指标口径确认", "待处理", "3 小时前"],
          ["可视化报表联调", "待开始", "1 天前"],
        ],
      },
      {
        title: "阻塞提示",
        rows: [["等待数据源账号确认"]],
      },
    ],
  },
  timeline: {
    title: "最近运行与时间线",
    description: "展示最近项目事件、运行与阶段动作 · mock",
    sections: [
      {
        title: "最近事件",
        rows: [
          ["数据源连通性测试完成", "run", "1 小时前"],
          ["阶段推进到任务拆分", "stage", "2 小时前"],
          ["生成指标口径草案", "deliverable", "4 小时前"],
          ["发起报表验收审批", "approval", "1 天前"],
        ],
      },
    ],
  },
  repository: {
    title: "仓库上下文",
    description: "展示当前项目绑定仓库与变更会话 · mock",
    sections: [
      {
        title: "仓库",
        rows: [
          ["仓库", "dev/marketing-analytics"],
          ["默认分支", "main"],
          ["当前分支", "feature/marketing-report"],
          ["访问模式", "read_only"],
          ["扫描状态", "completed"],
          ["文件数", "128"],
          ["目录数", "18"],
        ],
      },
      {
        title: "变更会话",
        rows: [
          ["guard", "clean"],
          ["dirty files", "0"],
          ["闭环状态", "进行中"],
        ],
      },
    ],
  },
  approval: {
    title: "审批与交付物",
    description: "展示待审批项、交付物与放行检查 · mock",
    sections: [
      {
        title: "审批",
        rows: [
          ["待审批", "1"],
          ["已完成", "2"],
          ["逾期", "0"],
        ],
      },
      {
        title: "交付物",
        rows: [
          ["指标口径说明 v1", "pending_review"],
          ["报表联调记录 v1", "draft"],
        ],
      },
      {
        title: "放行检查",
        rows: [
          ["release gate", "pending_approval"],
          ["blocked", "false"],
          ["missing items", "0"],
        ],
      },
    ],
  },
} as const;

type ProjectContextDialogKey = keyof typeof projectContextDialogContent;

type ProjectStageState = "done" | "current" | "pending" | "blocked";

type ProjectStageViewModel = {
  id: string;
  label: string;
  status_label: string;
  state: ProjectStageState;
  summary: string;
  meta: string;
};

type ProjectContextItemViewModel = {
  id: string;
  label: string;
  value: string;
  meta: string;
  dialogKey: ProjectContextDialogKey;
};

type ProjectOverviewViewModel = {
  id: string;
  name: string;
  status: "active" | "pending" | "blocked" | "archived";
  status_label: string;
  current_stage: string;
  updated_at: string;
  summary: string;
  recommendation: string;
  scope_rows: readonly (readonly [string, string])[];
  stages: readonly ProjectStageViewModel[];
  context_items: readonly ProjectContextItemViewModel[];
  task_total: number;
  task_done: number;
  task_running: number;
  manual_pending: number;
  backend_status: "mock" | "unavailable";
};

type ProjectPageViewState = "ready" | "loading" | "empty" | "error" | "no_project" | "no_permission";

const projectOverview: ProjectOverviewViewModel = {
  id: "proj_marketing_analytics",
  name: "营销活动分析平台",
  status: "active",
  status_label: "进行中",
  current_stage: "任务拆分",
  updated_at: "2025-05-22 14:32",
  summary: "项目整体进度顺利，已完成目标澄清并梳理核心需求，正在进行任务拆分与优先级排序。",
  recommendation: "建议聚焦数据接入与指标体系搭建的核心路径，优先完成关键链路以尽早验证价值。",
  scope_rows: projectScopeRows,
  stages: [
    { id: "stage_1", label: "目标澄清", status_label: "已完成", state: "done", summary: "已确认目标、边界与交付标准。", meta: "已完成" },
    { id: "stage_2", label: "任务拆分", status_label: "进行中", state: "current", summary: "正在拆分数据接入与指标口径任务。", meta: "待人工 1 项" },
    { id: "stage_3", label: "执行规划", status_label: "待开始", state: "pending", summary: "等待任务拆分完成后生成执行顺序。", meta: "待开始" },
    { id: "stage_4", label: "交付验收", status_label: "待开始", state: "pending", summary: "执行完成后汇总交付物与验收证据。", meta: "待开始" },
  ],
  context_items: [
    { id: "ctx_task", label: "最近任务", value: "拆分数据接入模块任务", meta: "32 分钟前", dialogKey: "task" },
    { id: "ctx_timeline", label: "最近操作", value: "数据源连通性测试", meta: "1 小时前", dialogKey: "timeline" },
    { id: "ctx_repo", label: "仓库绑定", value: "dev/marketing-analytics", meta: "已绑定", dialogKey: "repository" },
    { id: "ctx_approval", label: "审批 / 交付物", value: "待审批 1 项 / 交付物 0 项", meta: "待处理", dialogKey: "approval" },
  ],
  task_total: 28,
  task_done: 6,
  task_running: 2,
  manual_pending: 1,
  backend_status: "mock",
};

function ProjectSectionTitle({
  icon: Icon,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 text-base font-semibold text-white">
      <Icon className="h-[18px] w-[18px] text-[#C7C7C7]" />
      <span>{children}</span>
    </div>
  );
}

function ProjectContextDialog({
  dialogKey,
  children,
}: {
  dialogKey: ProjectContextDialogKey;
  children: React.ReactNode;
}) {
  const content = projectContextDialogContent[dialogKey];

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,540px)]">
        <DialogHeader>
          <DialogTitle>{content.title}</DialogTitle>
          <DialogDescription>{content.description}</DialogDescription>
        </DialogHeader>

        {"metrics" in content ? (
          <div className="mt-5 grid gap-2 sm:grid-cols-3">
            {content.metrics.map(([label, value]) => (
              <div key={label} className="rounded-lg border border-[#2A2A2A] bg-[#171717] px-3 py-3">
                <div className="text-xs text-[#8A8A8A]">{label}</div>
                <div className="mt-1 text-lg font-semibold text-white">{value}</div>
              </div>
            ))}
          </div>
        ) : null}

        <div className="mt-5 space-y-5">
          {content.sections.map((section, sectionIndex) => (
            <div key={section.title}>
              {sectionIndex > 0 ? <Separator className="mb-5" /> : null}
              <div className="mb-2 text-sm font-semibold text-white">{section.title}</div>
              <div className="border-y border-[#2A2A2A]">
                {section.rows.map((row) => (
                  <div
                    key={row.join("-")}
                    className="grid gap-2 border-b border-[#1F1F1F] px-3 py-2.5 text-sm last:border-b-0 sm:grid-cols-[1fr_112px_96px]"
                  >
                    <span className="text-[#C7C7C7]">{row[0]}</span>
                    <span className="text-[#8A8A8A]">{row[1] ?? ""}</span>
                    <span className="text-[#8A8A8A] sm:text-right">{row[2] ?? ""}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-5 flex justify-end">
          <DialogClose asChild>
            <Button variant="secondary" size="sm">关闭</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ProjectManagementMockPage() {
  const [discussion, setDiscussion] = useState("");
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [openStageIndex, setOpenStageIndex] = useState<number | null>(null);

  const projectPageViewState = "ready" as ProjectPageViewState;
  const ov = projectOverview;
  const projectDiscussionDisabled = projectPageViewState !== "ready";

  const projectDiscussionHint =
    projectPageViewState === "ready"
      ? "记录后，AI 主管将在工作台新会话中反馈 · mock"
      : projectPageViewState === "loading"
        ? "正在读取项目上下文，暂不可记录 · mock"
        : projectPageViewState === "error"
          ? "读取失败，暂不可记录 · mock"
          : projectPageViewState === "no_permission"
            ? "暂无权限，暂不可记录 · mock"
            : "请选择或创建项目后再记录 · mock";

  function handleRecordFeedback() {
    if (projectDiscussionDisabled || !discussion.trim()) return;
    setDiscussion("");
    setFeedbackMessage("已记录讨论点 · 将在工作台新会话反馈 · mock");
  }

  const openStage = openStageIndex === null ? null : ov.stages[openStageIndex];

  if (projectPageViewState === "loading") {
    return (
      <div className="ui-lab-project-page min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
        <div className="mx-auto flex w-full max-w-[980px] flex-col">
          <div className="text-sm text-[#8A8A8A]">正在读取项目上下文 · mock</div>
          <Separator className="mt-4" />
          <div className="mt-4 h-4 w-3/4 rounded bg-[#1A1A1A]" />
          <Separator className="mt-4" />
          <div className="mt-4 h-3 w-1/2 rounded bg-[#1A1A1A]" />
        </div>
      </div>
    );
  }

  if (projectPageViewState === "empty") {
    return (
      <div className="ui-lab-project-page min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
        <div className="mx-auto flex w-full max-w-[980px] flex-col py-8">
          <div className="text-sm text-[#8A8A8A]">暂无项目</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">
            创建项目后，AI 主管会在这里沉淀目标、范围、阶段计划和上下文。
          </div>
        </div>
      </div>
    );
  }

  if (projectPageViewState === "error") {
    return (
      <div className="ui-lab-project-page min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
        <div className="mx-auto flex w-full max-w-[980px] flex-col py-8">
          <div className="text-sm text-[#8A8A8A]">项目上下文读取失败 · mock</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">
            当前为模拟错误，不接真实后端。请稍后重试或回到工作台确认项目状态。
          </div>
        </div>
      </div>
    );
  }

  if (projectPageViewState === "no_project") {
    return (
      <div className="ui-lab-project-page min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
        <div className="mx-auto flex w-full max-w-[980px] flex-col py-8">
          <div className="text-sm text-[#8A8A8A]">尚未选择项目</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">
            选择一个项目后，这里会展示项目范围、阶段计划和当前上下文。
          </div>
        </div>
      </div>
    );
  }

  if (projectPageViewState === "no_permission") {
    return (
      <div className="ui-lab-project-page min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
        <div className="mx-auto flex w-full max-w-[980px] flex-col py-8">
          <div className="text-sm text-[#8A8A8A]">暂无访问权限 · mock</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">
            你当前没有查看该项目上下文的权限。
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="ui-lab-project-page min-h-0 flex-1 overflow-y-auto px-6 py-6 md:px-10">
      <div className="mx-auto flex w-full max-w-[980px] flex-col">
        <CompactPageHeader
          eyebrow="当前项目上下文"
          title={ov.name}
          meta={`${ov.status_label} · 当前阶段：${ov.current_stage} · ${ov.updated_at}`}
          description={`构建统一的营销数据分析平台，整合多渠道数据，提供可视化洞察与增长决策支持。任务 ${ov.task_total} 项 · 已完成 ${ov.task_done} · 执行中 ${ov.task_running} · 待人工 ${ov.manual_pending}`}
        />

        <section className="mt-5 border-y border-[#2A2A2A] py-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <FileText className="h-4 w-4 text-[#C7C7C7]" />
            <span>摘要</span>
          </div>
          <div className="mt-4 space-y-2 text-sm leading-6 text-[#C7C7C7]">
            <p>{ov.summary}</p>
            <p>{ov.recommendation}</p>
          </div>
        </section>

        <section className="mt-6">
          <ProjectSectionTitle icon={FolderOpen}>项目范围</ProjectSectionTitle>
          <div className="mt-3 border-y border-[#2A2A2A]">
            {ov.scope_rows.map(([label, value]) => (
              <div
                key={label}
                className="grid gap-2 border-b border-[#1F1F1F] px-3 py-2.5 text-sm last:border-b-0 md:grid-cols-[180px_1fr]"
              >
                <div className="text-[#8A8A8A]">{label}</div>
                <div className="text-[#C7C7C7]">{value}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-6">
          <ProjectSectionTitle icon={Clock3}>阶段计划</ProjectSectionTitle>

          <div className="mt-5 hidden lg:grid lg:grid-cols-4 lg:items-start">
            {ov.stages.map((stage, index) => (
              <div key={stage.id} className="relative flex min-w-0 flex-col items-center text-center">
                {index > 0 ? (
                  <span className="absolute left-0 top-3 h-px w-1/2 bg-[#3A3A3A]" />
                ) : null}
                {index < ov.stages.length - 1 ? (
                  <span className="absolute right-0 top-3 h-px w-1/2 bg-[#3A3A3A]" />
                ) : null}
                <button
                  className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-[#111111] focus-visible:bg-[#111111] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/10 active:scale-[0.98]"
                  onClick={() => setOpenStageIndex((current) => (current === index ? null : index))}
                  aria-label={`查看${stage.label}阶段进展`}
                  aria-pressed={openStageIndex === index}
                >
                  <span
                    className={[
                      "relative flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold",
                      stage.state === "done"
                        ? "border-[#3A3A3A] bg-[#2C2C2C] text-white"
                        : stage.state === "current"
                          ? "border-white bg-black text-white"
                          : "border-[#2A2A2A] bg-[#171717] text-[#8A8A8A]",
                    ].join(" ")}
                  >
                    {stage.state === "current" ? (
                      <span className="absolute inset-[-4px] rounded-full border border-white/20 animate-pulse" />
                    ) : null}
                    <span className="relative z-10">
                      {stage.state === "done" ? <Check className="h-4 w-4" /> : index + 1}
                    </span>
                  </span>
                </button>
                <div className="mt-3 w-full px-1 text-sm font-medium text-[#C7C7C7]">{stage.label}</div>
                <div className="mt-1 text-xs text-[#8A8A8A]">{stage.status_label}</div>
              </div>
            ))}
          </div>

          <div className="mt-4 lg:hidden">
            {ov.stages.map((stage, index) => (
              <button
                key={stage.id}
                type="button"
                onClick={() => setOpenStageIndex((current) => (current === index ? null : index))}
                className="flex w-full items-center gap-3 border-b border-[#1F1F1F] py-3 text-left transition-colors last:border-b-0 hover:bg-[#111111] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/10"
              >
                <span
                  className={[
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                    stage.state === "done"
                      ? "border-[#3A3A3A] bg-[#2C2C2C] text-white"
                      : stage.state === "current"
                        ? "border-white bg-black text-white"
                        : "border-[#2A2A2A] bg-[#171717] text-[#8A8A8A]",
                  ].join(" ")}
                >
                  {stage.state === "done" ? <Check className="h-4 w-4" /> : index + 1}
                </span>
                <span className="flex-1 text-sm font-medium text-[#C7C7C7]">{stage.label}</span>
                <span className="text-xs text-[#8A8A8A]">{stage.status_label}</span>
                <ChevronRight className="h-4 w-4 text-[#5F5F5F]" />
              </button>
            ))}
          </div>

          {openStage ? (
            <div className="mt-4 rounded-lg border border-[#2A2A2A] bg-[#171717]/80 px-4 py-3">
              <div className="text-sm font-medium text-white">{openStage.label} · {openStage.status_label}</div>
              <p className="mt-1 text-xs leading-5 text-[#C7C7C7]">{openStage.summary}</p>
              <div className="mt-2 text-xs text-[#8A8A8A]">状态：{openStage.meta}</div>
            </div>
          ) : null}
        </section>

        <section className="mt-6">
          <ProjectSectionTitle icon={Briefcase}>当前上下文</ProjectSectionTitle>
          <div className="mt-3 border-y border-[#2A2A2A]">
            {ov.context_items.map((item) => (
              <ProjectContextDialog key={item.id} dialogKey={item.dialogKey}>
                <button
                  className="grid w-full items-center gap-2 border-b border-[#1F1F1F] px-3 py-2.5 text-left text-sm transition-colors last:border-b-0 hover:bg-[#111111] focus-visible:bg-[#111111] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/10 md:grid-cols-[170px_1fr_112px_16px]"
                >
                  <span className="text-[#8A8A8A]">{item.label}</span>
                  <span className="min-w-0 truncate text-[#C7C7C7]">{item.value}</span>
                  <span className="text-left text-[#8A8A8A] md:text-right">{item.meta}</span>
                  <ChevronRight className="hidden h-4 w-4 text-[#5F5F5F] md:block" />
                </button>
              </ProjectContextDialog>
            ))}
          </div>
        </section>

        <div className="mt-4">
          <div className="flex h-11 items-center gap-2 rounded-[18px] border border-[#2A2A2A] bg-[#171717] px-4">
            <Textarea
              value={discussion}
              disabled={projectDiscussionDisabled}
              onChange={(event) => {
                setDiscussion(event.target.value);
                if (feedbackMessage) setFeedbackMessage("");
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleRecordFeedback();
                }
              }}
              placeholder="记录审批疑问或改进点，AI 主管将在工作台新会话中反馈..."
              className="h-8 min-h-0 flex-1 resize-none border-0 bg-transparent py-1 text-sm leading-6 text-white outline-none placeholder:text-[#8A8A8A]"
            />
            <Button
              variant="secondary"
              size="sm"
              disabled={projectDiscussionDisabled || !discussion.trim()}
              onClick={handleRecordFeedback}
              className="h-8 shrink-0 rounded-full px-3"
            >
              记录
            </Button>
          </div>
          {feedbackMessage ? (
            <div className="mt-2 text-xs text-[#8A8A8A]">{feedbackMessage}</div>
          ) : null}
          <div className="mt-2 text-xs text-[#5F5F5F]">
            {projectDiscussionHint}
          </div>
        </div>
      </div>
    </div>
  );
}

function ExecutionCenterMockPage({
  onQueueDiscussionAction,
}: {
  onQueueDiscussionAction?: (mode: "add" | "add-and-open", title: string) => void;
}) {
  const [activeEvidenceTab, setActiveEvidenceTab] = useState("status");
  const [queueDiscussionMessage, setQueueDiscussionMessage] = useState("");

  const viewState = executionPageViewState;
  const run = executionRun;
  const displayTitle = run.title.replace(/^AI 正在处理：/, "");
  const detailEvidenceTabs = ["context", "decision", "safety", "run"]
    .map((key) => run.evidence_tabs.find((item) => item.key === key))
    .filter((item): item is ExecutionEvidenceTabViewModel => Boolean(item));

  if (viewState === "idle") {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
        <div className="mx-auto flex w-full max-w-[1080px] flex-col py-8">
          <div className="text-sm text-[#8A8A8A]">暂无正在处理的任务</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">当前项目没有活跃处理事项。启动任务后，这里会展示处理进展、等待事项和后续安排。</div>
        </div>
      </div>
    );
  }

  if (viewState === "loading") {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
        <div className="mx-auto flex w-full max-w-[1080px] flex-col">
          <div className="text-sm text-[#8A8A8A]">正在读取处理状态 · mock</div>
          <Separator className="mt-4" />
          <div className="mt-4 h-4 w-3/4 rounded bg-[#1A1A1A]" />
          <Separator className="mt-4" />
          <div className="mt-4 h-3 w-1/2 rounded bg-[#1A1A1A]" />
        </div>
      </div>
    );
  }

  if (viewState === "completed") {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
        <div className="mx-auto flex w-full max-w-[1080px] flex-col py-8">
          <div className="text-sm text-[#8A8A8A]">当前处理已完成 · mock</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">执行结果已沉淀到成果中心，可继续查看交付证据。</div>
        </div>
      </div>
    );
  }

  if (viewState === "blocked") {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
        <div className="mx-auto flex w-full max-w-[1080px] flex-col py-8">
          <div className="text-sm text-[#8A8A8A]">处理被阻塞 · mock</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">当前任务需要人工补充信息后才能继续。</div>
        </div>
      </div>
    );
  }

  if (viewState === "error") {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
        <div className="mx-auto flex w-full max-w-[1080px] flex-col py-8">
          <div className="text-sm text-[#8A8A8A]">处理状态读取失败 · mock</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">当前为模拟错误，不接真实后端。请稍后重试或回到工作台确认项目状态。</div>
        </div>
      </div>
    );
  }

  if (viewState === "no_project") {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
        <div className="mx-auto flex w-full max-w-[1080px] flex-col py-8">
          <div className="text-sm text-[#8A8A8A]">尚未选择项目</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">选择项目后，这里会展示该项目的处理进展、等待事项和后续安排。</div>
        </div>
      </div>
    );
  }

  if (viewState === "no_permission") {
    return (
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
        <div className="mx-auto flex w-full max-w-[1080px] flex-col py-8">
          <div className="text-sm text-[#8A8A8A]">暂无访问权限 · mock</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">你当前没有查看该项目执行状态的权限。</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6 md:px-10">
      <div className="mx-auto flex w-full max-w-[1080px] flex-col">
        <CompactPageHeader
          eyebrow="当前处理"
          title={displayTitle}
          meta={`进行中 · ${run.updated_at.slice(0, 5)}`}
          description={run.current_summary}
        />

        <section className="grid gap-8 border-b border-[#2A2A2A] py-5 lg:grid-cols-[1fr_1.15fr] lg:gap-10">
          <div>
            <h2 className="text-base font-semibold text-white">处理步骤</h2>
            <div className="mt-5 space-y-0">
              {run.steps.map((step, index) => {
                const isDone = step.state === "done";
                const isCurrent = step.state === "current";
                const isPending = step.state === "pending";

                const stepContent = (
                  <>
                    {index < run.steps.length - 1 ? (
                      <span className="absolute left-[13px] top-7 h-[calc(100%-28px)] w-px bg-[#3A3A3A]" />
                    ) : null}
                    <span
                      className={[
                        "relative z-10 flex h-7 w-7 items-center justify-center rounded-full border text-xs",
                        isDone
                          ? "border-[#3A3A3A] bg-[#2C2C2C] text-white"
                          : isCurrent
                            ? "border-[#C7C7C7] bg-black text-white"
                            : "border-[#3A3A3A] bg-black text-[#5F5F5F]",
                      ].join(" ")}
                    >
                      {isDone ? <Check className="h-4 w-4" /> : isCurrent ? (
                        <span className="h-2.5 w-2.5 rounded-full bg-white animate-pulse" />
                      ) : null}
                    </span>
                    <div>
                      <div className={isCurrent ? "text-sm font-semibold text-white" : "text-sm font-medium text-[#C7C7C7]"}>
                        {step.title}
                      </div>
                      <div className="mt-2 text-sm text-[#8A8A8A]">
                        {isPending ? "尚未发生 · " : ""}{step.detail}
                      </div>
                    </div>
                  </>
                );

                if (isPending) {
                  return (
                    <div
                      key={step.id}
                      className="relative grid grid-cols-[40px_1fr] items-start rounded-2xl pb-7 text-left last:pb-0"
                    >
                      {stepContent}
                    </div>
                  );
                }

                return (
                  <Dialog key={step.id}>
                    <DialogTrigger asChild>
                      <button
                        type="button"
                        className={[
                          "relative grid w-full grid-cols-[40px_1fr] items-start rounded-2xl pb-7 text-left last:pb-0 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20",
                          isDone
                            ? "cursor-pointer hover:bg-[#090909] active:scale-[0.995]"
                            : "cursor-pointer hover:bg-[#111111] active:scale-[0.99]",
                        ].join(" ")}
                      >
                        {stepContent}
                      </button>
                    </DialogTrigger>
                    <DialogContent className="w-[min(92vw,520px)]">
                      <DialogHeader>
                        <DialogTitle>{step.title}</DialogTitle>
                        <DialogDescription>{step.title}读回 · mock</DialogDescription>
                      </DialogHeader>
                      <ReadbackRows rows={step.rows} records={step.logs} footer={step.footer} />
                      <div className="mt-5 flex justify-end">
                        <DialogClose asChild>
                          <Button variant="secondary" size="sm">关闭</Button>
                        </DialogClose>
                      </div>
                    </DialogContent>
                  </Dialog>
                );
              })}
            </div>
          </div>

          <div className="border-t border-[#2A2A2A] pt-7 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-0">
            <h2 className="text-base font-semibold text-white">状态说明</h2>
            <div className="mt-4 space-y-2 text-sm leading-6 text-[#8A8A8A]">
              <p>{run.current_summary}</p>
              <p>{run.safety_note}</p>
            </div>

            <Dialog>
              <DialogTrigger asChild>
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-5 h-7 rounded-md border border-[#2A2A2A] bg-transparent px-2.5 text-xs text-[#C7C7C7] hover:bg-[#222222] hover:text-white active:scale-[0.98]"
                  onClick={() => setActiveEvidenceTab("status")}
                >
                  查看详情
                </Button>
              </DialogTrigger>
              <DialogContent className="w-[min(92vw,620px)]">
                <DialogHeader>
                  <DialogTitle>处理详情</DialogTitle>
                  <DialogDescription>仅展示详情，不触发执行操作。</DialogDescription>
                </DialogHeader>
                <Tabs value={activeEvidenceTab} onValueChange={setActiveEvidenceTab}>
                  <TabsList className="mt-4">
                    <TabsTrigger value="status">状态</TabsTrigger>
                    {detailEvidenceTabs.map((item) => (
                      <TabsTrigger key={item.key} value={item.key}>{item.label}</TabsTrigger>
                    ))}
                  </TabsList>
                  <TabsContent value="status">
                    <ReadbackRows rows={run.status_rows} footer="仅展示状态详情，不触发执行操作 · mock" />
                  </TabsContent>
                  {detailEvidenceTabs.map((item) => (
                    <TabsContent key={item.key} value={item.key}>
                      <ReadbackRows rows={item.rows} footer={item.footer} />
                    </TabsContent>
                  ))}
                </Tabs>
                <div className="mt-5 flex justify-end">
                  <DialogClose asChild>
                    <Button variant="secondary" size="sm">关闭</Button>
                  </DialogClose>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </section>

        <section className="pt-6">
          <h2 className="text-base font-semibold text-white">后续安排</h2>
          {queueDiscussionMessage ? (
            <div className="mt-2 text-xs text-[#8A8A8A]">{queueDiscussionMessage}</div>
          ) : null}
          <div className="mt-4 space-y-0">
            {run.queue_items.map((item) => (
              <Dialog key={item.id}>
                <DialogTrigger asChild>
                  <button
                    type="button"
                    className="flex w-full cursor-pointer items-start gap-3 border-b border-[#1F1F1F] px-1 py-3 text-left text-sm transition-colors last:border-b-0 hover:bg-[#0D0D0D] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 active:scale-[0.99]"
                  >
                    <span className="shrink-0 text-xs text-[#8A8A8A]">{item.state_label}</span>
                    <span className="min-w-0 flex-1">
                      <span className="text-[#C7C7C7]">{item.title}</span>
                      <span className="ml-2 text-xs text-[#8A8A8A]">{item.note}</span>
                    </span>
                  </button>
                </DialogTrigger>
                <DialogContent className="w-[min(92vw,520px)]">
                  <DialogHeader>
                    <DialogTitle>{item.title}</DialogTitle>
                    <DialogDescription>{item.description}</DialogDescription>
                  </DialogHeader>
                  <ReadbackRows rows={item.rows} footer={item.footer} />
                  <div className="mt-5 flex justify-end gap-3">
                    {item.can_add_to_workbench ? (
                      <div className="flex items-center gap-1">
                        <DialogClose asChild>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => {
                              setQueueDiscussionMessage(`已加入工作台讨论：@「${item.title}」 · mock`);
                              onQueueDiscussionAction?.("add", item.title);
                            }}
                          >
                            加入工作台讨论
                          </Button>
                        </DialogClose>

                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="secondary" size="sm" className="px-2" aria-label="更多讨论动作">
                              <ChevronDown className="h-3.5 w-3.5" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DialogClose asChild>
                              <DropdownMenuItem
                                onClick={() => {
                                  setQueueDiscussionMessage(`已加入并前往工作台讨论：@「${item.title}」 · mock`);
                                  onQueueDiscussionAction?.("add-and-open", item.title);
                                }}
                              >
                                加入并前往工作台 · mock
                              </DropdownMenuItem>
                            </DialogClose>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    ) : null}
                    <DialogClose asChild>
                      <Button variant="secondary" size="sm">关闭</Button>
                    </DialogClose>
                  </div>
                </DialogContent>
              </Dialog>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function GovernanceSkillMockPage() {
  const [catalogMode, setCatalogMode] = useState<GovernanceCatalogMode>("skills");
  const [scopeMode, setScopeMode] = useState<GovernanceScopeMode>("project");
  const [selectedSkillId, setSelectedSkillId] = useState<string>(governanceSkills[0]?.id ?? "");
  const [selectedRegistrySkillCode, setSelectedRegistrySkillCode] = useState<string>(governanceRegistrySkills[0]?.code ?? "");
  const [selectedRoleCode, setSelectedRoleCode] = useState<string>(governanceRoles[0]?.role_code ?? "");
  const [selectedSystemRoleCode, setSelectedSystemRoleCode] = useState<string>(governanceSystemRoles[0]?.code ?? "");
  const [selectedPermissionId, setSelectedPermissionId] = useState<GovernancePermissionPolicy["id"]>(
    governancePermissionPolicies[0]?.id ?? "auto",
  );
  const [activeTab, setActiveTab] = useState("overview");
  const [opinionText, setOpinionText] = useState("");
  const [skillOpinionMessages, setSkillOpinionMessages] = useState<readonly { author: "user" | "director"; text: string }[]>([
    { author: "user", text: "这个 Skill 是否可以和任务指令生成合并？" },
    { author: "director", text: "暂不建议直接合并。当前 Skill 还承担 Git 边界和审查口径，建议只吸收任务生成 Skill 的模板部分。" },
    { author: "user", text: "如果保留，它后续需要优化什么？" },
    { author: "director", text: "建议补充版本淘汰条件和最近运行证据阈值。" },
  ]);
  const [roleOpinionMessages, setRoleOpinionMessages] = useState<readonly { author: "user" | "director"; text: string }[]>([
    { author: "user", text: "这个角色的职责边界是否清楚？" },
    { author: "director", text: "职责边界已经按输入、输出和默认能力拆开，适合作为普通用户查看的角色定义。" },
  ]);
  const [permissionOpinionMessages, setPermissionOpinionMessages] = useState<readonly { author: "user" | "director"; text: string }[]>([
    { author: "user", text: "权限边界是否需要按项目阶段调整？" },
    { author: "director", text: "建议保持三类边界稳定，只在项目阶段变化时补充具体授权项。" },
  ]);

  const viewState = governanceSkillViewState;
  const selectedSkill = governanceSkills.find((s) => s.id === selectedSkillId) ?? governanceSkills[0] ?? null;
  const selectedRegistrySkill =
    governanceRegistrySkills.find((skill) => skill.code === selectedRegistrySkillCode) ?? governanceRegistrySkills[0] ?? null;
  const selectedRole = governanceRoles.find((role) => role.role_code === selectedRoleCode) ?? governanceRoles[0] ?? null;
  const selectedSystemRole =
    governanceSystemRoles.find((role) => role.code === selectedSystemRoleCode) ?? governanceSystemRoles[0] ?? null;
  const selectedPermission =
    governancePermissionPolicies.find((policy) => policy.id === selectedPermissionId) ?? governancePermissionPolicies[0] ?? null;
  const catalogLabel =
    catalogMode === "skills" ? "Skill 清单" : catalogMode === "roles" ? "角色清单" : "权限清单";
  const scopeLabel = scopeMode === "project" ? "当前项目" : "全部";
  const showScopeMenu = catalogMode === "skills" || catalogMode === "roles";
  const opinionMessages =
    catalogMode === "skills"
      ? skillOpinionMessages
      : catalogMode === "roles"
        ? roleOpinionMessages
        : permissionOpinionMessages;
  const selectedName =
    catalogMode === "skills"
      ? scopeMode === "project"
        ? selectedSkill?.skill_name
        : selectedRegistrySkill?.name
      : catalogMode === "roles"
        ? scopeMode === "project"
          ? selectedRole?.name
          : selectedSystemRole?.name
        : selectedPermission?.title;

  function handleScopeChange(nextScope: GovernanceScopeMode) {
    setScopeMode(nextScope);
    setOpinionText("");
    if (catalogMode === "skills") {
      if (nextScope === "project") {
        setSelectedSkillId(governanceSkills[0]?.id ?? "");
        setActiveTab("overview");
      } else {
        setSelectedRegistrySkillCode(governanceRegistrySkills[0]?.code ?? "");
      }
    }
    if (catalogMode === "roles") {
      if (nextScope === "project") {
        setSelectedRoleCode(governanceRoles[0]?.role_code ?? "");
      } else {
        setSelectedSystemRoleCode(governanceSystemRoles[0]?.code ?? "");
      }
    }
  }

  function handleSubmitOpinion() {
    if (!selectedName || !opinionText.trim()) return;
    const userMsg = { author: "user" as const, text: opinionText.trim() };
    const directorMsg = { author: "director" as const, text: `已记录对「${selectedName}」的治理意见，后续将作为清单维护参考 · mock` };
    if (catalogMode === "skills") {
      setSkillOpinionMessages((prev) => [...prev, userMsg, directorMsg]);
    } else if (catalogMode === "roles") {
      setRoleOpinionMessages((prev) => [...prev, userMsg, directorMsg]);
    } else {
      setPermissionOpinionMessages((prev) => [...prev, userMsg, directorMsg]);
    }
    setOpinionText("");
  }

  if (viewState === "loading") {
    return (
      <div className="min-h-0 flex-1 overflow-hidden px-4 py-6 md:px-6 md:py-8 lg:px-10">
        <div className="mx-auto flex min-h-0 w-full max-w-[1080px] flex-1 flex-col">
          <div className="text-xs font-medium tracking-[0.12em] text-[#8A8A8A]">Skill 治理 · 当前项目：营销活动分析平台 · mock</div>
          <div className="mt-4 text-sm text-[#8A8A8A]">正在读取 Skill 治理状态</div>
          <Separator className="mt-4" />
          <div className="mt-4 h-4 w-3/4 rounded bg-[#1A1A1A]" />
          <Separator className="mt-4" />
          <div className="mt-4 h-3 w-1/2 rounded bg-[#1A1A1A]" />
        </div>
      </div>
    );
  }

  if (viewState === "empty") {
    return (
      <div className="min-h-0 flex-1 overflow-hidden px-4 py-6 md:px-6 md:py-8 lg:px-10">
        <div className="mx-auto flex min-h-0 w-full max-w-[1080px] flex-1 flex-col">
          <div className="text-xs font-medium tracking-[0.12em] text-[#8A8A8A]">Skill 治理 · 当前项目：营销活动分析平台 · mock</div>
          <div className="mt-6 text-sm text-[#8A8A8A]">暂无 Skill 绑定</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">当前项目还没有可展示的 Skill 绑定记录。</div>
        </div>
      </div>
    );
  }

  if (viewState === "error") {
    return (
      <div className="min-h-0 flex-1 overflow-hidden px-4 py-6 md:px-6 md:py-8 lg:px-10">
        <div className="mx-auto flex min-h-0 w-full max-w-[1080px] flex-1 flex-col">
          <div className="text-xs font-medium tracking-[0.12em] text-[#8A8A8A]">Skill 治理 · 当前项目：营销活动分析平台 · mock</div>
          <div className="mt-6 text-sm text-[#8A8A8A]">Skill 治理状态读取失败</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">请稍后重试或回到工作台确认项目状态。</div>
        </div>
      </div>
    );
  }

  if (viewState === "no_project") {
    return (
      <div className="min-h-0 flex-1 overflow-hidden px-4 py-6 md:px-6 md:py-8 lg:px-10">
        <div className="mx-auto flex min-h-0 w-full max-w-[1080px] flex-1 flex-col">
          <div className="text-xs font-medium tracking-[0.12em] text-[#8A8A8A]">Skill 治理</div>
          <div className="mt-6 text-sm text-[#8A8A8A]">尚未选择项目</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">选择项目后，这里会展示该项目的 Skill 绑定、运行证据和治理建议。</div>
        </div>
      </div>
    );
  }

  if (viewState === "no_permission") {
    return (
      <div className="min-h-0 flex-1 overflow-hidden px-4 py-6 md:px-6 md:py-8 lg:px-10">
        <div className="mx-auto flex min-h-0 w-full max-w-[1080px] flex-1 flex-col">
          <div className="text-xs font-medium tracking-[0.12em] text-[#8A8A8A]">Skill 治理</div>
          <div className="mt-6 text-sm text-[#8A8A8A]">暂无访问权限</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">你当前没有查看该项目 Skill 治理状态的权限。</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-hidden px-4 py-5 md:px-6 md:py-6 lg:px-10">
      <div className="mx-auto flex h-full min-h-0 w-full max-w-[1080px] flex-col">
        <section className="grid h-full min-h-0 flex-1 gap-7 lg:grid-cols-[1fr_0.95fr] lg:gap-8">
          <div className="flex h-full min-h-0 flex-col">
            <div className="flex h-8 shrink-0 items-center justify-between gap-4">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    className="flex h-8 items-center gap-1.5 rounded-md px-1 text-base font-semibold text-white outline-none transition-colors hover:bg-[#111111] focus-visible:bg-[#111111] focus-visible:ring-2 focus-visible:ring-white/10"
                  >
                    {catalogLabel}
                    <ChevronDown className="h-4 w-4 text-[#8A8A8A]" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="min-w-36 rounded-lg">
                  <DropdownMenuItem
                    onSelect={() => {
                      setCatalogMode("skills");
                      setOpinionText("");
                    }}
                    className={catalogMode === "skills" ? "bg-[#2C2C2C]" : undefined}
                  >
                    Skill 清单
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={() => {
                      setCatalogMode("roles");
                      setOpinionText("");
                    }}
                    className={catalogMode === "roles" ? "bg-[#2C2C2C]" : undefined}
                  >
                    角色清单
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={() => {
                      setCatalogMode("permissions");
                      setOpinionText("");
                    }}
                    className={catalogMode === "permissions" ? "bg-[#2C2C2C]" : undefined}
                  >
                    权限清单
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {showScopeMenu ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      className="flex h-7 items-center gap-1 rounded-md px-1.5 text-xs font-medium text-[#C7C7C7] outline-none transition-colors hover:bg-[#111111] hover:text-white focus-visible:bg-[#111111] focus-visible:ring-2 focus-visible:ring-white/10"
                    >
                      {scopeLabel}
                      <ChevronDown className="h-3.5 w-3.5 text-[#8A8A8A]" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="min-w-28 rounded-lg">
                    <DropdownMenuItem
                      onSelect={() => handleScopeChange("project")}
                      className={scopeMode === "project" ? "bg-[#2C2C2C]" : undefined}
                    >
                      当前项目
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onSelect={() => handleScopeChange("all")}
                      className={scopeMode === "all" ? "bg-[#2C2C2C]" : undefined}
                    >
                      全部
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : null}
            </div>
            <div className="mt-4 min-h-0 flex-1 overflow-y-auto overscroll-contain border-y border-[#2A2A2A] [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
              {catalogMode === "skills"
                ? scopeMode === "project"
                  ? governanceSkills.map((skill) => (
                    <button
                      key={skill.id}
                      type="button"
                      onClick={() => {
                        setSelectedSkillId(skill.id);
                        setActiveTab("overview");
                      }}
                      className={[
                        "relative w-full border-b border-[#1F1F1F] px-1 py-3 text-left transition-colors last:border-b-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 active:scale-[0.995]",
                        selectedSkillId === skill.id
                          ? "before:absolute before:left-0 before:top-3 before:h-[calc(100%-24px)] before:w-px before:bg-[#8A8A8A] before:content-[''] bg-[#0A0A0A]"
                          : "hover:bg-[#080808]",
                      ].join(" ")}
                    >
                      <div className={selectedSkillId === skill.id ? "text-sm font-medium text-white" : "text-sm font-medium text-[#C7C7C7]"}>
                        {skill.skill_name}
                      </div>
                      <div className="mt-1 text-xs text-[#8A8A8A]">
                        {skill.recommendation_label} · {skill.owner_role_name} · {skill.bound_version}
                      </div>
                      <div className="mt-1 text-xs text-[#5F5F5F]">
                        最近运行 {skill.run_count} 次 · 最近使用 {skill.latest_used_at ?? "—"}
                      </div>
                    </button>
                  ))
                  : governanceRegistrySkills.map((skill) => (
                    <button
                      key={skill.code}
                      type="button"
                      onClick={() => setSelectedRegistrySkillCode(skill.code)}
                      className={[
                        "relative w-full border-b border-[#1F1F1F] px-1 py-3 text-left transition-colors last:border-b-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 active:scale-[0.995]",
                        selectedRegistrySkillCode === skill.code
                          ? "before:absolute before:left-0 before:top-3 before:h-[calc(100%-24px)] before:w-px before:bg-[#8A8A8A] before:content-[''] bg-[#0A0A0A]"
                          : "hover:bg-[#080808]",
                      ].join(" ")}
                    >
                      <div className={selectedRegistrySkillCode === skill.code ? "text-sm font-medium text-white" : "text-sm font-medium text-[#C7C7C7]"}>
                        {skill.name}
                      </div>
                      <div className="mt-1 text-xs leading-5 text-[#8A8A8A]">{skill.summary}</div>
                      <div className="mt-1 text-xs text-[#5F5F5F]">
                        {skill.enabled ? "已启用" : "未启用"} · {skill.current_version}
                      </div>
                    </button>
                  ))
                : catalogMode === "roles"
                  ? scopeMode === "project"
                    ? governanceRoles.map((role) => (
                    <button
                      key={role.role_code}
                      type="button"
                      onClick={() => setSelectedRoleCode(role.role_code)}
                      className={[
                        "relative w-full border-b border-[#1F1F1F] px-1 py-3 text-left transition-colors last:border-b-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 active:scale-[0.995]",
                        selectedRoleCode === role.role_code
                          ? "before:absolute before:left-0 before:top-3 before:h-[calc(100%-24px)] before:w-px before:bg-[#8A8A8A] before:content-[''] bg-[#0A0A0A]"
                          : "hover:bg-[#080808]",
                      ].join(" ")}
                    >
                      <div className={selectedRoleCode === role.role_code ? "text-sm font-medium text-white" : "text-sm font-medium text-[#C7C7C7]"}>
                        {role.name}
                      </div>
                      <div className="mt-1 text-xs leading-5 text-[#8A8A8A]">{role.summary}</div>
                      <div className="mt-1 text-xs text-[#5F5F5F]">{role.enabled ? "已启用" : "未启用"}</div>
                    </button>
                  ))
                    : governanceSystemRoles.map((role) => (
                    <button
                      key={role.code}
                      type="button"
                      onClick={() => setSelectedSystemRoleCode(role.code)}
                      className={[
                        "relative w-full border-b border-[#1F1F1F] px-1 py-3 text-left transition-colors last:border-b-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 active:scale-[0.995]",
                        selectedSystemRoleCode === role.code
                          ? "before:absolute before:left-0 before:top-3 before:h-[calc(100%-24px)] before:w-px before:bg-[#8A8A8A] before:content-[''] bg-[#0A0A0A]"
                          : "hover:bg-[#080808]",
                      ].join(" ")}
                    >
                      <div className={selectedSystemRoleCode === role.code ? "text-sm font-medium text-white" : "text-sm font-medium text-[#C7C7C7]"}>
                        {role.name}
                      </div>
                      <div className="mt-1 text-xs leading-5 text-[#8A8A8A]">{role.summary}</div>
                      <div className="mt-1 text-xs text-[#5F5F5F]">{role.enabled_by_default ? "默认启用" : "默认关闭"}</div>
                    </button>
                  ))
                  : governancePermissionPolicies.map((policy) => (
                    <button
                      key={policy.id}
                      type="button"
                      onClick={() => setSelectedPermissionId(policy.id)}
                      className={[
                        "relative w-full border-b border-[#1F1F1F] px-1 py-3 text-left transition-colors last:border-b-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 active:scale-[0.995]",
                        selectedPermissionId === policy.id
                          ? "before:absolute before:left-0 before:top-3 before:h-[calc(100%-24px)] before:w-px before:bg-[#8A8A8A] before:content-[''] bg-[#0A0A0A]"
                          : "hover:bg-[#080808]",
                      ].join(" ")}
                    >
                      <div className={selectedPermissionId === policy.id ? "text-sm font-medium text-white" : "text-sm font-medium text-[#C7C7C7]"}>
                        {policy.title}
                      </div>
                      <div className="mt-1 text-xs leading-5 text-[#8A8A8A]">{policy.summary}</div>
                    </button>
                  ))}
            </div>
          </div>

          <div className="grid h-full min-h-0 grid-rows-[minmax(0,1fr)_minmax(190px,0.62fr)] border-t border-[#2A2A2A] pt-6 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
            {catalogMode === "skills" ? (
              scopeMode === "project" ? (
                selectedSkill ? (
                <section className="flex min-h-0 flex-col overflow-hidden">
                  <div className="shrink-0">
                    <div className="text-base font-semibold text-white">{selectedSkill.skill_name}</div>
                    <div className="mt-1 text-xs text-[#8A8A8A]">
                      {selectedSkill.registry_enabled ? "已生效" : "未启用"} · {selectedSkill.owner_role_name} · {selectedSkill.bound_version}
                    </div>
                  </div>

                  <Tabs
                    value={activeTab}
                    onValueChange={setActiveTab}
                    className="mt-4 flex min-h-0 flex-1 flex-col overflow-hidden"
                  >
                    <TabsList className="shrink-0">
                      <TabsTrigger value="overview">概览</TabsTrigger>
                      <TabsTrigger value="evidence">证据</TabsTrigger>
                      <TabsTrigger value="suggestion">建议</TabsTrigger>
                    </TabsList>
                    <TabsContent value="overview" className="min-h-0 flex-1 overflow-hidden">
                      <div className="h-full min-h-0 overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                        <ReadbackRows
                          compact
                          rows={[
                            ["用途", govShort(selectedSkill.purpose, 48)],
                            ["适用角色", selectedSkill.applicable_role_codes.join(", ")],
                            ["绑定来源", selectedSkill.binding_source === "default_seed" ? "默认映射" : selectedSkill.binding_source === "manual" ? "手动绑定" : "项目治理"],
                            ["当前版本", selectedSkill.bound_version],
                            ["注册表状态", selectedSkill.registry_enabled ? `启用 · ${selectedSkill.registry_current_version ?? selectedSkill.bound_version}` : "已下线"],
                          ]}
                        />
                      </div>
                    </TabsContent>
                    <TabsContent value="evidence" className="min-h-0 flex-1 overflow-hidden">
                      <div className="h-full min-h-0 overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                        <ReadbackRows
                          compact
                          rows={[
                            ["最近运行", `${selectedSkill.run_count} 次`],
                            ["成功 / 失败", `${selectedSkill.succeeded_run_count} / ${selectedSkill.failed_run_count}`],
                            ["总 Token", selectedSkill.total_tokens.toLocaleString()],
                            ["预估成本", `$${selectedSkill.estimated_cost.toFixed(2)}`],
                            ["最近 Run", selectedSkill.latest_run_id ?? "—"],
                            ["最近摘要", govShort(selectedSkill.latest_run_summary, 36)],
                          ]}
                        />
                      </div>
                    </TabsContent>
                    <TabsContent value="suggestion" className="min-h-0 flex-1 overflow-hidden">
                      <div className="h-full min-h-0 overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                        <ReadbackRows
                          compact
                          rows={[
                            ["建议", selectedSkill.recommendation_label],
                            ["理由", govShort(selectedSkill.recommendation_reason, 48)],
                            ["影响范围", `${selectedSkill.owner_role_name} · 所有关联任务`],
                            ["建议动作", govShort(selectedSkill.suggestion_rows.find((r) => r[0] === "建议动作")?.[1], 40)],
                          ]}
                        />
                      </div>
                    </TabsContent>
                  </Tabs>
                </section>
              ) : (
                <div className="py-8">
                  <div className="text-sm text-[#8A8A8A]">请选择一个 Skill</div>
                </div>
              )
              ) : selectedRegistrySkill ? (
                <section className="flex min-h-0 flex-col overflow-hidden">
                  <div className="shrink-0">
                    <div className="text-base font-semibold text-white">{selectedRegistrySkill.name}</div>
                    <div className="mt-1 text-xs leading-5 text-[#8A8A8A]">{selectedRegistrySkill.summary}</div>
                  </div>

                  <div className="mt-4 min-h-0 flex-1 overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                    <ReadbackRows
                      compact
                      rows={[
                        ["用途", govShort(selectedRegistrySkill.purpose, 56)],
                        ["适用角色", selectedRegistrySkill.applicable_role_codes.join(", ")],
                        ["当前版本", selectedRegistrySkill.current_version],
                        ["启用状态", selectedRegistrySkill.enabled ? "已启用" : "未启用"],
                      ]}
                    />
                    <div className="mt-5">
                      <div className="text-sm font-semibold text-white">版本记录</div>
                      <div className="mt-2 border-y border-[#2A2A2A]">
                        {selectedRegistrySkill.version_history.map((version) => (
                          <div key={version.id} className="border-b border-[#1F1F1F] px-1 py-2 last:border-b-0">
                            <div className="text-sm font-medium text-[#C7C7C7]">{version.version} · {version.name}</div>
                            <div className="mt-1 text-xs leading-5 text-[#8A8A8A]">{version.summary}</div>
                            <div className="mt-1 text-xs text-[#5F5F5F]">
                              {version.enabled ? "已启用" : "未启用"} · {version.created_at}
                              {version.change_note ? ` · ${version.change_note}` : ""}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </section>
              ) : (
                <div className="py-8">
                  <div className="text-sm text-[#8A8A8A]">请选择一个 Skill</div>
                </div>
              )
            ) : catalogMode === "roles" ? (
              scopeMode === "project" ? (
                selectedRole ? (
                <section className="flex min-h-0 flex-col overflow-hidden">
                  <div className="shrink-0">
                    <div className="text-base font-semibold text-white">{selectedRole.name}</div>
                    <div className="mt-1 text-xs text-[#8A8A8A]">
                      {selectedRole.summary} · {selectedRole.enabled ? "已启用" : "未启用"}
                    </div>
                  </div>

                  <div className="mt-4 min-h-0 flex-1 overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                    <ReadbackRows
                      compact
                      rows={[
                        ["一句话说明", selectedRole.summary],
                        ["是否启用", selectedRole.enabled ? "已启用" : "未启用"],
                      ]}
                    />
                    {[
                      { title: "主要职责", items: selectedRole.responsibilities },
                      { title: "接收的信息", items: selectedRole.input_boundary },
                      { title: "输出结果", items: selectedRole.output_boundary },
                      { title: "默认能力", items: selectedRole.default_skill_slots },
                    ].map((section) => (
                      <div key={section.title} className="mt-5">
                        <div className="text-sm font-semibold text-white">{section.title}</div>
                        <div className="mt-2 border-y border-[#2A2A2A]">
                          {section.items.map((item) => (
                            <div key={item} className="border-b border-[#1F1F1F] px-1 py-2 text-sm leading-6 text-[#C7C7C7] last:border-b-0">
                              {item}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                    <div className="mt-5">
                      <div className="text-sm font-semibold text-white">补充说明</div>
                      <div className="mt-2 border-y border-[#2A2A2A] px-1 py-2 text-sm leading-6 text-[#C7C7C7]">
                        {selectedRole.custom_notes ?? "暂无补充说明"}
                      </div>
                    </div>
                  </div>
                </section>
              ) : (
                <div className="py-8">
                  <div className="text-sm text-[#8A8A8A]">请选择一个角色</div>
                </div>
              )
              ) : selectedSystemRole ? (
                <section className="flex min-h-0 flex-col overflow-hidden">
                  <div className="shrink-0">
                    <div className="text-base font-semibold text-white">{selectedSystemRole.name}</div>
                    <div className="mt-1 text-xs text-[#8A8A8A]">
                      {selectedSystemRole.summary} · {selectedSystemRole.enabled_by_default ? "默认启用" : "默认关闭"}
                    </div>
                  </div>

                  <div className="mt-4 min-h-0 flex-1 overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                    <ReadbackRows
                      compact
                      rows={[
                        ["一句话说明", selectedSystemRole.summary],
                        ["默认启用状态", selectedSystemRole.enabled_by_default ? "默认启用" : "默认关闭"],
                      ]}
                    />
                    {[
                      { title: "主要职责", items: selectedSystemRole.responsibilities },
                      { title: "接收的信息", items: selectedSystemRole.input_boundary },
                      { title: "输出结果", items: selectedSystemRole.output_boundary },
                      { title: "默认能力", items: selectedSystemRole.default_skill_slots },
                    ].map((section) => (
                      <div key={section.title} className="mt-5">
                        <div className="text-sm font-semibold text-white">{section.title}</div>
                        <div className="mt-2 border-y border-[#2A2A2A]">
                          {section.items.map((item) => (
                            <div key={item} className="border-b border-[#1F1F1F] px-1 py-2 text-sm leading-6 text-[#C7C7C7] last:border-b-0">
                              {item}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              ) : (
                <div className="py-8">
                  <div className="text-sm text-[#8A8A8A]">请选择一个角色</div>
                </div>
              )
            ) : selectedPermission ? (
              <section className="flex min-h-0 flex-col overflow-hidden">
                <div className="shrink-0">
                  <div className="text-base font-semibold text-white">{selectedPermission.title}</div>
                  <div className="mt-1 text-xs leading-5 text-[#8A8A8A]">{selectedPermission.summary}</div>
                </div>

                <div className="mt-4 min-h-0 flex-1 overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                  <div className="border-y border-[#2A2A2A]">
                    <div className="border-b border-[#1F1F1F] px-1 py-2 last:border-b-0">
                      <div className="text-xs font-semibold text-[#8A8A8A]">权限边界</div>
                      <div className="mt-1 text-sm leading-6 text-[#C7C7C7]">{selectedPermission.summary}</div>
                    </div>
                  </div>

                  <div className="mt-5">
                    <div className="text-sm font-semibold text-white">包含项</div>
                    <div className="mt-2 border-y border-[#2A2A2A]">
                      {selectedPermission.items.map((item) => (
                        <div key={item} className="border-b border-[#1F1F1F] px-1 py-2 text-sm leading-6 text-[#C7C7C7] last:border-b-0">
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-5">
                    <div className="text-sm font-semibold text-white">原因</div>
                    <div className="mt-2 border-y border-[#2A2A2A] px-1 py-2 text-sm leading-6 text-[#C7C7C7]">
                      {selectedPermission.reason}
                    </div>
                  </div>
                </div>
              </section>
            ) : (
              <div className="py-8">
                <div className="text-sm text-[#8A8A8A]">请选择一个权限类别</div>
              </div>
            )}

            <section className="mt-4 flex min-h-0 flex-col rounded-lg border border-[#2A2A2A] bg-[#0A0A0A]">
              <div className="shrink-0 px-3 pt-3 pb-2 text-xs font-semibold text-[#C7C7C7]">治理意见</div>
              <div className="min-h-0 flex-1 overflow-y-auto px-3 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                <div className="space-y-3 pb-2">
                  {opinionMessages.map((msg, i) => (
                    <div key={i} className="flex gap-2">
                      <div className={[
                        "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold",
                        msg.author === "user"
                          ? "bg-[#2C2C2C] text-white"
                          : "bg-[#1A1A1A] text-[#8A8A8A]",
                      ].join(" ")}>
                        {msg.author === "user" ? "K" : "AI"}
                      </div>
                      <div className="min-w-0 flex-1 text-xs leading-5 text-[#C7C7C7]">{msg.text}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="shrink-0 flex items-center gap-2 border-t border-[#1F1F1F] px-3 py-2">
                <Textarea
                  value={opinionText}
                  onChange={(e) => setOpinionText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmitOpinion();
                    }
                  }}
                  placeholder="补充治理意见..."
                  className="h-7 min-h-0 flex-1 resize-none border-0 bg-transparent py-0.5 text-xs leading-5 text-white outline-none placeholder:text-[#5F5F5F]"
                />
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!selectedName || !opinionText.trim()}
                  onClick={handleSubmitOpinion}
                  className="h-7 shrink-0 rounded-full px-2.5 text-xs"
                >
                  发送
                </Button>
              </div>
            </section>
          </div>
        </section>
      </div>
    </div>
  );
}

function DeliverablesCenterMockPage({
  onQueueDiscussionAction,
}: {
  onQueueDiscussionAction?: (mode: "add" | "add-and-open", title: string) => void;
}) {
  const [selectedId, setSelectedId] = useState<string>(deliverablesItems[0]?.id ?? "");
  const [activeDetailTab, setActiveDetailTab] = useState("content");
  const [discussionText, setDiscussionText] = useState("");
  const [discussionMessage, setDiscussionMessage] = useState("");
  const deliverablesViewState = "ready" as DeliverablesDemoState;

  const visibleDeliverables = deliverablesViewState === "ready" ? deliverablesItems : [];
  const selected = visibleDeliverables.find((d) => d.id === selectedId) ?? visibleDeliverables[0] ?? null;
  const hasDeliverables = visibleDeliverables.length > 0;

  const lockedCount = deliverablesItems.filter((d) => d.status === "locked").length;
  const pendingCount = deliverablesItems.filter((d) => d.status === "pending_review").length;
  const totalCount = deliverablesItems.length;

  const discussionDisabled = deliverablesViewState !== "ready" || !selected;

  function handleSelectDeliverable(id: string) {
    setSelectedId(id);
    setActiveDetailTab("content");
  }

  function handleDiscussionSubmit() {
    if (discussionDisabled || !selected || !discussionText.trim()) return;
    setDiscussionText("");
    setDiscussionMessage("已记录到工作台讨论");
    onQueueDiscussionAction?.("add", `成果讨论：${selected.title}`);
  }

  const discussionHint =
    deliverablesViewState === "ready"
      ? "发送后会加入工作台讨论。"
      : deliverablesViewState === "empty"
        ? "暂无成果可补充。"
        : deliverablesViewState === "loading"
          ? "正在读取成果，暂不可补充。"
          : deliverablesViewState === "error"
            ? "读取失败，暂不可补充。"
            : "请选择项目后再补充成果说明。";

  const evidenceRows: readonly (readonly [string, string])[] = selected
    ? [
        ["来源任务", selected.source_task_id ? "关联任务" : "暂无关联任务"],
        ["生成记录", selected.source_run_id ? "已记录" : "暂无记录"],
        ["生成来源", selected.source_label],
        ["关联材料", selected.evidence_refs.length ? selected.evidence_refs.join("、") : "暂无关联材料"],
        ["变更状态", formatDeliverableGitStatus(selected.git_write_status)],
        ["数据状态", formatDeliverableDataStatus(selected.backend_status)],
      ]
    : [];

  const versionRows: readonly (readonly [string, string])[] = selected
    ? [
        ["当前版本", `第 ${selected.version_no} 版`],
        ["版本数量", `${selected.total_versions} 个版本`],
        ["是否最新", selected.latest_version ? "是" : "否"],
        ["版本说明", "当前仅展示版本信息，不做内容对比"],
      ]
    : [];

  const summaryRows: readonly (readonly [string, string])[] = selected
    ? [
        ["状态", selected.status_label],
        ["类型", selected.type_label],
        ["阶段", selected.stage_label],
        ["创建者", selected.created_by],
        ["创建时间", selected.created_at],
        ["更新时间", selected.updated_at],
        ["可用于验收", selected.can_be_acceptance_evidence ? "是" : "否"],
      ]
    : [];

  return (
    <div className="flex min-h-0 flex-1 overflow-hidden px-4 py-5 md:px-6 md:py-6 lg:px-10">
      <style>{`
        .ui-lab-deliverables-scroll {
          scrollbar-width: none;
          -ms-overflow-style: none;
        }

        .ui-lab-deliverables-scroll::-webkit-scrollbar {
          display: none;
          width: 0;
          height: 0;
        }
      `}</style>
      <div className="mx-auto flex min-h-0 w-full max-w-[1080px] flex-1 flex-col">
        <CompactPageHeader
          eyebrow="营销活动分析平台"
          title="成果"
          meta={`已沉淀 ${totalCount} 项 · 待审查 ${pendingCount} 项 · 已锁定 ${lockedCount} 项`}
          description="项目成果、说明文档与验收材料"
        />

        <section className="grid min-h-0 flex-1 gap-7 border-b border-[#2A2A2A] py-5 lg:grid-cols-[1fr_1.2fr] lg:gap-8 lg:py-7">
          <div className="min-h-0 flex flex-col">
            <h2 className="text-base font-semibold text-white">近期沉淀</h2>
            <div className="ui-lab-deliverables-scroll mt-4 min-h-0 flex-1 overflow-y-auto pr-1 md:mt-5">
              {deliverablesViewState === "loading" ? (
                <div className="space-y-4 py-4">
                  <div className="text-sm text-[#8A8A8A]">正在读取当前项目成果</div>
                  <Separator />
                  <div className="h-4 w-3/4 rounded bg-[#1A1A1A]" />
                  <div className="h-3 w-1/2 rounded bg-[#1A1A1A]" />
                  <Separator />
                  <div className="h-4 w-2/3 rounded bg-[#1A1A1A]" />
                  <div className="h-3 w-2/5 rounded bg-[#1A1A1A]" />
                </div>
              ) : deliverablesViewState === "error" ? (
                <div className="py-8">
                  <div className="text-sm text-[#8A8A8A]">成果读取失败</div>
                  <div className="mt-2 text-xs text-[#5F5F5F]">请回到工作台确认项目状态。</div>
                </div>
              ) : deliverablesViewState === "no_project" ? (
                <div className="py-8">
                  <div className="text-sm text-[#8A8A8A]">尚未选择项目</div>
                  <div className="mt-2 text-xs text-[#5F5F5F]">选择一个项目后，这里会展示该项目沉淀下来的成果、证据和版本。</div>
                </div>
              ) : !hasDeliverables ? (
                <div className="py-8">
                  <div className="text-sm text-[#8A8A8A]">暂无沉淀成果</div>
                  <div className="mt-2 text-xs text-[#5F5F5F]">当前项目还没有可展示的成果。完成一次执行或审查后，AI 主管会在这里沉淀文档、摘要和证据。</div>
                </div>
              ) : (
                visibleDeliverables.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handleSelectDeliverable(item.id)}
                    className={[
                      "relative w-full border-b border-[#2A2A2A] py-3 pl-3 pr-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 active:scale-[0.995] md:py-4",
                      selectedId === item.id ? "before:absolute before:left-0 before:top-4 before:h-[calc(100%-32px)] before:w-px before:bg-[#8A8A8A] before:content-['']" : "hover:bg-[#080808]",
                    ].join(" ")}
                  >
                    <div className={selectedId === item.id ? "text-sm font-medium text-white" : "text-sm font-medium text-[#C7C7C7]"}>{item.title}</div>
                    <div className="mt-1 text-xs text-[#8A8A8A]">
                      {item.status_label} · {item.type_label} · {item.stage_label} · 版本 {item.version_no}
                    </div>
                    <div className="mt-2 text-sm leading-5 text-[#C7C7C7]">{item.summary}</div>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-xs text-[#5F5F5F]">{item.created_by} · {item.created_at}</span>
                      <span className="text-xs text-[#5F5F5F]">查看详情</span>
                    </div>
                  </button>
                ))
              )}
            </div>

            <div className="mt-3 shrink-0 border-t border-[#2A2A2A] pt-3 md:mt-4 md:pt-4">
              <div className="flex h-10 items-center gap-2 rounded-[18px] border border-[#2A2A2A] bg-[#171717] px-3 md:h-12">
                <Textarea
                  value={discussionText}
                  disabled={discussionDisabled}
                  onChange={(e) => {
                    setDiscussionText(e.target.value);
                    if (discussionMessage) setDiscussionMessage("");
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleDiscussionSubmit();
                    }
                  }}
                  placeholder="补充修改意见或关联材料说明..."
                  className="h-8 min-h-0 flex-1 resize-none border-0 bg-transparent py-1 text-sm leading-6 text-white outline-none placeholder:text-[#5F5F5F]"
                />
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={discussionDisabled || !discussionText.trim()}
                  onClick={handleDiscussionSubmit}
                  className="h-8 shrink-0 rounded-full px-3"
                >
                  发送
                </Button>
              </div>
              <div className="mt-2 text-xs text-[#5F5F5F]">
                {discussionHint}
              </div>
              {discussionMessage && (
                <div className="mt-2 text-xs text-[#8A8A8A]">{discussionMessage}</div>
              )}
            </div>
          </div>

          <div className="min-h-0 overflow-y-auto border-t border-[#2A2A2A] pt-6 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
            {selected ? (
              <>
                <div className="text-sm font-semibold text-white">{selected.title}</div>
                <div className="mt-0.5 text-xs text-[#8A8A8A]">
                  {selected.status_label} · {selected.type_label} · {selected.stage_label}
                </div>

                <Tabs value={activeDetailTab} onValueChange={setActiveDetailTab} className="mt-4 md:mt-5">
                  <TabsList>
                    <TabsTrigger value="content">内容</TabsTrigger>
                    <TabsTrigger value="evidence">证据</TabsTrigger>
                    <TabsTrigger value="versions">版本</TabsTrigger>
                    <TabsTrigger value="summary">摘要</TabsTrigger>
                  </TabsList>
                  <TabsContent value="content">
                    <div className="mt-4 text-sm leading-6 text-[#C7C7C7] whitespace-pre-line">
                      {cleanMockMarkdown(selected.content_markdown)}
                    </div>
                  </TabsContent>
                  <TabsContent value="evidence">
                    <ReadbackRows rows={evidenceRows} footer="仅展示成果来源与关联材料，不触发任何写入操作。" />
                  </TabsContent>
                  <TabsContent value="versions">
                    <ReadbackRows rows={versionRows} footer="仅展示版本信息，不执行修改操作。" />
                  </TabsContent>
                  <TabsContent value="summary">
                    <ReadbackRows rows={summaryRows} footer="仅展示成果摘要。" />
                  </TabsContent>
                </Tabs>
              </>
            ) : (
              <div className="py-8">
                <div className="text-sm text-[#8A8A8A]">
                  {deliverablesViewState === "loading" ? "正在准备成果详情" : deliverablesViewState === "error" ? "无法展示成果详情" : deliverablesViewState === "no_project" ? "等待项目上下文" : "请选择一个成果"}
                </div>
                <div className="mt-2 text-xs text-[#5F5F5F]">
                  {deliverablesViewState === "error" ? "请稍后重新查看。" : deliverablesViewState === "no_project" ? "当前没有可展示成果。" : "暂无可展示内容。"}
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function RepositorySpaceMockPage() {
  const [noteText, setNoteText] = useState("");
  const [noteMessage, setNoteMessage] = useState("");
  const [workspaceMessage, setWorkspaceMessage] = useState("");
  const viewState = "ready" as RepositoryPageViewState;

  const noteDisabled = viewState !== "ready";
  const workspacePath = "/Users/kk/owner project/AI-Dev-Orchestrator";
  const defaultWorkspaceRoot = "/Users/kk/AI-Workspaces";
  const detailItems = [
    {
      title: "仓库信息",
      description: "当前项目绑定的本地仓库。",
      rows: [
        ["仓库名称", "AI-Dev-Orchestrator"],
        ["本地路径", workspacePath],
        ["默认分支", "main"],
        ["查看方式", "只读查看"],
        ["忽略目录", ".git、node_modules、dist、build"],
      ] as const,
    },
    {
      title: "工作区设置",
      description: "Agent 可以使用的本地位置范围。",
      rows: [
        ["默认工作区", defaultWorkspaceRoot],
        ["允许位置", "/Users/kk/AI-Workspaces、/Users/kk/owner project"],
        ["当前路径状态", "位于允许位置内"],
        ["设置来源", "项目设置"],
      ] as const,
    },
    {
      title: "最近快照",
      description: "供 Agent 分析项目结构和定位文件。",
      rows: [
        ["快照状态", "已刷新"],
        ["最近刷新", "今天 14:32"],
        ["主要目录", "apps/web、runtime、docs"],
        ["用途", "供 Agent 分析项目结构和定位文件"],
      ] as const,
      actionLabel: "刷新仓库信息",
      actionMessage: "已记录刷新仓库信息",
    },
    {
      title: "变更准备",
      description: "仓库已可分析，等待生成变更计划。",
      rows: [
        ["当前状态", "等待生成变更计划"],
        ["已有关联成果", `${repositoryLinkedDeliverables.length} 项`],
        ["变更准备", "0 项待执行"],
        ["下一步", "让 AI 主管根据项目目标生成变更计划"],
      ] as const,
      actionLabel: "生成变更计划",
      actionMessage: "已记录生成变更计划请求",
    },
    {
      title: "写入边界",
      description: "改变本地仓库或远程仓库前需要人工确认。",
      rows: [
        ["默认方式", "只读查看"],
        ["需要确认", "修改文件、生成变更草稿、关联成果"],
        ["禁止自动处理", "自动提交、自动推送、自动合并、自动发布"],
        ["原因", repositoryBoundaryItems.find((item) => item.id === "repo_boundary_forbidden")?.reason ?? "这些操作会改变本地仓库或远程仓库，需要人工确认"],
      ] as const,
    },
  ];

  function handleSubmitNote() {
    if (noteDisabled || !noteText.trim()) return;
    setNoteText("");
    setNoteMessage("已记录到工作台讨论");
    setWorkspaceMessage("");
  }

  if (viewState === "loading") {
    return (
      <div className="min-h-0 flex-1 overflow-hidden px-4 py-6 md:px-6 md:py-8 lg:px-10">
        <div className="mx-auto w-full max-w-[1080px]">
          <div className="text-sm text-[#8A8A8A]">正在读取工作区</div>
          <Separator className="mt-4" />
          <div className="mt-4 h-4 w-3/4 rounded bg-[#1A1A1A]" />
          <div className="mt-3 h-3 w-1/2 rounded bg-[#1A1A1A]" />
        </div>
      </div>
    );
  }

  if (viewState === "empty") {
    return (
      <div className="min-h-0 flex-1 overflow-hidden px-4 py-6 md:px-6 md:py-8 lg:px-10">
        <div className="mx-auto w-full max-w-[1080px]">
          <div className="text-sm text-[#8A8A8A]">暂无仓库关联</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">当前项目还没有可展示的工作区。</div>
        </div>
      </div>
    );
  }

  if (viewState === "error") {
    return (
      <div className="min-h-0 flex-1 overflow-hidden px-4 py-6 md:px-6 md:py-8 lg:px-10">
        <div className="mx-auto w-full max-w-[1080px]">
          <div className="text-sm text-[#8A8A8A]">仓库信息读取失败</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">请稍后重试或回到工作台确认项目状态。</div>
        </div>
      </div>
    );
  }

  if (viewState === "no_project") {
    return (
      <div className="min-h-0 flex-1 overflow-hidden px-4 py-6 md:px-6 md:py-8 lg:px-10">
        <div className="mx-auto w-full max-w-[1080px]">
          <div className="text-sm text-[#8A8A8A]">尚未选择项目</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">选择项目后，这里会展示该项目的工作区。</div>
        </div>
      </div>
    );
  }

  if (viewState === "no_permission") {
    return (
      <div className="min-h-0 flex-1 overflow-hidden px-4 py-6 md:px-6 md:py-8 lg:px-10">
        <div className="mx-auto w-full max-w-[1080px]">
          <div className="text-sm text-[#8A8A8A]">暂无查看权限</div>
          <div className="mt-2 text-xs text-[#5F5F5F]">当前账号不能查看该项目的代码空间。</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 overflow-hidden px-4 py-5 md:px-6 md:py-6 lg:px-10">
      <div className="mx-auto flex h-full min-h-0 w-full max-w-[1080px] flex-col">
        <CompactPageHeader
          eyebrow="营销活动分析平台"
          title="工作区"
          meta="已就绪 · 只读查看"
          description="当前项目的 Agent 工作位置和准备状态。"
        />

        <section className="min-h-0 flex-1 overflow-y-auto border-b border-[#2A2A2A] py-5 [scrollbar-width:none] [-ms-overflow-style:none] md:py-6 [&::-webkit-scrollbar]:hidden">
          <div className="grid gap-6 border-b border-[#2A2A2A] pb-6 lg:grid-cols-[1fr_340px] lg:gap-8">
            <div className="min-w-0">
              <div className="mb-2 flex items-center gap-3">
                <h2 className="min-w-0 flex-1 truncate text-lg font-semibold text-white">AI-Dev-Orchestrator</h2>
                <span className="shrink-0 text-sm text-[#C7C7C7]">已就绪</span>
              </div>
              <div className="break-all text-sm leading-6 text-[#C7C7C7]">{workspacePath}</div>
              <div className="mt-3 text-sm text-[#8A8A8A]">本地 Git 仓库 · main · 只读查看</div>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-[#C7C7C7]">
                Agent 可以基于这个仓库分析项目、生成计划和准备变更。
              </p>

              <div className="mt-5 flex flex-wrap gap-3">
                <Button
                  onClick={() => {
                    setWorkspaceMessage("已记录开始分析仓库");
                    setNoteMessage("");
                  }}
                >
                  开始分析仓库
                </Button>
                <Dialog>
                  <DialogTrigger asChild>
                    <Button variant="secondary">更换仓库</Button>
                  </DialogTrigger>
                  <DialogContent className="w-[min(92vw,620px)]">
                    <DialogHeader>
                      <DialogTitle>连接工作区</DialogTitle>
                      <DialogDescription>
                        没有仓库时，可以选择已有仓库，或让 AI 主管创建新仓库作为当前项目工作区。
                      </DialogDescription>
                    </DialogHeader>

                    <div className="mt-5 grid gap-5 border-y border-[#2A2A2A] py-5 sm:grid-cols-2">
                      <div>
                        <h3 className="text-sm font-semibold text-white">选择已有仓库</h3>
                        <div className="mt-4 space-y-3 text-sm">
                          <div>
                            <div className="text-xs text-[#8A8A8A]">路径</div>
                            <div className="mt-1 break-all leading-6 text-[#C7C7C7]">{workspacePath}</div>
                          </div>
                          <div className="space-y-1 text-xs leading-5 text-[#8A8A8A]">
                            <div>必须是本地 Git 仓库</div>
                            <div>必须位于允许的工作区目录内</div>
                            <div>不会自动提交或推送</div>
                          </div>
                        </div>
                        <DialogClose asChild>
                          <Button
                            className="mt-5"
                            variant="secondary"
                            onClick={() => {
                              setWorkspaceMessage("已记录连接工作区操作");
                              setNoteMessage("");
                            }}
                          >
                            绑定已有仓库
                          </Button>
                        </DialogClose>
                      </div>

                      <div className="border-t border-[#2A2A2A] pt-5 sm:border-l sm:border-t-0 sm:pl-5 sm:pt-0">
                        <h3 className="text-sm font-semibold text-white">让 AI 主管创建新仓库</h3>
                        <div className="mt-4 space-y-3 text-sm">
                          <div>
                            <div className="text-xs text-[#8A8A8A]">默认位置</div>
                            <div className="mt-1 break-all leading-6 text-[#C7C7C7]">{defaultWorkspaceRoot}</div>
                          </div>
                          <div>
                            <div className="text-xs text-[#8A8A8A]">仓库名称</div>
                            <div className="mt-1 text-[#C7C7C7]">marketing-analytics</div>
                          </div>
                          <p className="text-xs leading-5 text-[#8A8A8A]">
                            创建后会绑定到当前项目，作为 Agent 工作区。
                          </p>
                        </div>
                        <DialogClose asChild>
                          <Button
                            className="mt-5"
                            variant="secondary"
                            onClick={() => {
                              setWorkspaceMessage("已记录创建工作区操作");
                              setNoteMessage("");
                            }}
                          >
                            创建新仓库
                          </Button>
                        </DialogClose>
                      </div>
                    </div>

                    <div className="mt-5 flex justify-end">
                      <DialogClose asChild>
                        <Button variant="secondary">关闭</Button>
                      </DialogClose>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>
              {workspaceMessage ? <div className="mt-3 text-xs text-[#8A8A8A]">{workspaceMessage}</div> : null}
            </div>

            <div className="border-t border-[#2A2A2A] pt-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
              <h2 className="text-sm font-semibold text-white">准备情况</h2>
              <div className="mt-4 space-y-2 text-sm leading-6">
                {[
                  "✓ 已绑定本地仓库",
                  "✓ 位于允许的工作区目录",
                  "✓ 已识别为 Git 仓库",
                  "✓ 仓库快照已刷新",
                  "○ 等待生成变更计划",
                ].map((item) => (
                  <div key={item} className="text-[#C7C7C7]">{item}</div>
                ))}
              </div>
            </div>
          </div>

          <div className="py-6">
            <h2 className="text-base font-semibold text-white">详情</h2>
            <div className="mt-3 border-y border-[#2A2A2A]">
              {detailItems.map((item) => (
                <Dialog key={item.title}>
                  <DialogTrigger asChild>
                    <button
                      type="button"
                      className="flex w-full items-center justify-between gap-4 border-b border-[#1F1F1F] px-1 py-3 text-left transition-colors last:border-b-0 hover:bg-[#080808] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20"
                    >
                      <span className="min-w-0">
                        <span className="block text-sm font-medium text-[#C7C7C7]">{item.title}</span>
                        <span className="mt-0.5 block text-xs leading-5 text-[#8A8A8A]">{item.description}</span>
                      </span>
                      <ChevronRight className="h-4 w-4 shrink-0 text-[#8A8A8A]" />
                    </button>
                  </DialogTrigger>
                  <DialogContent className="w-[min(92vw,560px)]">
                    <DialogHeader>
                      <DialogTitle>{item.title}</DialogTitle>
                      <DialogDescription>{item.description}</DialogDescription>
                    </DialogHeader>
                    <div className="mt-5">
                      <ReadbackRows rows={item.rows} />
                    </div>
                    <div className="mt-5 flex justify-end gap-3">
                      {item.actionLabel && item.actionMessage ? (
                        <Button
                          variant="secondary"
                          onClick={() => {
                            setWorkspaceMessage(item.actionMessage);
                            setNoteMessage("");
                          }}
                        >
                          {item.actionLabel}
                        </Button>
                      ) : null}
                      <DialogClose asChild>
                        <Button variant="secondary">关闭</Button>
                      </DialogClose>
                    </div>
                  </DialogContent>
                </Dialog>
              ))}
            </div>
          </div>

          <div className="shrink-0 border-t border-[#2A2A2A] pt-4">
            <div className="flex h-10 items-center gap-2 rounded-[18px] border border-[#2A2A2A] bg-[#171717] px-3 md:h-12">
              <Textarea
                value={noteText}
                disabled={noteDisabled}
                onChange={(e) => {
                  setNoteText(e.target.value);
                  if (noteMessage) setNoteMessage("");
                  if (workspaceMessage) setWorkspaceMessage("");
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmitNote();
                  }
                }}
                placeholder="补充工作区说明或仓库问题..."
                className="h-8 min-h-0 flex-1 resize-none border-0 bg-transparent py-1 text-sm leading-6 text-white outline-none placeholder:text-[#5F5F5F]"
              />
              <Button
                variant="secondary"
                size="sm"
                disabled={noteDisabled || !noteText.trim()}
                onClick={handleSubmitNote}
                className="h-8 shrink-0 rounded-full px-3"
              >
                发送
              </Button>
            </div>
            {noteMessage ? <div className="mt-2 text-xs text-[#8A8A8A]">{noteMessage}</div> : null}
          </div>
        </section>
      </div>
    </div>
  );
}

export function MockPageContent({
  pageKey,
  onQueueDiscussionAction,
}: {
  pageKey: string;
  onQueueDiscussionAction?: (mode: "add" | "add-and-open", title: string) => void;
}) {
  if (pageKey === "projects") {
    return <ProjectManagementMockPage />;
  }

  if (pageKey === "execution") {
    return <ExecutionCenterMockPage onQueueDiscussionAction={onQueueDiscussionAction} />;
  }

  if (pageKey === "deliverables") {
    return <DeliverablesCenterMockPage onQueueDiscussionAction={onQueueDiscussionAction} />;
  }

  if (pageKey === "repository") {
    return <RepositorySpaceMockPage />;
  }

  if (pageKey === "governance") {
    return <GovernanceSkillMockPage />;
  }

  const content: MainPageContent | undefined = mainPageMockContents[pageKey];

  if (!content) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[#8A8A8A]">
        页面未找到
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col px-6 py-8 md:px-10 md:py-12">
      <h2 className="text-2xl font-semibold tracking-normal text-white">{content.title}</h2>
      <p className="mt-2 text-sm font-medium text-[#C7C7C7]">{content.subtitle}</p>
      <p className="mt-3 max-w-lg text-sm leading-6 text-[#8A8A8A]">{content.description}</p>

      <div className="mt-8 space-y-1 max-w-md">
        {content.items.map((item) => (
          <button
            key={item.label}
            className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left transition-colors hover:bg-[#222222] active:scale-[0.98]"
          >
            <span className="min-w-0 flex-1 text-sm font-medium text-white">{item.label}</span>
            <span className="text-xs text-[#8A8A8A]">{item.description}</span>
            <ChevronRight className="h-4 w-4 shrink-0 text-[#5F5F5F]" />
          </button>
        ))}
      </div>
    </div>
  );
}
