import {
  Activity,
  Archive,
  CircleEllipsis,
  ClipboardCheck,
  FolderKanban,
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

export type MessageCardType = "draft" | "review" | "progress" | "next_step";

export interface MessageCard {
  type: MessageCardType;
  title: string;
  status: string;
  summary: string;
  items: string[];
  primaryAction: string;
  secondaryAction?: string;
}

export interface MockMessage {
  role: "user" | "assistant";
  content: string;
  time: string;
  card?: MessageCard;
}

// ── Mock Cards for Conversation Samples ─────────────────────

export const mockDraftCard: MessageCard = {
  type: "draft",
  title: "项目草案",
  status: "draft",
  summary: "基于对话澄清的目标，整理出以下项目草案。",
  items: [
    "目标：为二手交易平台构建 MVP 版本",
    "范围：商品发布、搜索、聊天、订单闭环",
    "约束：React + Node.js，预算 $500 以内",
  ],
  primaryAction: "确认草案",
  secondaryAction: "继续澄清",
};

export const mockReviewCard: MessageCard = {
  type: "review",
  title: "审查报告",
  status: "passed",
  summary: "Workbench UI Lab 构建检查已完成，代码审查通过。",
  items: [
    "结论：通过",
    "发现：无阻断问题",
    "建议：PromptBox 对齐方式建议后续微调",
  ],
  primaryAction: "生成修正指令",
  secondaryAction: "标记为已读",
};

export const mockProgressCard: MessageCard = {
  type: "progress",
  title: "进度汇报",
  status: "in_progress",
  summary: "当前项目执行进度概览。",
  items: [
    "已完成：商品发布与搜索规划",
    "进行中：聊天与订单闭环",
    "阻塞：支付与结算设计（等待 API 文档）",
  ],
  primaryAction: "查看详情",
};

export const mockNextStepCard: MessageCard = {
  type: "next_step",
  title: "下一步指令",
  status: "ready",
  summary: "根据当前审查结果，建议下一轮只修复 PromptBox 与消息卡片视觉。",
  items: [
    "范围：仅修改隐藏实验页",
    "执行器：Codex",
    "验收：build 通过，视觉保持 Minimal Dark",
  ],
  primaryAction: "复制指令",
  secondaryAction: "继续讨论",
};

export const mockConversationMessages: Record<string, MockMessage[]> = {
  "conv-1": [
    {
      role: "user",
      content: "为二手交易平台的商品搜索功能设计执行计划。",
      time: "12:38",
    },
    {
      role: "assistant",
      content: "我已经根据当前目标整理出项目草案，下面是主管建议：",
      time: "12:39",
      card: mockDraftCard,
    },
    {
      role: "user",
      content: "能否加入按发布时间排序？",
      time: "12:41",
    },
    {
      role: "assistant",
      content: "可以。已追加 `created_at` 排序字段到索引映射，默认按相关性排序，用户可切换到最新发布。",
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
      content: "收到。我先整理当前进度：",
      time: "11:22",
      card: mockProgressCard,
    },
    {
      role: "user",
      content: "需要支持图片消息吗？",
      time: "11:25",
    },
    {
      role: "assistant",
      content: "第一期仅支持文本消息。图片消息已列入 Phase 2，将复用对象存储基础设施。当前优先完成文本消息的收发、持久化和订单联动。",
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
      content: "创建一个项目或选择一个已有项目来开始。",
      time: "刚刚",
    },
  ];
}

export function getNewConversationWelcome(): MockMessage[] {
  return [
    {
      role: "assistant",
      content: "项目已创建。描述你的目标，AI 主管会逐步帮你澄清范围、生成计划并推进执行。",
      time: "刚刚",
    },
  ];
}

// Extend conv-5 with card messages
mockConversationMessages["conv-5"] = [
  {
    role: "user",
    content: "将三省六部工作台重构为两栏布局。",
    time: "09:15",
  },
  {
    role: "assistant",
    content: "我已经整理出当前方案，下面是主管建议：",
    time: "09:18",
    card: { ...mockDraftCard, title: "主管建议", status: "draft", summary: "基于 Minimal Dark 方向整理的两栏布局方案。" },
  },
  {
    role: "user",
    content: "方向没问题，继续推进。",
    time: "09:22",
  },
  {
    role: "assistant",
    content: "下面是我根据当前进度整理的审查报告：",
    time: "09:24",
    card: mockReviewCard,
  },
  {
    role: "assistant",
    content: "审查已完成。建议按以下最小指令推进下一步：",
    time: "09:26",
    card: mockNextStepCard,
  },
];

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

// ── More Tools Mock (slim — only 3) ────────────────────────

export interface SlimToolEntry {
  key: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

export const slimMoreTools: SlimToolEntry[] = [
  {
    key: "cost-usage",
    label: "成本用量",
    icon: Wallet,
    description: "Token 消耗与 API 成本统计",
  },
  {
    key: "repo-queue",
    label: "仓库队列",
    icon: Archive,
    description: "待处理仓库任务与变更队列",
  },
  {
    key: "git-write-preview",
    label: "Git 写入预览",
    icon: GitBranch,
    description: "预览待提交的代码变更",
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
  "cost-usage": {
    title: "成本用量",
    subtitle: "Token 消耗与 API 成本统计",
    description: "查看近期 API 调用次数、Token 消耗量及预估费用。",
    items: [
      { label: "本周消耗", description: "GPT-4o: 142K tokens / $0.71" },
      { label: "本月累计", description: "总计 1.2M tokens / $5.84" },
      { label: "按项目拆分", description: "闲置二手 42% / AI 主管改造 58%" },
    ],
  },
  "repo-queue": {
    title: "仓库队列",
    subtitle: "待处理仓库任务与变更队列",
    description: "查看当前排队中的仓库操作、分支状态与合并请求。",
    items: [
      { label: "待合并分支", description: "feat/search-bar — 等待审查" },
      { label: "构建队列", description: "2 个任务排队中" },
      { label: "最近提交", description: "23c2f8a — workbench lab interactions" },
    ],
  },
  "git-write-preview": {
    title: "Git 写入预览",
    subtitle: "预览待提交的代码变更",
    description: "审查 AI 生成的代码 diff 后再决定是否提交。",
    items: [
      { label: "待提交 diff", description: "3 files changed, +156 -12" },
      { label: "变更文件", description: "SanshengLiubuUiLabPage.tsx, mockInteractions.ts" },
      { label: "提交信息预览", description: "feat(web): add workbench lab interactions" },
    ],
  },
};

// ── More Tools Dialog Mock Data ─────────────────────────────

export const costUsageMock = {
  todayTokens: "42,180",
  weekCost: "$2.47",
  primaryModel: "GPT-4o",
  trend: [28, 34, 42, 38, 46, 52, 42],
};

export const repoQueueMock = {
  pendingReview: [
    { branch: "feat/search-bar", status: "等待审查", author: "Codex" },
  ],
  pendingMerge: [
    { branch: "feat/sansheng-liubu-ui-selection-lab", status: "待合入", author: "kk" },
  ],
  pendingDraft: [
    { message: "feat(web): add search component", changedFiles: 3, additions: 156, deletions: 12 },
  ],
};

export const gitWritePreviewMock = {
  changes: [
    { file: "SanshengLiubuUiLabPage.tsx", additions: 42, deletions: 18 },
    { file: "WorkbenchRuntimeModals.tsx", additions: 86, deletions: 5 },
    { file: "mockInteractions.ts", additions: 28, deletions: 0 },
  ],
  commitMessage: "fix(web): correct more tools sidebar interaction",
  diffSummary: `diff --git a/apps/web/src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx
--- a/apps/web/src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx
+++ b/apps/web/src/features/ui-selection-lab/SanshengLiubuUiLabPage.tsx
@@ -435,11 +435,10 @@
-  <div className="ml-5 mt-0.5 ...">
+  <div className="mt-0.5 ...">
-    onClick={() => { setActiveMainPage(tool.key); ... }}
+    // open dialog instead`,
  limitationNote: "实验页 mock：不执行真实 Git 写入。",
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
