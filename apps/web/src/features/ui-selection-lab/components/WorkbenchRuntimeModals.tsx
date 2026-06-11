import {
  Check,
  Copy,
  Eye,
  Send,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { useState } from "react";

import {
  chartBars,
  chartLinePoints,
  costUsageMock,
  dashboardMetrics,
  gitWritePreviewMock,
  initialApprovals,
  quickActionMockContent,
  repoQueueMock,
  runRecords,
  type ApprovalItem,
} from "../mockInteractions";
import { StatusPill } from "./DataListPreview";
import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Separator,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "./ui";

// ── Dashboard Modal ────────────────────────────────────────

export function DashboardModal({ children }: { children: React.ReactNode }) {
  const path = chartLinePoints.map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x} ${y}`).join(" ");

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,520px)]">
        <DialogHeader>
          <DialogTitle>数据看板</DialogTitle>
          <DialogDescription>近 7 天运行概览与成本估算</DialogDescription>
        </DialogHeader>

        <div className="mt-5 grid grid-cols-2 gap-2">
          {dashboardMetrics.map((m) => {
            const Icon = m.icon;
            return (
              <div key={m.label} className="rounded-2xl bg-[#222222] px-3 py-3">
                <div className="mb-2 flex items-center gap-2 text-xs text-[#8A8A8A]">
                  <Icon className="h-3.5 w-3.5" />
                  {m.label}
                </div>
                <div className="text-lg font-semibold text-white">{m.value}</div>
                <div className="mt-0.5 text-xs text-[#5F5F5F]">{m.hint}</div>
              </div>
            );
          })}
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-[#2A2A2A] bg-black p-3">
            <div className="mb-3 flex items-center justify-between text-xs">
              <span className="text-white">运行趋势</span>
              <span className="text-[#8A8A8A]">7 天</span>
            </div>
            <svg viewBox="0 0 176 92" className="h-28 w-full overflow-visible" role="img" aria-label="运行趋势折线图">
              <path d="M 8 82 H 168" stroke="#2A2A2A" strokeWidth="1" />
              <path d="M 8 58 H 168" stroke="#222222" strokeWidth="1" />
              <path d="M 8 34 H 168" stroke="#222222" strokeWidth="1" />
              <path d={path} fill="none" stroke="#C7C7C7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              {chartLinePoints.map(([x, y]) => (
                <circle key={`${x}-${y}`} cx={x} cy={y} fill="#000" r="2.5" stroke="#C7C7C7" strokeWidth="1.5" />
              ))}
            </svg>
          </div>

          <div className="rounded-2xl border border-[#2A2A2A] bg-black p-3">
            <div className="mb-3 flex items-center justify-between text-xs">
              <span className="text-white">任务吞吐</span>
              <span className="text-[#8A8A8A]">7 天</span>
            </div>
            <div className="flex h-28 items-end gap-2">
              {chartBars.map((h, i) => (
                <div key={i} className="flex flex-1 items-end rounded-full bg-[#171717]">
                  <div
                    className="w-full rounded-full bg-[#C7C7C7]"
                    style={{ height: `${h}%`, opacity: 0.36 + i * 0.04 }}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <DialogClose asChild>
            <Button variant="secondary">关闭</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Approvals Modal ────────────────────────────────────────

const approvalDetails: Record<string, { rows: [string, string][]; records: string[]; footer: string }> = {
  "appr-1": {
    rows: [
      ["审批项", "商品发布与搜索规划"],
      ["项目", "二手交易平台 MVP"],
      ["当前状态", "pending"],
      ["等待原因", "需要确认搜索排序和筛选范围"],
      ["风险", "范围不清会导致后续任务拆分反复"],
      ["建议处理", "先在工作台继续澄清，再决定是否放行"],
    ],
    records: [
      "12:30 AI 主管生成规划草案",
      "12:34 等待人工确认范围",
      "12:38 当前审批仍处于待处理",
    ],
    footer: "仅展示审批读回与本地 mock 状态，不接真实后端。",
  },
  "appr-2": {
    rows: [
      ["审批项", "Workbench 两栏布局"],
      ["项目", "AI 项目主管改造"],
      ["当前状态", "pending"],
      ["等待原因", "等待用户确认视觉方向"],
      ["风险", "未确认前不应进入正式页替换"],
      ["建议处理", "仅在隐藏实验页继续推进"],
    ],
    records: [
      "09:18 生成两栏布局方案",
      "09:24 完成审查报告",
      "09:26 等待用户选择是否放行",
    ],
    footer: "仅展示审批读回与本地 mock 状态，不接真实后端。",
  },
};

export function ApprovalsModal({ children }: { children: React.ReactNode }) {
  const [approvals, setApprovals] = useState<ApprovalItem[]>(initialApprovals);
  const [selectedApprovalId, setSelectedApprovalId] = useState(initialApprovals[0]?.id ?? "");

  const selectedApproval = approvals.find((item) => item.id === selectedApprovalId);
  const detail = approvalDetails[selectedApprovalId];

  function handleAction(id: string, action: "approved" | "rejected") {
    setApprovals((prev) => prev.map((a) => (a.id === id ? { ...a, state: action } : a)));
    setSelectedApprovalId(id);
  }

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,500px)]">
        <DialogHeader>
          <DialogTitle>待审批</DialogTitle>
          <DialogDescription>mock 审批列表，不接真实后端</DialogDescription>
        </DialogHeader>

        <div
          className="mt-5 max-h-[min(52vh,420px)] overflow-y-auto"
          style={{ scrollbarWidth: "none" } as React.CSSProperties}
        >
          <style>{`.no-scrollbar::-webkit-scrollbar{display:none}`}</style>
          <div className="no-scrollbar space-y-0">
            {approvals.map((item, idx) => (
              <div key={item.id}>
                {idx > 0 && <div className="mx-0 h-px bg-[#3A3A3A]" />}
                <div
                  className={[
                    "group rounded-xl px-1 py-3 transition-colors",
                    selectedApprovalId === item.id ? "bg-[#171717]" : "hover:bg-[#222222]",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-white">{item.title}</div>
                      <div className="mt-0.5 flex items-center gap-2">
                        <span className="text-xs text-[#8A8A8A]">{item.project}</span>
                        <StatusPill status={item.status} />
                      </div>
                    </div>
                    <div className="shrink-0 text-xs text-[#5F5F5F]">{item.actionLabel}</div>
                  </div>

                  <div className="mt-2 flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => setSelectedApprovalId(item.id)}
                      className="flex items-center gap-1 rounded-full px-2.5 py-1 text-xs text-[#8A8A8A] transition-colors hover:bg-[#2C2C2C] hover:text-white"
                    >
                      <Eye className="h-3 w-3" />
                      查看
                    </button>

                    {item.state === "pending" ? (
                      <>
                        <button
                          type="button"
                          className="flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-xs text-black transition-all active:scale-[0.97]"
                          onClick={() => handleAction(item.id, "approved")}
                        >
                          <ThumbsUp className="h-3 w-3" />
                          放行
                        </button>
                        <button
                          type="button"
                          className="flex items-center gap-1 rounded-full px-2.5 py-1 text-xs text-[#8A8A8A] transition-all hover:bg-[#2C2C2C] hover:text-white active:scale-[0.97]"
                          onClick={() => handleAction(item.id, "rejected")}
                        >
                          <ThumbsDown className="h-3 w-3" />
                          驳回
                        </button>
                      </>
                    ) : (
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs ${
                          item.state === "approved"
                            ? "bg-[#1C1C1C] text-white"
                            : "bg-[#171717] text-[#8A8A8A]"
                        }`}
                      >
                        <Check className="h-3 w-3" />
                        {item.state === "approved" ? "已放行" : "已驳回"}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {selectedApproval && detail ? (
          <>
            <Separator className="my-4" />
            <div>
              <div className="text-sm font-semibold text-white">审批详情</div>
              <div className="mt-0.5 text-xs text-[#8A8A8A]">当前查看项 · mock</div>
            </div>
            <div className="mt-3 border-y border-[#2A2A2A]">
              {detail.rows.map(([label, value]) => (
                <div
                  key={label}
                  className="grid gap-2 border-b border-[#1F1F1F] px-3 py-2.5 text-sm last:border-b-0 sm:grid-cols-[100px_1fr]"
                >
                  <span className="text-[#C7C7C7]">{label}</span>
                  <span className="text-[#8A8A8A]">
                    {label === "当前状态"
                      ? selectedApproval.state === "approved"
                        ? "已放行"
                        : selectedApproval.state === "rejected"
                          ? "已驳回"
                          : "待处理"
                      : value}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-3">
              <div className="mb-1.5 text-xs font-semibold text-[#C7C7C7]">处理记录</div>
              <div className="space-y-1">
                {detail.records.map((record) => (
                  <div key={record} className="text-xs text-[#8A8A8A]">{record}</div>
                ))}
              </div>
            </div>
            <div className="mt-3 text-xs text-[#5F5F5F]">{detail.footer}</div>
          </>
        ) : null}

        <div className="mt-4 flex justify-end">
          <DialogClose asChild>
            <Button variant="secondary">关闭</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Execution Status Modal ─────────────────────────────────

const runRecordDetails: Record<string, { summary: [string, string][]; log: string; safety: [string, string][] }> = {
  "run-1": {
    summary: [
      ["任务", "Workbench UI Lab 构建检查"],
      ["状态", "passed"],
      ["执行器", "Codex"],
      ["开始时间", "12:42"],
      ["耗时", "4s"],
      ["结果", "构建检查通过"],
    ],
    log: `[12:42:10] run started: workbench-ui-lab
[12:42:11] lint check passed
[12:42:14] build passed (3.2s)
[12:42:16] diff summary: 5 files changed, +340 -12
[12:42:18] run completed: passed`,
    safety: [
      ["Runtime", "ready"],
      ["Workspace", "clean"],
      ["Git", "只读预检 · 写入关闭"],
      ["Approval", "无需审批"],
      ["Quality gate", "passed"],
      ["Budget", "正常"],
    ],
  },
  "run-2": {
    summary: [
      ["任务", "商品搜索规划执行"],
      ["状态", "partial"],
      ["执行器", "Codex"],
      ["开始时间", "12:38"],
      ["耗时", "22s"],
      ["结果", "4 项中 3 项完成，1 项待确认"],
    ],
    log: `[12:38:02] run started: search-planning
[12:38:06] task 1/4 completed: index design
[12:38:12] task 2/4 completed: search fields
[12:38:18] task 3/4 completed: filter UI
[12:38:24] task 4/4 partial: sort dimension pending
[12:38:24] run completed: partial`,
    safety: [
      ["Runtime", "ready"],
      ["Workspace", "clean"],
      ["Git", "只读预检 · 写入关闭"],
      ["Approval", "无需审批"],
      ["Quality gate", "waiting"],
      ["Budget", "正常"],
    ],
  },
  "run-3": {
    summary: [
      ["任务", "聊天消息持久化层"],
      ["状态", "running"],
      ["执行器", "Codex · Worker 2 / 3"],
      ["开始时间", "11:22"],
      ["耗时", "进行中"],
      ["结果", "等待执行完成"],
    ],
    log: `[11:22:10] run started: chat-persistence
[11:22:15] loading project context
[11:22:30] analyzing message schema
[11:23:01] generating storage layer mock`,
    safety: [
      ["Runtime", "ready"],
      ["Workspace", "clean"],
      ["Git", "只读预检 · 写入关闭"],
      ["Approval", "无需审批"],
      ["Quality gate", "waiting"],
      ["Budget", "正常"],
    ],
  },
  "run-4": {
    summary: [
      ["任务", "支付结算方案审查"],
      ["状态", "blocked"],
      ["执行器", "DeepSeek"],
      ["开始时间", "10:15"],
      ["耗时", "8s"],
      ["结果", "依赖未满足，阻塞中"],
    ],
    log: `[10:15:02] run started: payment-review
[10:15:06] loading project context
[10:15:08] blocked: missing payment provider config
[10:15:10] run completed: blocked`,
    safety: [
      ["Runtime", "ready"],
      ["Workspace", "clean"],
      ["Git", "只读预检 · 写入关闭"],
      ["Approval", "无需审批"],
      ["Quality gate", "blocked"],
      ["Budget", "正常"],
    ],
  },
  "run-5": {
    summary: [
      ["任务", "后端审核模块部署"],
      ["状态", "passed"],
      ["执行器", "Codex"],
      ["开始时间", "09:48"],
      ["耗时", "31s"],
      ["结果", "部署检查通过"],
    ],
    log: `[09:48:10] run started: audit-deploy
[09:48:15] lint check passed
[09:48:22] type check passed
[09:48:35] build passed
[09:48:41] run completed: passed`,
    safety: [
      ["Runtime", "ready"],
      ["Workspace", "clean"],
      ["Git", "只读预检 · 写入关闭"],
      ["Approval", "无需审批"],
      ["Quality gate", "passed"],
      ["Budget", "正常"],
    ],
  },
};

export function ExecutionStatusModal({ children }: { children: React.ReactNode }) {
  const [selectedRunId, setSelectedRunId] = useState(runRecords[0]?.id ?? "");
  const [copyMessage, setCopyMessage] = useState("");

  const detail = runRecordDetails[selectedRunId] ?? runRecordDetails["run-1"];

  function handleCopyLog() {
    void navigator.clipboard?.writeText(detail.log).catch(() => undefined);
    setCopyMessage("已复制日志摘要 · mock");
  }

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,540px)]">
        <DialogHeader>
          <DialogTitle>执行状态</DialogTitle>
          <DialogDescription>最近运行记录</DialogDescription>
        </DialogHeader>

        <div
          className="mt-5 max-h-[min(40vh,320px)] overflow-y-auto"
          style={{ scrollbarWidth: "none" } as React.CSSProperties}
        >
          <style>{`.no-scrollbar::-webkit-scrollbar{display:none}`}</style>
          <div className="no-scrollbar space-y-0">
            {runRecords.map((run) => (
              <button
                key={run.id}
                type="button"
                onClick={() => { setSelectedRunId(run.id); setCopyMessage(""); }}
                className={[
                  "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 active:scale-[0.99]",
                  selectedRunId === run.id ? "bg-[#171717]" : "hover:bg-[#111111]",
                ].join(" ")}
              >
                <StatusPill status={run.status} />
                <span className="min-w-0 flex-1 truncate text-sm text-white">{run.title}</span>
                <span className="shrink-0 text-xs text-[#8A8A8A]">{run.time}</span>
                <span className="shrink-0 text-xs text-[#5F5F5F] w-12 text-right">{run.duration}</span>
              </button>
            ))}
          </div>
        </div>

        <Tabs defaultValue="summary" className="mt-4">
          <TabsList>
            <TabsTrigger value="summary">摘要</TabsTrigger>
            <TabsTrigger value="log">日志</TabsTrigger>
            <TabsTrigger value="safety">安全</TabsTrigger>
          </TabsList>
          <TabsContent value="summary">
            <div className="mt-3 border-y border-[#2A2A2A]">
              {detail.summary.map(([label, value]) => (
                <div
                  key={label}
                  className="grid gap-2 border-b border-[#1F1F1F] px-3 py-2.5 text-sm last:border-b-0 sm:grid-cols-[100px_1fr]"
                >
                  <span className="text-[#C7C7C7]">{label}</span>
                  <span className="text-[#8A8A8A]">{value}</span>
                </div>
              ))}
            </div>
          </TabsContent>
          <TabsContent value="log">
            <div className="mt-3 rounded-2xl border border-[#2A2A2A] bg-black">
              <pre className="max-h-48 overflow-y-auto p-4 font-mono text-xs leading-6 text-[#C7C7C7]">
                {detail.log}
              </pre>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <Button variant="secondary" size="sm" onClick={handleCopyLog}>
                复制日志
              </Button>
              {copyMessage ? (
                <span className="text-xs text-[#8A8A8A]">{copyMessage}</span>
              ) : null}
            </div>
          </TabsContent>
          <TabsContent value="safety">
            <div className="mt-3 border-y border-[#2A2A2A]">
              {detail.safety.map(([label, value]) => (
                <div
                  key={label}
                  className="grid gap-2 border-b border-[#1F1F1F] px-3 py-2.5 text-sm last:border-b-0 sm:grid-cols-[120px_1fr]"
                >
                  <span className="text-[#C7C7C7]">{label}</span>
                  <span className="text-[#8A8A8A]">{value}</span>
                </div>
              ))}
            </div>
          </TabsContent>
        </Tabs>

        <div className="mt-5 flex justify-end">
          <DialogClose asChild>
            <Button variant="secondary">关闭</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Cost Usage Modal ───────────────────────────────────────

export function CostUsageModal({ children }: { children: React.ReactNode }) {
  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,440px)]">
        <DialogHeader>
          <DialogTitle>成本用量</DialogTitle>
          <DialogDescription>Token 消耗与 API 成本统计</DialogDescription>
        </DialogHeader>

        <div className="mt-5">
          {/* Primary metric */}
          <div className="rounded-2xl border border-[#2A2A2A] bg-[#0B0B0B] px-4 py-4">
            <div className="text-xs text-[#8A8A8A]">本周成本</div>
            <div className="mt-1 text-[30px] font-semibold leading-none text-white">{costUsageMock.weekCost}</div>
          </div>

          {/* Secondary metrics */}
          <div className="mt-3 grid grid-cols-2 gap-3">
            <div className="rounded-2xl border border-[#2A2A2A] bg-[#0B0B0B] px-4 py-3">
              <div className="text-xs text-[#8A8A8A]">今日 Token</div>
              <div className="mt-1 text-[15px] font-semibold text-white">{costUsageMock.todayTokens}</div>
            </div>
            <div className="rounded-2xl border border-[#2A2A2A] bg-[#0B0B0B] px-4 py-3">
              <div className="text-xs text-[#8A8A8A]">主要模型</div>
              <div className="mt-1 text-[15px] font-semibold text-white">{costUsageMock.primaryModel}</div>
            </div>
          </div>

          {/* Cost trend */}
          <div className="mt-3 rounded-2xl border border-[#2A2A2A] bg-[#0B0B0B] p-3">
            <div className="mb-3 flex items-center justify-between text-xs">
              <span className="text-white">成本趋势</span>
              <span className="text-[#8A8A8A]">7 天</span>
            </div>
            <div className="flex h-20 items-end gap-2">
              {costUsageMock.trend.map((h, i) => (
                <div key={i} className="flex flex-1 items-end rounded-full bg-[#171717]">
                  <div
                    className="w-full rounded-full bg-[#C7C7C7]"
                    style={{ height: `${(h / 60) * 100}%`, opacity: 0.4 + i * 0.05 }}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <DialogClose asChild>
            <Button variant="secondary">关闭</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Repository Queue Modal ──────────────────────────────────

function QueueStatusPill({ status }: { status: string }) {
  const style =
    status === "等待审查"
      ? "bg-[#2C2C2C] text-white border-transparent"
      : status === "待合入"
        ? "bg-transparent text-[#C7C7C7] border-[#3A3A3A]"
        : "bg-[#171717] text-[#C7C7C7] border-[#2A2A2A]";
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] ${style}`}
    >
      {status}
    </span>
  );
}

export function RepositoryQueueModal({ children }: { children: React.ReactNode }) {
  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,460px)]">
        <DialogHeader>
          <DialogTitle>仓库队列</DialogTitle>
          <DialogDescription>待处理仓库任务与变更队列</DialogDescription>
        </DialogHeader>

        <div className="mt-5 space-y-4">
          {/* 待审查 */}
          <div>
            <div className="mb-2 text-xs font-medium text-[#8A8A8A]">待审查变更</div>
            <div className="space-y-0">
              {repoQueueMock.pendingReview.map((item, idx) => (
                <div key={item.branch}>
                  {idx > 0 && <div className="mx-0 h-px bg-[#3A3A3A]" />}
                  <div className="flex items-center gap-3 rounded-xl px-1 py-2.5 transition-colors hover:bg-[#222222]">
                    <span className="min-w-0 flex-1 truncate text-sm text-white">{item.branch}</span>
                    <QueueStatusPill status={item.status} />
                    <span className="shrink-0 text-xs text-[#5F5F5F]">{item.author}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 待合入 */}
          <div>
            <div className="mb-2 text-xs font-medium text-[#8A8A8A]">待合入分支</div>
            <div className="space-y-0">
              {repoQueueMock.pendingMerge.map((item, idx) => (
                <div key={item.branch}>
                  {idx > 0 && <div className="mx-0 h-px bg-[#3A3A3A]" />}
                  <div className="flex items-center gap-3 rounded-xl px-1 py-2.5 transition-colors hover:bg-[#222222]">
                    <span className="min-w-0 flex-1 truncate text-sm text-white">{item.branch}</span>
                    <QueueStatusPill status={item.status} />
                    <span className="shrink-0 text-xs text-[#5F5F5F]">{item.author}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 待提交草稿 */}
          <div>
            <div className="mb-2 text-xs font-medium text-[#8A8A8A]">待提交草稿</div>
            {repoQueueMock.pendingDraft.map((draft) => (
              <div key={draft.message} className="rounded-xl bg-[#0B0B0B] px-3 py-3">
                <div className="text-sm text-white">{draft.message}</div>
                <div className="mt-1 text-xs text-[#8A8A8A]">
                  {draft.changedFiles} files, +{draft.additions} −{draft.deletions}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <DialogClose asChild>
            <Button variant="secondary">关闭</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Git Write Preview Modal ─────────────────────────────────

function DiffLine({ line }: { line: string }) {
  const isAdd = line.startsWith("+");
  const isDel = line.startsWith("-");
  const textColor = isAdd ? "text-[#C7C7C7]" : isDel ? "text-[#6F6F6F]" : "text-[#8A8A8A]";
  const borderLeft = isAdd
    ? "border-l-2 border-l-[#5F5F5F]"
    : isDel
      ? "border-l-2 border-l-[#3A3A3A]"
      : "border-l-2 border-l-transparent";
  return (
    <div className={`pl-2 font-mono text-xs leading-5 ${textColor} ${borderLeft}`}>
      {line}
    </div>
  );
}

export function GitWritePreviewModal({ children }: { children: React.ReactNode }) {
  const diffLines = gitWritePreviewMock.diffSummary.split("\n");
  const totalChanged = gitWritePreviewMock.changes.length;

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,500px)]">
        <DialogHeader>
          <DialogTitle>Git 写入预览</DialogTitle>
          <DialogDescription>预览待提交的代码变更</DialogDescription>
        </DialogHeader>

        <div className="mt-5 space-y-3">
          <div>
            <div className="mb-2 text-xs font-medium text-[#8A8A8A]">变更文件</div>
            <div className="space-y-0">
              {gitWritePreviewMock.changes.map((change, idx) => (
                <div key={change.file}>
                  {idx > 0 && <div className="mx-0 h-px bg-[#3A3A3A]" />}
                  <div className="flex items-center gap-3 rounded-xl px-1 py-2.5 transition-colors hover:bg-[#222222]">
                    <span className="min-w-0 flex-1 truncate font-mono text-xs text-[#C7C7C7]">{change.file}</span>
                    <span className="shrink-0 text-xs text-[#8A8A8A]">
                      +{change.additions} −{change.deletions}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-medium text-[#8A8A8A]">提交信息</div>
            <div className="rounded-xl bg-[#0B0B0B] px-3 py-2.5 font-mono text-xs text-white">
              {gitWritePreviewMock.commitMessage}
            </div>
          </div>

          {/* Diff with code block top bar */}
          <div>
            <div className="mb-2 text-xs font-medium text-[#8A8A8A]">Diff 摘要</div>
            <div className="overflow-hidden rounded-2xl border border-[#2A2A2A]">
              {/* top bar */}
              <div className="flex h-[36px] items-center justify-between border-b border-[#2A2A2A] bg-[#0B0B0B] px-3">
                <span className="text-xs text-[#C7C7C7]">Diff 摘要</span>
                <span className="text-xs text-[#8A8A8A]">{totalChanged} files changed</span>
              </div>
              {/* code content */}
              <div className="max-h-40 overflow-y-auto bg-black">
                <pre className="p-3 font-mono text-xs leading-5">
                  {diffLines.map((line, i) => (
                    <DiffLine key={i} line={line} />
                  ))}
                </pre>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-[#3A3A3A] bg-[#0B0B0B] px-3 py-2 text-xs text-[#8A8A8A]">
            {gitWritePreviewMock.limitationNote}
          </div>
        </div>

        <div className="mt-4 flex justify-end">
          <DialogClose asChild>
            <Button variant="secondary">关闭</Button>
          </DialogClose>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Quick Action: Create Project Plan ──────────────────────

export function CreatePlanModal({ children }: { children: React.ReactNode }) {
  const [submitted, setSubmitted] = useState(false);

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,480px)]">
        <DialogHeader>
          <DialogTitle>创建项目计划</DialogTitle>
          <DialogDescription>描述目标与约束，生成任务队列</DialogDescription>
        </DialogHeader>

        <div className="mt-5 space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-[#C7C7C7]">项目目标</label>
            <textarea
              className="flex min-h-[72px] w-full resize-none rounded-2xl border border-[#2A2A2A] bg-[#171717] px-4 py-3 text-sm text-white outline-none transition-colors placeholder:text-[#8A8A8A] focus:border-[#3A3A3A] focus:ring-2 focus:ring-white/10"
              defaultValue={quickActionMockContent.createPlan.projectGoal}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-[#C7C7C7]">约束条件</label>
            <textarea
              className="flex min-h-[56px] w-full resize-none rounded-2xl border border-[#2A2A2A] bg-[#171717] px-4 py-3 text-sm text-white outline-none transition-colors placeholder:text-[#8A8A8A] focus:border-[#3A3A3A] focus:ring-2 focus:ring-white/10"
              defaultValue={quickActionMockContent.createPlan.constraints}
            />
          </div>

          <Button
            className="w-full"
            onClick={() => setSubmitted(true)}
          >
            <Send className="h-4 w-4" />
            生成任务队列
          </Button>

          {submitted && (
            <div className="rounded-2xl border border-[#2A2A2A] bg-black px-4 py-3 text-sm leading-6 text-[#C7C7C7]">
              已生成 4 个任务并添加到 mock 会话。切换到「项目会话」查看。
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Quick Action: Review Execution Result ──────────────────

export function ReviewResultModal({ children }: { children: React.ReactNode }) {
  const [reviewed, setReviewed] = useState(false);

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,500px)]">
        <DialogHeader>
          <DialogTitle>审查执行结果</DialogTitle>
          <DialogDescription>粘贴执行结果，点击审查判断 Pass / Partial</DialogDescription>
        </DialogHeader>

        <div className="mt-5 space-y-4">
          <textarea
            className="flex min-h-[140px] w-full resize-none rounded-2xl border border-[#2A2A2A] bg-[#171717] px-4 py-3 font-mono text-sm text-white outline-none transition-colors placeholder:text-[#8A8A8A] focus:border-[#3A3A3A] focus:ring-2 focus:ring-white/10"
            placeholder={quickActionMockContent.reviewResult.placeholder}
          />

          <Button className="w-full" onClick={() => setReviewed(true)}>
            <Eye className="h-4 w-4" />
            审查
          </Button>

          {reviewed && (
            <div className="rounded-2xl border border-[#2A2A2A] bg-black px-4 py-3">
              <div className="flex items-center gap-2 text-sm">
                <StatusPill status="passed" />
                <span className="text-white">审查通过</span>
              </div>
              <p className="mt-2 text-sm leading-6 text-[#C7C7C7]">
                构建检查通过，diff 变更符合预期。建议放行至下一步执行。
              </p>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Quick Action: Advance Next Step ────────────────────────

export function AdvanceNextModal({ children }: { children: React.ReactNode }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(quickActionMockContent.advanceNext.instruction).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,520px)]">
        <DialogHeader>
          <DialogTitle>推进下一步</DialogTitle>
          <DialogDescription>下一条最小执行指令预览</DialogDescription>
        </DialogHeader>

        <div className="mt-5">
          <div className="rounded-2xl border border-[#2A2A2A] bg-black p-4">
            <pre className="whitespace-pre-wrap font-mono text-xs leading-6 text-[#C7C7C7]">
              {quickActionMockContent.advanceNext.instruction}
            </pre>
          </div>

          <Button className="mt-4 w-full" variant="secondary" onClick={handleCopy}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? "已复制" : "复制指令"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
