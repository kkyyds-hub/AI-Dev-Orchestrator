import { useEffect } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import type { ConsoleBudget, ConsoleTask } from "../../features/console/types";
import type { StreamConnectionStatus } from "../../features/events/types";
import { formatDateTime, formatNullableCurrencyUsd } from "../../lib/format";
import { mapRunStatusTone, mapTaskStatusTone } from "../../lib/status";

type RightSidebarOverviewSectionProps = {
  isOpen: boolean;
  onClose: () => void;
  requestedRunId: string | null;
  selectedTask: ConsoleTask | null;
  budget: ConsoleBudget | null;
  realtimeStatus: StreamConnectionStatus;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToRun?: (runId: string, taskId: string) => void;
  onNavigateToProjectDrilldown: (detail: {
    source: "home_latest_run" | "home_manual_run";
    taskId: string;
    runId?: string | null;
  }) => void;
};

const actionButtonClass =
  "rounded-md border border-[#333333] bg-transparent px-3.5 py-2 text-sm font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f] hover:text-zinc-50 disabled:cursor-not-allowed disabled:text-zinc-700";
const primaryActionButtonClass =
  "rounded-md border border-zinc-200 bg-transparent px-3.5 py-2 text-sm font-medium text-zinc-100 transition hover:bg-[#2f2f2f] disabled:cursor-not-allowed disabled:border-[#333333] disabled:text-zinc-700";

