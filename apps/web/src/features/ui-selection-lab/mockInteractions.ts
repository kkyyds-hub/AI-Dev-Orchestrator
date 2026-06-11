import {
  Activity,
  Archive,
  Bot,
  CircleEllipsis,
  ClipboardCheck,
  FolderKanban,
  Gauge,
  GitBranch,
  LayoutDashboard,
  ShieldCheck,
  Timer,
  Wallet,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// ── Nav Items ──────────────────────────────────────────────

export interface NavItem {
  label: string;
  icon: LucideIcon;
  active?: boolean;
  muted?: boolean;
  badge?: string;
}

export const runtimeNavItems: NavItem[] = [
  { label: "数据看板", icon: LayoutDashboard },
  { label: "待审批", icon: ClipboardCheck, badge: "2" },
  { label: "执行状态", icon: Activity },
  { label: "... 更多", icon: CircleEllipsis, muted: true },
];

export const pageNavItems: NavItem[] = [
  { label: "项目管理", icon: FolderKanban },
  { label: "执行中心", icon: Workflow },
  { label: "成果中心", icon: Archive },
  { label: "治理", icon: ShieldCheck },
];

// ── Project Groups & Conversations ─────────────────────────

export interface Conversation {
  id: string;
  title: string;
  status: "running" | "partial" | "passed" | "blocked" | "pending";
}

export interface ProjectGroup {
  id: string;
  name: string;
  conversations: Conversation[];
}

export const projectGroups: ProjectGroup[] = [
  {
    id: "proj-mvp",
    name: "二手交易平台 MVP",
    conversations: [
      { id: "conv-1", title: "商品发布与搜索规划", status: "partial" },
      { id: "conv-2", title: "聊天与订单闭环", status: "running" },
      { id: "conv-3", title: "后台审核方案", status: "pending" },
      { id: "conv-4", title: "支付与结算设计", status: "blocked" },
    ],
  },
  {
    id: "proj-ai",
    name: "AI 项目主管改造",
    conversations: [
      { id: "conv-5", title: "Workbench 两栏布局", status: "passed" },
      { id: "conv-6", title: "PromptBox 交互设计", status: "partial" },
      { id: "conv-7", title: "Minimal Dark Tokens", status: "running" },
    ],
  },
  {
    id: "proj-infra",
    name: "基础设施与部署",
    conversations: [
      { id: "conv-8", title: "CI 流水线配置", status: "passed" },
      { id: "conv-9", title: "容器化方案", status: "pending" },
    ],
  },
];

// ── Mock Conversations Messages ────────────────────────────

export interface MockMessage {
  role: "user" | "assistant";
  content: string;
  time: string;
}

export const mockConversationMessages: Record<string, MockMessage[]> = {
  "conv-1": [
    {
      role: "user",
      content: "为二手交易平台的商品搜索功能设计执行计划。",
      time: "12:38",
    },
    {
      role: "assistant",
      content:
        "已生成商品发布与搜索规划：\n\n1. 定义搜索字段（标题、分类、价格区间、位置）\n2. 设计 Elasticsearch 索引映射\n3. 实现前端搜索栏与结果列表\n4. 添加搜索结果过滤与排序\n\n状态：Partial — 等待确认过滤维度。",
      time: "12:39",
    },
    {
      role: "user",
      content: "能否加入按发布时间排序？",
      time: "12:41",
    },
    {
      role: "assistant",
      content:
        "可以。已追加 `created_at` 排序字段到索引映射，默认按相关性排序，用户可切换到最新发布。更新后的过滤维度：分类、价格区间、位置、发布时间。",
      time: "12:42",
    },
  ],
  "conv-2": [
    {
      role: "user",
      content: "为买家卖家聊天设计实时消息方案。",
      time: "11:20",
    },
    {
      role: "assistant",
      content:
        "聊天与订单闭环方案：\n\n1. WebSocket 实时消息通道\n2. 消息持久化到 PostgreSQL\n3. 未读消息计数与推送\n4. 订单状态变更联动聊天通知\n\n状态：Running — 正在实现消息持久化层。",
      time: "11:22",
    },
    {
      role: "user",
      content: "需要支持图片消息吗？",
      time: "11:25",
    },
    {
      role: "assistant",
      content:
        "第一期仅支持文本消息。图片消息已列入 Phase 2，将复用对象存储基础设施。当前优先完成文本消息的收发、持久化和订单联动。",
      time: "11:26",
    },
  ],
  "conv-5": [
    {
      role: "user",
      content: "将三省六部工作台重构为两栏布局。",
      time: "09:15",
    },
    {
      role: "assistant",
      content:
        "Workbench 两栏布局方案：\n\n1. 左侧固定 Sidebar（248-300px 响应式）\n2. 右侧主工作区 flex-1\n3. 底部 PromptBox 居中悬浮\n4. 顶部状态栏 56-64px\n\n布局已完成并通过响应式验收。",
      time: "09:18",
    },
    {
      role: "user",
      content: "PromptBox 的对齐方式是否合理？",
      time: "09:22",
    },
    {
      role: "assistant",
      content:
        "当前 PromptBox 采用 `absolute bottom left-1/2 -translate-x-1/2` 居中定位，宽度使用 `min(760px, calc(100vw - sidebar - 64px))` 约束。在 1280-1440px 视口宽度下表现良好，建议保持。",
      time: "09:24",
    },
  ],
};

export function getDefaultMessages(): MockMessage[] {
  return [
    {
      role: "assistant",
      content: "欢迎回来。选择一个项目会话，或描述你想构建的目标。",
      time: "刚刚",
    },
  ];
}

// ── Dashboard Mock ─────────────────────────────────────────

export const dashboardMetrics = [
  { label: "运行次数", value: "128", hint: "近 7 天", icon: Workflow },
  { label: "成功率", value: "91%", hint: "灰阶状态", icon: Activity },
  { label: "平均耗时", value: "6m 42s", hint: "单次运行", icon: Timer },
  { label: "成本估算", value: "$18.6", hint: "本周", icon: Wallet },
];

export const chartLinePoints: readonly (readonly [number, number])[] = [
  [8, 72],
  [28, 58],
  [48, 66],
  [68, 42],
  [88, 46],
  [108, 28],
  [128, 36],
  [148, 20],
  [168, 30],
] as const;

export const chartBars = [44, 68, 52, 82, 58, 74, 48, 64];

// ── Approvals Mock ─────────────────────────────────────────

export interface ApprovalItem {
  id: string;
  title: string;
  project: string;
  status: "partial" | "passed" | "pending" | "blocked";
  actionLabel: string;
  state: "pending" | "approved" | "rejected";
}

export const initialApprovals: ApprovalItem[] = [
  {
    id: "appr-1",
    title: "商品发布与搜索规划",
    project: "二手交易平台 MVP",
    status: "partial",
    actionLabel: "等待确认",
    state: "pending",
  },
  {
    id: "appr-2",
    title: "Workbench 两栏布局",
    project: "AI 项目主管改造",
    status: "passed",
    actionLabel: "等待放行",
    state: "pending",
  },
];

// ── Execution Status Mock ──────────────────────────────────

export interface RunRecord {
  id: string;
  title: string;
  status: "running" | "partial" | "passed" | "blocked";
  time: string;
  duration: string;
}

export const runRecords: RunRecord[] = [
  {
    id: "run-1",
    title: "Workbench UI Lab 构建检查",
    status: "passed",
    time: "12:42",
    duration: "4s",
  },
  {
    id: "run-2",
    title: "商品搜索规划执行",
    status: "partial",
    time: "12:38",
    duration: "22s",
  },
  {
    id: "run-3",
    title: "聊天消息持久化层",
    status: "running",
    time: "11:22",
    duration: "进行中",
  },
  {
    id: "run-4",
    title: "支付结算方案审查",
    status: "blocked",
    time: "10:15",
    duration: "8s",
  },
  {
    id: "run-5",
    title: "后端审核模块部署",
    status: "passed",
    time: "09:48",
    duration: "31s",
  },
];

export const mockExecutionLog = `[12:42:10] run started: workbench-ui-lab
[12:42:11] lint check passed
[12:42:14] build passed (3.2s)
[12:42:16] diff summary: 5 files changed, +340 -12
[12:42:18] run completed: passed

[12:38:02] run started: search-planning
[12:38:06] task 1/4 completed: index design
[12:38:12] task 2/4 completed: search fields
[12:38:18] task 3/4 completed: filter UI
[12:38:24] task 4/4 partial: sort dimension pending
[12:38:24] run completed: partial`;

// ── More Tools Mock ────────────────────────────────────────

export interface ToolEntry {
  label: string;
  icon: LucideIcon;
  description: string;
}

export const moreTools: ToolEntry[] = [
  {
    label: "任务队列",
    icon: Workflow,
    description: "查看当前排队的任务与优先级",
  },
  {
    label: "运行记录",
    icon: Timer,
    description: "浏览历史运行日志与结果",
  },
  {
    label: "Git 写入预览",
    icon: GitBranch,
    description: "预览待提交的代码变更",
  },
  {
    label: "证据中心",
    icon: Archive,
    description: "查看可交付物与审查证据",
  },
  {
    label: "成本用量",
    icon: Wallet,
    description: "Token 消耗与 API 成本统计",
  },
  {
    label: "模型配置",
    icon: Bot,
    description: "管理可用模型与策略",
  },
  {
    label: "执行器配置",
    icon: Gauge,
    description: "配置 Codex / DeepSeek 执行器参数",
  },
];

// ── Main Pages Mock ────────────────────────────────────────

export interface MainPageContent {
  title: string;
  subtitle: string;
  description: string;
  items: { label: string; description: string }[];
}

export const mainPageMockContents: Record<string, MainPageContent> = {
  projects: {
    title: "项目管理",
    subtitle: "项目目标、范围与阶段计划",
    description: "创建和管理 AI 项目主管协助的项目，拆分为可执行的最小子任务。",
    items: [
      { label: "创建新项目", description: "定义目标、约束和初始范围" },
      { label: "导入现有项目", description: "从 Git 仓库或本地路径导入" },
      { label: "查看项目列表", description: "浏览所有活跃和归档项目" },
    ],
  },
  execution: {
    title: "执行中心",
    subtitle: "Agent 队列、运行状态与恢复",
    description: "监控 Agent 执行队列，查看运行日志，处理失败恢复和人工介入。",
    items: [
      { label: "运行中任务", description: "当前正在执行的 Agent 任务" },
      { label: "失败恢复", description: "查看并重试失败的执行步骤" },
      { label: "执行日志", description: "浏览 Codex / DeepSeek 运行日志" },
    ],
  },
  deliverables: {
    title: "成果中心",
    subtitle: "沉淀文档、代码变更与可交付证据",
    description: "集中查看所有项目产生的文档、代码变更记录和审查证据。",
    items: [
      { label: "交付文档", description: "查看生成的技术文档和计划" },
      { label: "代码变更", description: "浏览 Git diff 与变更摘要" },
      { label: "审查记录", description: "查看审查结果与通过状态" },
    ],
  },
  governance: {
    title: "治理",
    subtitle: "审批、策略、权限与记忆治理",
    description: "管理项目审批流程、访问策略、成本限制和 AI 记忆治理。",
    items: [
      { label: "审批管理", description: "查看和操作待审批项目" },
      { label: "策略配置", description: "设置执行策略与安全边界" },
      { label: "记忆治理", description: "管理 AI 上下文与记忆范围" },
    ],
  },
};

// ── Quick Action Mock Content ──────────────────────────────

export const quickActionMockContent = {
  createPlan: {
    projectGoal: "为「二手交易平台 MVP」生成完整的任务拆分计划",
    constraints: "预算限制：$500 以内；技术栈：React + Node.js",
  },
  reviewResult: {
    placeholder: "粘贴 Codex / DeepSeek 执行结果...\n\n例如：\n- diff 摘要\n- 构建状态\n- 测试结果",
  },
  advanceNext: {
    instruction: `## 下一条最小执行指令

**任务**: 实现搜索栏组件 SearchBar.tsx
**依赖**: 无
**预计耗时**: 15-25 分钟
**验收标准**:
- 输入框支持关键词搜索
- 搜索结果实时过滤
- 空状态显示占位提示
- 使用 Minimal Dark Tokens`,
  },
};
