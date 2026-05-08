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
  "rounded-lg border border-zinc-800 bg-zinc-950/45 px-2.5 py-1 text-[11px] font-medium text-zinc-300 transition hover:border-zinc-600 hover:bg-zinc-900 hover:text-zinc-50";
const subtleActionButtonClass =
  "rounded-lg border border-zinc-800 bg-zinc-900/65 px-2.5 py-1 text-[11px] font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-zinc-800";

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
  const emptyRowCount = Math.max(0, TASKS_PER_PAGE - pagedTasks.length);

  return (
    <section
      data-testid="home-task-table-section"
      className="rounded-[24px] border border-zinc-800/90 bg-zinc-950/50 p-3 shadow-xl shadow-black/15 ring-1 ring-white/[0.02] sm:p-4"
    >
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-50">任务队列</h2>
          <p className="mt-1 text-xs text-zinc-500 sm:text-sm">每页 5 条，点击任务查看摘要。</p>
        </div>
        <StatusBadge
          label={props.overviewIsLoading ? "加载中" : props.overviewIsError ? "加载失败" : "已同步"}
          tone={props.overviewIsLoading ? "warning" : props.overviewIsError ? "danger" : "neutral"}
        />
      </div>

      {props.overviewIsError ? (
        <div className="rounded-xl border border-rose-900/60 bg-rose-950/25 p-4 text-sm text-rose-100">
          工作台数据加载失败。请确认后端服务已启动，并且 GET /tasks/console 可访问。
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-zinc-800/80 bg-black/15">
          <div className="overflow-x-auto">
            <table className="min-w-[760px] table-fixed divide-y divide-zinc-800/80 text-sm">
              <colgroup>
                <col className="w-[33%]" />
                <col className="w-[12%]" />
                <col className="w-[22%]" />
                <col className="w-[9%]" />
                <col className="w-[11%]" />
                <col className="w-[13%]" />
              </colgroup>
              <thead className="bg-zinc-950/80 text-left text-xs tracking-[0.12em] text-zinc-500">
                <tr>
                  <th className="px-3 py-2.5 font-medium">任务</th>
                  <th className="px-3 py-2.5 font-medium">状态</th>
                  <th className="px-3 py-2.5 font-medium">最近运行</th>
                  <th className="px-3 py-2.5 font-medium">费用</th>
                  <th className="px-3 py-2.5 font-medium">更新</th>
                  <th className="px-3 py-2.5 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/70 bg-zinc-950/20">
                {pagedTasks.length ? (
                  pagedTasks.map((task) => {
                    const isSelected = props.selectedTaskId === task.id;

                    return (
                      <tr
                        key={task.id}
                        data-testid={`home-task-row-${task.id}`}
                        className={`h-[72px] align-middle transition ${
                          isSelected
                            ? "bg-zinc-900/70 shadow-[inset_3px_0_0_rgba(244,244,245,0.5)]"
                            : "hover:bg-zinc-900/45"
                        }`}
                      >
                        <td className="px-3 py-2.5">
                          <div className="min-w-0">
                            <div className="flex min-w-0 items-center gap-2">
                              <button type="button" onClick={() => props.onSelectTask(task.id)} className="min-w-0 flex-1 text-left">
                                <div className="truncate font-medium text-zinc-100">{task.title}</div>
                              </button>
                              <span
                                className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                                  isSelected
                                    ? "border-zinc-600 bg-zinc-100 text-zinc-950"
                                    : "border-zinc-800 bg-zinc-950/60 text-zinc-500"
                                }`}
                              >
                                {isSelected ? "已选" : "选择"}
                              </span>
                            </div>
                            <button
                              type="button"
                              onClick={() => props.onSelectTask(task.id)}
                              className="mt-1 block max-w-full truncate text-left text-xs leading-5 text-zinc-500 transition hover:text-zinc-300"
                            >
                              P{task.priority} · {task.input_summary}
                            </button>
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <StatusBadge label={formatTaskStatusLabel(task.status)} tone={mapTaskStatusTone(task.status)} />
                        </td>
                        <td className="px-3 py-2.5">
                          {task.latest_run ? (
                            <div className="min-w-0 space-y-1">
                              <div className="flex min-w-0 items-center gap-2">
                                <StatusBadge label={formatRunStatusLabel(task.latest_run.status)} tone={mapRunStatusTone(task.latest_run.status)} />
                                <span className="truncate text-xs text-zinc-500">{formatDateTime(task.latest_run.created_at)}</span>
                              </div>
                              <div className="truncate text-xs text-zinc-500">{buildRunMicroSummary(task.latest_run)}</div>
                            </div>
                          ) : (
                            <span className="text-xs text-zinc-500">暂无运行</span>
                          )}
                        </td>
                        <td data-testid={`home-task-estimated-cost-${task.id}`} className="truncate px-3 py-2.5 text-zinc-300">
                          {task.latest_run ? formatNullableCurrencyUsd(task.latest_run.estimated_cost) : "-"}
                        </td>
                        <td className="truncate px-3 py-2.5 text-xs text-zinc-500">{formatDateTime(task.updated_at)}</td>
                        <td className="px-3 py-2.5">
                          <div className="flex flex-wrap justify-end gap-1.5">
                            {props.onNavigateToTask ? (
                              <button
                                type="button"
                                onClick={() => props.onNavigateToTask?.(task.id, { runId: task.latest_run?.id ?? null })}
                                className={tableActionButtonClass}
                              >
                                任务
                              </button>
                            ) : null}
                            {task.latest_run?.id && props.onNavigateToRun ? (
                              <button
                                type="button"
                                onClick={() => (task.latest_run?.id ? props.onNavigateToRun?.(task.latest_run.id, task.id) : undefined)}
                                className={tableActionButtonClass}
                              >
                                运行
                              </button>
                            ) : null}
                            {task.latest_run ? (
                              <button
                                type="button"
                                data-testid={`home-task-latest-run-drilldown-${task.id}`}
                                onClick={() =>
                                  props.onNavigateToProjectDrilldown({
                                    source: "home_latest_run",
                                    taskId: task.id,
                                    runId: task.latest_run?.id ?? null,
                                  })
                                }
                                className={subtleActionButtonClass}
                              >
                                钻取
                              </button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-sm text-zinc-500">
                      暂无任务。后端创建任务后，可在这里查看状态、费用和最近运行。
                    </td>
                  </tr>
                )}
                {props.tasks.length
                  ? Array.from({ length: emptyRowCount }).map((_, index) => (
                      <tr key={`empty-row-${index}`} aria-hidden="true" className="h-[72px] bg-black/10">
                        <td colSpan={6} className="px-3 py-2.5">
                          <div className="h-px w-full bg-zinc-900/70" />
                        </td>
                      </tr>
                    ))
                  : null}
              </tbody>
            </table>
          </div>
          <div className="flex flex-col gap-3 border-t border-zinc-800/80 bg-black/20 px-3 py-3 text-sm text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
            <div>
              共 {props.tasks.length} 条任务，每页 {TASKS_PER_PAGE} 条
              {props.tasks.length ? `，当前 ${pageStart}-${pageEnd}` : ""}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                disabled={currentPage <= 1}
                className="rounded-lg border border-zinc-800 bg-zinc-950/45 px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:border-zinc-600 hover:text-zinc-50 disabled:cursor-not-allowed disabled:border-zinc-900 disabled:bg-black/20 disabled:text-zinc-700"
              >
                上一页
              </button>
              <span className="min-w-16 text-center text-xs text-zinc-500">{currentPage} / {totalPages}</span>
              <button
                type="button"
                onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                disabled={currentPage >= totalPages}
                className="rounded-lg border border-zinc-800 bg-zinc-950/45 px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:border-zinc-600 hover:text-zinc-50 disabled:cursor-not-allowed disabled:border-zinc-900 disabled:bg-black/20 disabled:text-zinc-700"
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