export function RightSidebarOverviewSection(props: RightSidebarOverviewSectionProps) {
  const { isOpen, onClose } = props;
  const selectedTask = props.selectedTask;
  const latestRun = selectedTask?.latest_run ?? null;
  const activeRunId = props.requestedRunId ?? latestRun?.id ?? null;
  const acceptancePreview = selectedTask?.acceptance_criteria.slice(0, 3) ?? [];

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      data-testid="home-right-sidebar-overview-section"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3 backdrop-blur-[6px] sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="workbench-task-detail-modal-title"
      onClick={props.onClose}
      style={{ animation: "workbench-overlay-in 220ms cubic-bezier(0.16, 1, 0.3, 1) both" }}
    >
      <style>
        {`
          @keyframes workbench-overlay-in {
            from { opacity: 0; }
            to { opacity: 1; }
          }

          @keyframes workbench-detail-modal-in {
            from {
              opacity: 0;
              transform: translateY(14px) scale(0.98);
            }
            to {
              opacity: 1;
              transform: translateY(0) scale(1);
            }
          }
        `}
      </style>
      <div
        className="flex max-h-[calc(100vh-2rem)] w-full max-w-3xl min-w-0 flex-col overflow-hidden border border-[#333333] bg-[#111111] sm:max-h-[calc(100vh-3rem)]"
        onClick={(event) => event.stopPropagation()}
        style={{ animation: "workbench-detail-modal-in 260ms cubic-bezier(0.16, 1, 0.3, 1) both" }}
      >
        <div className="border-b border-[#333333] px-5 py-4 sm:px-6">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-[#333333] px-3 py-1 text-xs font-medium tracking-[0.16em] text-zinc-500">
              任务摘要
            </span>
            {selectedTask ? <StatusBadge label={formatTaskStatusLabel(selectedTask.status)} tone={mapTaskStatusTone(selectedTask.status)} /> : null}
          </div>
          <h2 id="workbench-task-detail-modal-title" className="mt-3 truncate text-xl font-semibold tracking-tight text-zinc-100">
            {selectedTask?.title ?? "未选择任务"}
          </h2>
          <p className="mt-1 text-sm text-zinc-500">点击遮罩或按 Esc 关闭。</p>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5 sm:p-6">
          {selectedTask ? (
            <div className="space-y-4">
              <div className="grid gap-2 sm:grid-cols-4">
                <SummaryItem label="优先级" value={`P${selectedTask.priority}`} />
                <SummaryItem label="风险" value={selectedTask.risk_level || "-"} />
                <SummaryItem label="负责人" value={selectedTask.owner_role_code ?? "未分配"} />
                <SummaryItem label="人工状态" value={selectedTask.human_status || "-"} />
              </div>

              <section className="border-b border-[#333333] pb-4">
                <div className="text-xs font-medium tracking-[0.16em] text-zinc-500">输入摘要</div>
                <p className="mt-2 text-sm leading-6 text-zinc-300">{selectedTask.input_summary || "暂无摘要"}</p>
              </section>

              <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
                <section className="border-b border-[#333333] pb-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-xs font-medium tracking-[0.16em] text-zinc-500">最近运行</div>
                    {latestRun ? <StatusBadge label={formatRunStatusLabel(latestRun.status)} tone={mapRunStatusTone(latestRun.status)} /> : null}
                  </div>
                  {latestRun ? (
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      <SummaryItem label="运行 ID" value={activeRunId ?? "-"} />
                      <SummaryItem label="费用" value={formatNullableCurrencyUsd(latestRun.estimated_cost)} />
                      <SummaryItem label="创建" value={formatDateTime(latestRun.created_at)} />
                      <SummaryItem label="完成" value={formatDateTime(latestRun.finished_at)} />
                      <SummaryItem label="质检" value={formatQualityGate(latestRun.quality_gate_passed)} />
                      <SummaryItem label="失败分类" value={latestRun.failure_category ?? "-"} />
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-zinc-500">暂无运行记录。</p>
                  )}
                </section>

                <section className="border-b border-[#333333] pb-4">
                  <div className="text-xs font-medium tracking-[0.16em] text-zinc-500">运行环境</div>
                  <div className="mt-3 space-y-2">
                    <SummaryItem label="实时连接" value={formatRealtimeStatus(props.realtimeStatus)} />
                    <SummaryItem label="预算压力" value={props.budget?.pressure_level ?? "-"} />
                    <SummaryItem label="预算策略" value={props.budget?.strategy_label ?? "-"} />
                  </div>
                </section>
              </div>

              <section className="border-b border-[#333333] pb-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-xs font-medium tracking-[0.16em] text-zinc-500">验收要点</div>
                  <span className="text-xs text-zinc-600">{selectedTask.acceptance_criteria.length} 项</span>
                </div>
                {acceptancePreview.length ? (
                  <ul className="mt-3 space-y-2 text-sm leading-6 text-zinc-300">
                    {acceptancePreview.map((item) => (
                      <li key={item} className="flex gap-2">
                        <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-500" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-3 text-sm text-zinc-500">暂无验收要点。</p>
                )}
              </section>

              <details className="group rounded-xl border border-[#333333] bg-transparent p-4">
                <summary className="cursor-pointer list-none text-sm font-medium text-zinc-200 outline-none transition hover:text-zinc-50">
                  <span className="inline-flex items-center gap-2">
                    <span className="transition group-open:rotate-90">›</span>
                    完整详情
                  </span>
                </summary>
                <div className="mt-4 space-y-4 border-t border-[#333333] pt-4">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <SummaryItem label="任务 ID" value={selectedTask.id} />
                    <SummaryItem label="更新时间" value={formatDateTime(selectedTask.updated_at)} />
                    <SummaryItem label="运行 ID" value={activeRunId ?? "-"} />
                    <SummaryItem label="最近运行状态" value={latestRun ? formatRunStatusLabel(latestRun.status) : "-"} />
                  </div>
                  {selectedTask.acceptance_criteria.length ? (
                    <div>
                      <div className="text-xs font-medium tracking-[0.16em] text-zinc-500">全部验收条件</div>
                      <ul className="mt-3 space-y-2 text-sm leading-6 text-zinc-300">
                        {selectedTask.acceptance_criteria.map((item) => (
                          <li key={item} className="flex gap-2">
                            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-600" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </details>
            </div>
          ) : (
            <div className="border border-dashed border-[#3a3a3a] px-4 py-6 text-sm leading-6 text-zinc-400">
              请先在任务队列中选择一个任务。
            </div>
          )}
        </div>

        <div className="flex flex-wrap justify-end gap-2 border-t border-[#333333] px-5 py-4 sm:px-6">
          <button
            type="button"
            data-testid="workbench-modal-open-task"
            disabled={!selectedTask || !props.onNavigateToTask}
            onClick={() => (selectedTask ? props.onNavigateToTask?.(selectedTask.id, { runId: activeRunId }) : undefined)}
            className={primaryActionButtonClass}
          >
            打开任务页
          </button>
          <button
            type="button"
            data-testid="workbench-modal-open-run"
            disabled={!selectedTask || !latestRun?.id || !props.onNavigateToRun}
            onClick={() => (selectedTask && latestRun?.id ? props.onNavigateToRun?.(latestRun.id, selectedTask.id) : undefined)}
            className={actionButtonClass}
          >
            打开运行页
          </button>
          <button
            type="button"
            data-testid="workbench-modal-drilldown"
            disabled={!selectedTask || !latestRun}
            onClick={() =>
              selectedTask
                ? props.onNavigateToProjectDrilldown({ source: "home_latest_run", taskId: selectedTask.id, runId: activeRunId })
                : undefined
            }
            className={actionButtonClass}
          >
            查看项目上下文
          </button>
        </div>
      </div>
    </div>
  );
}

function SummaryItem(props: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-l border-[#333333] px-4 py-2">
      <div className="text-[11px] tracking-[0.14em] text-zinc-600">{props.label}</div>
      <div className="mt-1 truncate text-sm font-medium text-zinc-200">{props.value}</div>
    </div>
  );
}

function formatTaskStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "待处理",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    blocked: "已阻断",
    paused: "已暂停",
    waiting_human: "等待人工",
  };

  return labels[status] ?? status;
}

function formatRunStatusLabel(status: string) {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    succeeded: "成功",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
  };

  return labels[status] ?? status;
}

function formatQualityGate(value: boolean | null) {
  if (value === true) {
    return "通过";
  }

  if (value === false) {
    return "阻断";
  }

  return "未知";
}

function formatRealtimeStatus(status: StreamConnectionStatus) {
  switch (status) {
    case "open":
      return "已连接";
    case "reconnecting":
      return "重连中";
    case "unsupported":
      return "不可用";
    default:
      return "连接中";
  }
}
