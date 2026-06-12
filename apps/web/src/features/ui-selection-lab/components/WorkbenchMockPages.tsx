import {
  Briefcase,
  Check,
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
  ReadbackRows,
  Separator,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "./ui";
import { mainPageMockContents, type MainPageContent } from "../mockInteractions";

const projectScopeRows = [
  ["项目目标", "构建营销数据分析平台，支持多维度洞察与增长决策"],
  ["当前边界", "聚焦接入、指标体系、可视化分析、报表导出"],
  ["关键约束", "数据合规、敏捷交付、上线时间"],
  ["交付标准", "功能可用、性能达标、文档完整、验收通过"],
] as const;

const projectPlanSteps = [
  {
    label: "目标澄清",
    status: "已完成",
    state: "done",
    bubbleTitle: "目标澄清已完成",
    bubbleSummary: "已确认目标、边界与交付标准。",
    bubbleMeta: "已完成",
  },
  {
    label: "任务拆分",
    status: "进行中",
    state: "current",
    bubbleTitle: "任务拆分进行中",
    bubbleSummary: "正在拆分数据接入与指标口径任务。",
    bubbleMeta: "待人工 1 项",
  },
  {
    label: "执行规划",
    status: "待开始",
    state: "pending",
    bubbleTitle: "执行规划待开始",
    bubbleSummary: "等待任务拆分完成后生成执行顺序。",
    bubbleMeta: "待开始",
  },
  {
    label: "交付验收",
    status: "待开始",
    state: "pending",
    bubbleTitle: "交付验收待开始",
    bubbleSummary: "执行完成后汇总交付物与验收证据。",
    bubbleMeta: "待开始",
  },
] as const;

const projectContextRows = [
  ["task", "最近任务", "拆分数据接入模块任务", "32 分钟前"],
  ["timeline", "最近操作", "数据源连通性测试", "1 小时前"],
  ["repository", "仓库绑定", "dev/marketing-analytics", "已绑定"],
  ["approval", "审批 / 交付物", "待审批 1 项 / 交付物 0 项", "待处理"],
] as const;

const executionProgressSteps = [
  {
    title: "已领取任务",
    detail: "11:32:41 · Worker 1 已领取并确认",
    state: "done",
  },
  {
    title: "上下文已建立",
    detail: "11:32:43 · 项目信息与上下文已加载",
    state: "done",
  },
  {
    title: "执行中",
    detail: "11:34:08 · AI 正在处理当前任务",
    state: "current",
  },
  {
    title: "等待结果回写",
    detail: "预计 11:40 前完成",
    state: "pending",
  },
] as const;

const executionStepDetails = {
  已领取任务: {
    title: "已领取任务",
    description: "任务领取读回 · mock",
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
  上下文已建立: {
    title: "上下文已建立",
    description: "执行上下文读回 · mock",
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
  执行中: {
    title: "执行中",
    description: "当前运行步骤读回 · mock",
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
  等待结果回写: {
    title: "等待结果回写",
    description: "结果回写等待状态 · mock",
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
} as const;

type ExecutionStepTitle = keyof typeof executionStepDetails;

const executionStatusRows = [
  ["运行", "running · run_7F3A"],
  ["运行环境", "ready"],
  ["工作区", "clean"],
  ["Git", "只读预检 · 写入关闭"],
  ["审批", "无需审批"],
  ["质量闸门", "等待结果"],
  ["预算", "正常"],
] as const;

const executionEvidenceDialogItems = [
  {
    key: "run",
    label: "运行详情",
    title: "运行详情",
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
    label: "决策回放",
    title: "决策回放",
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
    label: "安全预检",
    title: "安全预检",
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
] as const;

const executionQueueRows = [
  {
    state: "待人工",
    title: "数据源账号确认",
    note: "需产品负责人确认",
    description: "后续队列任务读回 · mock",
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
  },
  {
    state: "待执行",
    title: "指标口径确认",
    note: "AI 评估后自动执行",
    description: "后续队列任务读回 · mock",
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
  },
  {
    state: "待执行",
    title: "可视化报表联调",
    note: "预计 2 个任务后进行",
    description: "后续队列任务读回 · mock",
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
  },
] as const;

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
  const hasDiscussion = discussion.trim().length > 0;
  const openStage = openStageIndex === null ? null : projectPlanSteps[openStageIndex];
  const stageBubbleLeft = openStageIndex === null ? "50%" : `${(openStageIndex + 0.5) * 25}%`;

  function handleRecordFeedback() {
    if (!hasDiscussion) return;
    setDiscussion("");
    setFeedbackMessage("已记录讨论点 · 将在工作台新会话反馈 · mock");
  }

  return (
    <div className="ui-lab-project-page min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
      <div className="mx-auto flex w-full max-w-[980px] flex-col">
        <section className="pt-1">
          <div className="mb-3 text-xs font-medium tracking-[0.12em] text-[#8A8A8A]">
            当前项目上下文 · 仅展示当前选中项目
          </div>
          <h1 className="text-2xl font-semibold tracking-normal text-white">营销活动分析平台</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[#C7C7C7]">
            构建统一的营销数据分析平台，整合多渠道数据，提供可视化洞察与增长决策支持。
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-[#C7C7C7]">
            <span className="inline-flex h-7 items-center gap-1.5 rounded-full border border-[#2A2A2A] bg-[#171717] px-3 text-xs text-white">
              <span className="h-1.5 w-1.5 rounded-full bg-[#C7C7C7]" />
              进行中
            </span>
            <span className="hidden h-5 w-px bg-[#2A2A2A] sm:block" />
            <span>当前阶段：任务拆分</span>
            <span className="hidden h-5 w-px bg-[#2A2A2A] sm:block" />
            <span>最后更新：2025-05-22 14:32</span>
          </div>
          <div className="mt-3 text-xs text-[#8A8A8A]">
            任务 28 项 · 已完成 6 · 执行中 2 · 待人工 1
          </div>
        </section>

        <section className="mt-6 rounded-lg border border-[#2A2A2A] bg-[#171717]/80 px-5 py-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <FileText className="h-4 w-4 text-[#C7C7C7]" />
            <span>摘要</span>
          </div>
          <div className="mt-4 space-y-2 text-sm leading-6 text-[#C7C7C7]">
            <p>项目整体进度顺利，已完成目标澄清并梳理核心需求，正在进行任务拆分与优先级排序。</p>
            <p>建议聚焦数据接入与指标体系搭建的核心路径，优先完成关键链路以尽早验证价值。</p>
          </div>
        </section>

        <section className="mt-6">
          <ProjectSectionTitle icon={FolderOpen}>项目范围</ProjectSectionTitle>
          <div className="mt-3 border-y border-[#2A2A2A]">
            {projectScopeRows.map(([label, value]) => (
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

        <section className="relative mt-6">
          <ProjectSectionTitle icon={Clock3}>阶段计划</ProjectSectionTitle>
          <div className="mt-5 grid grid-cols-4 items-start">
            {projectPlanSteps.map((step, index) => (
              <div key={step.label} className="relative flex min-w-0 flex-col items-center text-center">
                {index > 0 ? (
                  <span className="absolute left-0 top-3 h-px w-1/2 bg-[#3A3A3A]" />
                ) : null}
                {index < projectPlanSteps.length - 1 ? (
                  <span className="absolute right-0 top-3 h-px w-1/2 bg-[#3A3A3A]" />
                ) : null}
                <button
                  className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-[#111111] focus-visible:bg-[#111111] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/10 active:scale-[0.98]"
                  onClick={() => {
                    setOpenStageIndex((current) => (current === index ? null : index));
                  }}
                  aria-label={`查看${step.label}阶段进展`}
                  aria-pressed={openStageIndex === index}
                >
                  <span
                    className={[
                      "relative flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold",
                      step.state === "done"
                        ? "border-[#3A3A3A] bg-[#2C2C2C] text-white"
                        : step.state === "current"
                          ? "border-white bg-black text-white"
                          : "border-[#2A2A2A] bg-[#171717] text-[#8A8A8A]",
                    ].join(" ")}
                  >
                    {step.state === "current" ? (
                      <span className="absolute inset-[-4px] rounded-full border border-white/20 animate-pulse" />
                    ) : null}
                    <span className="relative z-10">
                      {step.state === "done" ? <Check className="h-4 w-4" /> : index + 1}
                    </span>
                  </span>
                </button>
                <div className="mt-3 w-full px-1 text-sm font-medium text-[#C7C7C7]">{step.label}</div>
                <div className="mt-1 text-xs text-[#8A8A8A]">{step.status}</div>
              </div>
            ))}
          </div>
          <div
            className={[
              "absolute top-[76px] z-20 w-[min(82vw,260px)] origin-top -translate-x-1/2 rounded-2xl border border-[#2A2A2A] bg-[#171717] px-3 py-3 shadow-2xl shadow-black/40 transition-all duration-200 ease-out",
              openStage ? "scale-100 opacity-100" : "pointer-events-none scale-95 opacity-0",
            ].join(" ")}
            style={{ left: stageBubbleLeft }}
          >
            <span className="absolute left-1/2 top-[-5px] h-2.5 w-2.5 -translate-x-1/2 rotate-45 border-l border-t border-[#2A2A2A] bg-[#171717]" />
            {openStage ? (
              <>
                <div className="text-sm font-medium text-white">{openStage.bubbleTitle}</div>
                <p className="mt-1 text-xs leading-5 text-[#C7C7C7]">{openStage.bubbleSummary}</p>
                <div className="mt-2 text-xs text-[#8A8A8A]">状态：{openStage.bubbleMeta}</div>
              </>
            ) : null}
          </div>
        </section>

        <section className="mt-6">
          <ProjectSectionTitle icon={Briefcase}>当前上下文</ProjectSectionTitle>
          <div className="mt-3 border-y border-[#2A2A2A]">
            {projectContextRows.map(([dialogKey, label, value, meta]) => (
              <ProjectContextDialog key={label} dialogKey={dialogKey}>
                <button
                  className="grid w-full items-center gap-2 border-b border-[#1F1F1F] px-3 py-2.5 text-left text-sm transition-colors last:border-b-0 hover:bg-[#111111] focus-visible:bg-[#111111] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/10 md:grid-cols-[170px_1fr_112px_16px]"
                >
                  <span className="text-[#8A8A8A]">{label}</span>
                  <span className="min-w-0 truncate text-[#C7C7C7]">{value}</span>
                  <span className="text-left text-[#8A8A8A] md:text-right">{meta}</span>
                  <ChevronRight className="hidden h-4 w-4 text-[#5F5F5F] md:block" />
                </button>
              </ProjectContextDialog>
            ))}
          </div>
        </section>

        <div className="mt-4">
          <div className="flex h-11 items-center gap-2 rounded-[18px] border border-[#2A2A2A] bg-[#171717] px-4">
            <input
              className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-[#8A8A8A]"
              placeholder="记录审批疑问或改进点，AI 主管将在工作台新会话中反馈..."
              value={discussion}
              onChange={(event) => {
                setDiscussion(event.target.value);
                if (feedbackMessage) setFeedbackMessage("");
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  handleRecordFeedback();
                }
              }}
            />
            <button
              className={[
                "flex h-8 shrink-0 items-center justify-center rounded-full px-3 text-xs font-medium transition-colors active:scale-[0.96]",
                hasDiscussion ? "bg-white text-black hover:bg-[#E7E7E7]" : "bg-[#2C2C2C] text-[#8A8A8A]",
              ].join(" ")}
              disabled={!hasDiscussion}
              aria-label="记录讨论点"
              onClick={handleRecordFeedback}
            >
              记录
            </button>
          </div>
          {feedbackMessage ? (
            <div className="mt-2 text-xs text-[#8A8A8A]">{feedbackMessage}</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ExecutionCenterMockPage() {
  const [activeEvidenceTab, setActiveEvidenceTab] = useState("run");

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-6 py-8 md:px-10">
      <div className="mx-auto flex w-full max-w-[1080px] flex-col">
        <section className="border-b border-[#2A2A2A] pb-7">
          <div className="text-sm font-medium text-[#8A8A8A]">当前运行</div>
          <h1 className="mt-3 text-2xl font-semibold tracking-normal text-white md:text-[28px]">
            AI 正在处理：数据接入模块联调
          </h1>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-[#C7C7C7]">
            <span>Codex</span>
            <span className="text-[#5F5F5F]">·</span>
            <span>Worker 1/3</span>
            <span className="text-[#5F5F5F]">·</span>
            <span>运行环境就绪</span>
            <span className="text-[#5F5F5F]">·</span>
            <span>预算正常</span>
            <span className="text-[#5F5F5F]">·</span>
            <span>Git 写入关闭</span>
          </div>
          <div className="mt-2 text-xs text-[#5F5F5F]">上次刷新 11:34:40 · mock</div>
        </section>

        <section className="grid gap-8 border-b border-[#2A2A2A] py-7 lg:grid-cols-[1fr_1.15fr] lg:gap-10">
          <div>
            <h2 className="text-base font-semibold text-white">当前运行</h2>
            <div className="mt-5 space-y-0">
              {executionProgressSteps.map((step, index) => {
                const detail = executionStepDetails[step.title as ExecutionStepTitle];
                const isDone = step.state === "done";
                const isCurrent = step.state === "current";
                const isPending = step.state === "pending";

                const stepContent = (
                  <>
                    {index < executionProgressSteps.length - 1 ? (
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

                // Pending step: not clickable
                if (isPending) {
                  return (
                    <div
                      key={step.title}
                      className="relative grid grid-cols-[40px_1fr] items-start rounded-2xl pb-7 text-left last:pb-0"
                    >
                      {stepContent}
                    </div>
                  );
                }

                // Done or current: clickable with dialog
                return (
                  <Dialog key={step.title}>
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
                        <DialogTitle>{detail.title}</DialogTitle>
                        <DialogDescription>{detail.description}</DialogDescription>
                      </DialogHeader>
                      <ReadbackRows rows={detail.rows} records={detail.logs} footer={detail.footer} />
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
            <h2 className="text-base font-semibold text-white">安全与状态</h2>
            <ReadbackRows rows={executionStatusRows} compact />
            <div className="mt-5 space-y-2 text-sm leading-6 text-[#8A8A8A]">
              <p>正在校验数据源连通性，并生成接入任务拆分建议。</p>
              <p>当前未触发 Git 写入，运行环境处于只读安全边界内。</p>
            </div>

            {/* Merged evidence dialog */}
            <Dialog>
              <div className="mt-5 flex flex-wrap items-center gap-2 text-sm text-[#8A8A8A]">
                <span>查看证据：</span>
                {executionEvidenceDialogItems.map((item) => (
                  <DialogTrigger asChild key={item.key}>
                    <Button
                      variant="secondary"
                      size="sm"
                      className="h-7 rounded-md border border-[#2A2A2A] bg-transparent px-2.5 text-xs text-[#C7C7C7] hover:bg-[#222222] hover:text-white active:scale-[0.98]"
                      onClick={() => setActiveEvidenceTab(item.key)}
                    >
                      {item.label}
                    </Button>
                  </DialogTrigger>
                ))}
              </div>
              <DialogContent className="w-[min(92vw,620px)]">
                <DialogHeader>
                  <DialogTitle>执行证据</DialogTitle>
                  <DialogDescription>当前运行证据读回 · mock</DialogDescription>
                </DialogHeader>
                <Tabs value={activeEvidenceTab} onValueChange={setActiveEvidenceTab}>
                  <TabsList className="mt-4">
                    {executionEvidenceDialogItems.map((item) => (
                      <TabsTrigger key={item.key} value={item.key}>{item.label}</TabsTrigger>
                    ))}
                  </TabsList>
                  {executionEvidenceDialogItems.map((item) => (
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
          <h2 className="text-base font-semibold text-white">后续队列 · 当前项目内</h2>
          <div className="mt-4 border-y border-[#2A2A2A]">
            {executionQueueRows.map((item) => (
              <Dialog key={item.title}>
                <DialogTrigger asChild>
                  <button
                    type="button"
                    className="grid w-full cursor-pointer gap-2 border-b border-[#1F1F1F] px-1 py-3 text-left text-sm transition-colors last:border-b-0 hover:bg-[#0D0D0D] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 active:scale-[0.99] md:grid-cols-[120px_1fr_1.15fr]"
                  >
                    <span className="text-[#8A8A8A]">{item.state}</span>
                    <span className="text-[#C7C7C7]">{item.title}</span>
                    <span className="text-[#8A8A8A]">{item.note}</span>
                  </button>
                </DialogTrigger>
                <DialogContent className="w-[min(92vw,520px)]">
                  <DialogHeader>
                    <DialogTitle>{item.title}</DialogTitle>
                    <DialogDescription>{item.description}</DialogDescription>
                  </DialogHeader>
                  <ReadbackRows rows={item.rows} footer={item.footer} />
                  <div className="mt-5 flex justify-end gap-3">
                    {item.state === "待人工" ? (
                      <DialogClose asChild>
                        <Button variant="secondary" size="sm">回到工作台讨论 · mock</Button>
                      </DialogClose>
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

export function MockPageContent({ pageKey }: { pageKey: string }) {
  if (pageKey === "projects") {
    return <ProjectManagementMockPage />;
  }

  if (pageKey === "execution") {
    return <ExecutionCenterMockPage />;
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
