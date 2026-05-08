import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import type { ConsoleTask } from "../../features/console/types";
import { formatDateTime, formatNullableCurrencyUsd } from "../../lib/format";
import { mapRunStatusTone, mapTaskStatusTone } from "../../lib/status";

type TaskTableSectionProps = {
  tasks: ConsoleTask[];
  selectedTaskId: string | null;
  overviewIsLoading: boolean;
  overviewIsError: boolean;
  onSelectTask: (taskId: string) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToRun?: (runId: string, taskId: string) => void;
  onNavigateToProjectDrilldown: (detail: {
    source: "home_latest_run" | "home_manual_run";
    taskId: string;
    runId?: string | null;
  }) => void;
};

const TASKS_PER_PAGE = 5;
const tableActionButtonClass =
  "rounded-md border border-transparent px-2.5 py-1 text-xs font-medium text-zinc-400 transition hover:bg-white/[0.06] hover:text-zinc-100";
const subtleActionButtonClass =
  "rounded-md border border-[#333333] bg-transparent px-2.5 py-1 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]";

export function TaskTableSection(props: TaskTableSectionProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(props.tasks.length / TASKS_PER_PAGE));

  useEffect(() => {
    setCurrentPage((page) => Math.min(page, totalPages));
  }, [totalPages]);

  const pagedTasks = useMemo(() => {
    const startIndex = (currentPage - 1) * TASKS_PER_PAGE;
    return props.tasks.slice(startIndex, startIndex + TASKS_PER_PAGE);
  }, [currentPage, props.tasks]);

  const pageStart = props.tasks.length ? (currentPage - 1) * TASKS_PER_PAGE + 1 : 0;
  const pageEnd = Math.min(currentPage * TASKS_PER_PAGE, props.tasks.length);

  return (
    <section
      data-testid="home-task-table-section"
      className="space-y-3"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">任务队列</h2>
          <p className="mt-1 text-sm text-zinc-500">每页 5 条，点击任务查看摘要。</p>
        </div>
        <StatusBadge
          label={props.overviewIsLoading ? "加载中" : props.overviewIsError ? "加载失败" : "已同步"}
          tone={props.overviewIsLoading ? "warning" : props.overviewIsError ? "danger" : "neutral"}
        />
      </div>

      {props.overviewIsError ? (
        <div className="rounded-xl border border-rose-900/60 bg-rose-950/20 p-4 text-sm text-rose-100">
          工作台数据加载失败。请确认后端服务已启动，并且 GET /tasks/console 可访问。
        </div>
      ) : (
        <div className="border-y border-[#333333]">
          <div className="divide-y divide-[#333333]">
            {pagedTasks.length ? (
              pagedTasks.map((task) => {
                const isSelected = props.selectedTaskId === task.id;
                const latestRun = task.latest_run;

                return (
                  <article
                    key={task.id}
                    data-testid={`home-task-row-${task.id}`}
                    role="button"
                    tabIndex={0}
                    onClick={() => props.onSelectTask(task.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        props.onSelectTask(task.id);
                      }
                    }}
                    className={`grid min-h-[84px] cursor-pointer gap-3 px-2 py-4 transition sm:px-3 lg:grid-cols-[minmax(0,1.7fr)_minmax(210px,1fr)_116px_190px] lg:items-center ${
                      isSelected ? "rounded-md bg-[#2b2b2b]" : "hover:rounded-md hover:bg-[#2a2a2a]"
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="flex min-w-0 items-center gap-2">
                        <div className="truncate text-sm font-medium text-zinc-100">{task.title}</div>
                        <span
                          className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                            isSelected
                              ? "border-zinc-500 text-zinc-100"
                              : "border-[#333333] text-zinc-600"
                          }`}
                        >
                          {isSelected ? "已选" : "选择"}
                        </span>
                      </div>
                      <div className="mt-1 truncate text-xs leading-5 text-zinc-500">
                        P{task.priority} · {task.input_summary}
                      </div>
                    </div>

                    <div className="min-w-0 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge label={formatTaskStatusLabel(task.status)} tone={mapTaskStatusTone(task.status)} />
                        {latestRun ? <StatusBadge label={formatRunStatusLabel(latestRun.status)} tone={mapRunStatusTone(latestRun.status)} /> : null}
                      </div>
                      <div className="truncate text-xs text-zinc-500">
                        {latestRun
                          ? `${buildRunMicroSummary(latestRun)} · ${formatDateTime(latestRun.created_at)}`
                          : "暂无运行"}
                      </div>
                    </div>

                    <div data-testid={`home-task-estimated-cost-${task.id}`} className="font-mono text-sm text-zinc-300">
                      {latestRun ? formatNullableCurrencyUsd(latestRun.estimated_cost) : "-"}
                    </div>

                    <div className="flex flex-wrap gap-1.5 lg:justify-end" onClick={(event) => event.stopPropagation()}>
                      {props.onNavigateToTask ? (
                        <button
                          type="button"
                          onClick={() => props.onNavigateToTask?.(task.id, { runId: latestRun?.id ?? null })}
                          className={tableActionButtonClass}
                        >
                          任务
                        </button>
                      ) : null}
                      {latestRun?.id && props.onNavigateToRun ? (
                        <button
                          type="button"
                          onClick={() => (latestRun.id ? props.onNavigateToRun?.(latestRun.id, task.id) : undefined)}
                          className={tableActionButtonClass}
                        >
                          运行
                        </button>
                      ) : null}
                      {latestRun ? (
                        <button
                          type="button"
                          data-testid={`home-task-latest-run-drilldown-${task.id}`}
                          onClick={() =>
                            props.onNavigateToProjectDrilldown({
                              source: "home_latest_run",
                              taskId: task.id,
                              runId: latestRun.id ?? null,
                            })
                          }
                          className={subtleActionButtonClass}
                        >
                          钻取
                        </button>
                      ) : null}
                    </div>
                  </article>
                );
              })
            ) : (
              <div className="py-12 text-center text-sm text-zinc-500">
                暂无任务。后端创建任务后，可在这里查看状态、费用和最近运行。
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3 border-t border-[#333333] px-2 py-3 text-sm text-zinc-500 sm:flex-row sm:items-center sm:justify-between sm:px-3">
            <div>
              共 {props.tasks.length} 条任务，每页 {TASKS_PER_PAGE} 条
              {props.tasks.length ? `，当前 ${pageStart}-${pageEnd}` : ""}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                disabled={currentPage <= 1}
                className="rounded-md border border-[#333333] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:bg-[#2f2f2f] hover:text-zinc-50 disabled:cursor-not-allowed disabled:text-zinc-700"
              >
                上一页
              </button>
              <span className="min-w-16 text-center text-xs text-zinc-500">{currentPage} / {totalPages}</span>
              <button
                type="button"
                onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                disabled={currentPage >= totalPages}
                className="rounded-md border border-[#333333] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:bg-[#2f2f2f] hover:text-zinc-50 disabled:cursor-not-allowed disabled:text-zinc-700"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
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

function buildRunMicroSummary(run: NonNullable<ConsoleTask["latest_run"]>) {
  const gate =
    run.quality_gate_passed === true
      ? "质检通过"
      : run.quality_gate_passed === false
        ? "质检阻断"
        : "质检未知";
  const failure = run.failure_category ? ` · ${run.failure_category}` : "";
  return `${gate}${failure}`;
}
