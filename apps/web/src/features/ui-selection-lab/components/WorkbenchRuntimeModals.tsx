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
  mockExecutionLog,
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

        <div
          className="mt-5 max-h-[min(52vh,420px)] overflow-y-auto"
          style={{ scrollbarWidth: "none" } as React.CSSProperties}
        >
          <style>{`.no-scrollbar::-webkit-scrollbar{display:none}`}</style>
          <div className="no-scrollbar space-y-0">
            {approvals.map((item, idx) => (
              <div key={item.id}>
                {idx > 0 && <div className="mx-0 h-px bg-[#3A3A3A]" />}
                <div className="group rounded-xl px-1 py-3 transition-colors hover:bg-[#222222]">
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
                    <button className="flex items-center gap-1 rounded-full px-2.5 py-1 text-xs text-[#8A8A8A] transition-colors hover:bg-[#2C2C2C] hover:text-white">
                      <Eye className="h-3 w-3" />
                      查看
                    </button>

                    {item.state === "pending" ? (
                      <>
                        <button
                          className="flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-xs text-black transition-all active:scale-[0.97]"
                          onClick={() => handleAction(item.id, "approved")}
                        >
                          <ThumbsUp className="h-3 w-3" />
                          放行
                        </button>
                        <button
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

export function ExecutionStatusModal({ children }: { children: React.ReactNode }) {
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
              <div
                key={run.id}
                className="flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-[#222222]"
              >
                <StatusPill status={run.status} />
                <span className="min-w-0 flex-1 truncate text-sm text-white">{run.title}</span>
                <span className="shrink-0 text-xs text-[#8A8A8A]">{run.time}</span>
                <span className="shrink-0 text-xs text-[#5F5F5F] w-12 text-right">{run.duration}</span>
              </div>
            ))}
          </div>
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

        <div className="mt-5 grid grid-cols-3 gap-3">
          <div className="rounded-2xl bg-[#222222] px-3 py-3">
            <div className="text-xs text-[#8A8A8A]">今日 Token</div>
            <div className="mt-1.5 text-lg font-semibold text-white">{costUsageMock.todayTokens}</div>
          </div>
          <div className="rounded-2xl bg-[#222222] px-3 py-3">
            <div className="text-xs text-[#8A8A8A]">本周成本</div>
            <div className="mt-1.5 text-lg font-semibold text-white">{costUsageMock.weekCost}</div>
          </div>
          <div className="rounded-2xl bg-[#222222] px-3 py-3">
            <div className="text-xs text-[#8A8A8A]">主要模型</div>
            <div className="mt-1.5 text-lg font-semibold text-white">{costUsageMock.primaryModel}</div>
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-[#2A2A2A] bg-black p-3">
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
          <div>
            <div className="mb-2 text-xs font-medium text-[#8A8A8A]">待审查变更</div>
            <div className="space-y-0">
              {repoQueueMock.pendingReview.map((item, idx) => (
                <div key={item.branch}>
                  {idx > 0 && <div className="mx-0 h-px bg-[#3A3A3A]" />}
                  <div className="flex items-center gap-3 rounded-xl px-1 py-2.5 transition-colors hover:bg-[#222222]">
                    <span className="min-w-0 flex-1 truncate text-sm text-white">{item.branch}</span>
                    <span className="shrink-0 text-xs text-[#8A8A8A]">{item.status}</span>
                    <span className="shrink-0 text-xs text-[#5F5F5F]">{item.author}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-medium text-[#8A8A8A]">待提交草稿</div>
            {repoQueueMock.pendingDraft.map((draft) => (
              <div key={draft.message} className="rounded-xl bg-[#222222] px-3 py-3">
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

export function GitWritePreviewModal({ children }: { children: React.ReactNode }) {
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
            <div className="rounded-xl bg-[#222222] px-3 py-2.5 font-mono text-xs text-white">
              {gitWritePreviewMock.commitMessage}
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-medium text-[#8A8A8A]">Diff 摘要</div>
            <div className="rounded-2xl border border-[#2A2A2A] bg-black">
              <pre className="max-h-36 overflow-y-auto p-3 font-mono text-xs leading-5 text-[#C7C7C7]">
                {gitWritePreviewMock.diffSummary}
              </pre>
            </div>
          </div>

          <div className="rounded-xl border border-[#3A3A3A] bg-[#222222] px-3 py-2 text-xs text-[#8A8A8A]">
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
