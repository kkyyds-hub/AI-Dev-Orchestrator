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
  dashboardMetrics,
  initialApprovals,
  mockExecutionLog,
  moreTools,
  quickActionMockContent,
  runRecords,
  type ApprovalItem,
  type ToolEntry,
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
              <div key={m.label} className="rounded-2xl bg-[#1F1F1F] px-3 py-3">
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
              <path d="M 8 58 H 168" stroke="#1F1F1F" strokeWidth="1" />
              <path d="M 8 34 H 168" stroke="#1F1F1F" strokeWidth="1" />
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
                <div key={i} className="flex flex-1 items-end rounded-full bg-[#1A1A1A]">
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

export function ApprovalsModal({ children }: { children: React.ReactNode }) {
  const [approvals, setApprovals] = useState<ApprovalItem[]>(initialApprovals);

  function handleAction(id: string, action: "approved" | "rejected") {
    setApprovals((prev) => prev.map((a) => (a.id === id ? { ...a, state: action } : a)));
  }

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,500px)]">
        <DialogHeader>
          <DialogTitle>待审批</DialogTitle>
          <DialogDescription>mock 审批列表，不接真实后端</DialogDescription>
        </DialogHeader>

        <div className="mt-5 space-y-3">
          {approvals.map((item) => (
            <div
              key={item.id}
              className="rounded-2xl border border-[#2A2A2A] bg-black p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-white">{item.title}</div>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-xs text-[#8A8A8A]">{item.project}</span>
                    <StatusPill status={item.status} />
                  </div>
                </div>
                <div className="shrink-0 text-xs text-[#8A8A8A]">{item.actionLabel}</div>
              </div>

              <div className="mt-3 flex items-center gap-2">
                <button
                  className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-[#C7C7C7] transition-colors hover:bg-[#1F1F1F] hover:text-white"
                  onClick={() => {}}
                >
                  <Eye className="h-3.5 w-3.5" />
                  查看
                </button>

                {item.state === "pending" ? (
                  <>
                    <button
                      className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-xs text-black transition-all active:scale-[0.97]"
                      onClick={() => handleAction(item.id, "approved")}
                    >
                      <ThumbsUp className="h-3.5 w-3.5" />
                      放行
                    </button>
                    <button
                      className="flex items-center gap-1.5 rounded-full bg-[#2A2A2A] px-3 py-1.5 text-xs text-[#C7C7C7] transition-all hover:bg-[#3A3A3A] active:scale-[0.97]"
                      onClick={() => handleAction(item.id, "rejected")}
                    >
                      <ThumbsDown className="h-3.5 w-3.5" />
                      驳回
                    </button>
                  </>
                ) : (
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs ${
                      item.state === "approved"
                        ? "bg-[#303030] text-white"
                        : "bg-[#1A1A1A] text-[#8A8A8A]"
                    }`}
                  >
                    <Check className="h-3.5 w-3.5" />
                    {item.state === "approved" ? "已放行" : "已驳回"}
                  </span>
                )}
              </div>
            </div>
          ))}
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

// ── Execution Status Modal ─────────────────────────────────

export function ExecutionStatusModal({ children }: { children: React.ReactNode }) {
  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,540px)]">
        <DialogHeader>
          <DialogTitle>执行状态</DialogTitle>
          <DialogDescription>最近运行记录与状态样张</DialogDescription>
        </DialogHeader>

        <div className="mt-4 flex flex-wrap gap-2">
          {(["running", "partial", "passed", "blocked", "pending"] as const).map((s) => (
            <StatusPill key={s} status={s} />
          ))}
        </div>

        <div className="mt-4 space-y-1">
          {runRecords.map((run) => (
            <div
              key={run.id}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-[#1F1F1F]"
            >
              <StatusPill status={run.status} />
              <span className="min-w-0 flex-1 truncate text-sm text-white">{run.title}</span>
              <span className="shrink-0 text-xs text-[#8A8A8A]">{run.time}</span>
              <span className="shrink-0 text-xs text-[#5F5F5F] w-12 text-right">{run.duration}</span>
            </div>
          ))}
        </div>

        <div className="mt-4 rounded-2xl border border-[#2A2A2A] bg-black">
          <pre className="max-h-48 overflow-y-auto p-4 font-mono text-xs leading-6 text-[#C7C7C7]">
            {mockExecutionLog}
          </pre>
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

// ── More Tools Modal ───────────────────────────────────────

export function MoreToolsModal({ children }: { children: React.ReactNode }) {
  const [activeTool, setActiveTool] = useState<ToolEntry | null>(null);

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="w-[min(92vw,480px)]">
        <DialogHeader>
          <DialogTitle>{activeTool ? activeTool.label : "更多工具"}</DialogTitle>
          <DialogDescription>
            {activeTool ? activeTool.description : "选择工具入口查看 mock 内容"}
          </DialogDescription>
        </DialogHeader>

        {activeTool ? (
          <div className="mt-5">
            <button
              className="mb-4 text-xs text-[#8A8A8A] transition-colors hover:text-white"
              onClick={() => setActiveTool(null)}
            >
              ← 返回工具列表
            </button>
            <div className="rounded-2xl border border-[#2A2A2A] bg-black p-4">
              <p className="text-sm leading-6 text-[#C7C7C7]">
                这是 <span className="text-white">{activeTool.label}</span> 的占位内容。
              </p>
              <p className="mt-2 text-sm text-[#8A8A8A]">
                当前为实验页 mock，不接真实后端。正式接入后将展示实际数据。
              </p>
            </div>
          </div>
        ) : (
          <div className="mt-4 space-y-1">
            {moreTools.map((tool) => {
              const Icon = tool.icon;
              return (
                <button
                  key={tool.label}
                  className="flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left transition-colors hover:bg-[#1F1F1F] active:scale-[0.98]"
                  onClick={() => setActiveTool(tool)}
                >
                  <Icon className="h-4 w-4 shrink-0 text-[#8A8A8A]" />
                  <span className="min-w-0 flex-1 text-sm text-white">{tool.label}</span>
                  <span className="text-xs text-[#5F5F5F]">{tool.description}</span>
                </button>
              );
            })}
          </div>
        )}

        <div className="mt-5 flex justify-end">
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
              className="flex min-h-[72px] w-full resize-none rounded-2xl border border-[#2A2A2A] bg-[#1A1A1A] px-4 py-3 text-sm text-white outline-none transition-colors placeholder:text-[#8A8A8A] focus:border-[#3A3A3A] focus:ring-2 focus:ring-white/10"
              defaultValue={quickActionMockContent.createPlan.projectGoal}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-[#C7C7C7]">约束条件</label>
            <textarea
              className="flex min-h-[56px] w-full resize-none rounded-2xl border border-[#2A2A2A] bg-[#1A1A1A] px-4 py-3 text-sm text-white outline-none transition-colors placeholder:text-[#8A8A8A] focus:border-[#3A3A3A] focus:ring-2 focus:ring-white/10"
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
            className="flex min-h-[140px] w-full resize-none rounded-2xl border border-[#2A2A2A] bg-[#1A1A1A] px-4 py-3 font-mono text-sm text-white outline-none transition-colors placeholder:text-[#8A8A8A] focus:border-[#3A3A3A] focus:ring-2 focus:ring-white/10"
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
