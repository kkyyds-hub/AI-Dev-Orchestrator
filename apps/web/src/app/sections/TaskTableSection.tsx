import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import type { ConsoleTask } from "../../features/console/types";
import { formatDateTime, formatNullableCurrencyUsd } from "../../lib/format";
import { mapTaskStatusTone } from "../../lib/status";

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

const TASKS_PER_PAGE = 8;
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
      className="flex min-h-0 flex-col overflow-hidden border-r border-[#333333]"
    >
      <div className="flex shrink-0 items-center justify-between border-b border-[#333333] px-3 py-2.5">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100">任务列表</h2>
          <p className="mt-0.5 text-xs text-zinc-500">{props.tasks.length} 条任务</p>
        </div>
        <StatusBadge
          label={props.overviewIsLoading ? "加载中" : props.overviewIsError ? "加载失败" : "就绪"}
          tone={props.overviewIsLoading ? "warning" : props.overviewIsError ? "danger" : "success"}
        />
      </div>

      {props.overviewIsError ? (
        <div className="shrink-0 border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
          任务数据加载失败，请刷新页面或检查服务状态。
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto divide-y divide-[#333333]">
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
                    className={`grid min-h-[68px] cursor-pointer gap-3 px-2 py-3 transition sm:px-3 lg:grid-cols-[minmax(0,1.75fr)_minmax(220px,0.95fr)_116px_176px] lg:items-center ${
                      isSelected ? "rounded-md bg-[#2b2b2b]" : "hover:rounded-md hover:bg-[#2a2a2a]"
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-zinc-100">{task.title}</div>
                      <div className="mt-1 truncate text-xs leading-5 text-zinc-500">
                        优先级 {formatPriorityLabel(task.priority)} · {task.input_summary}
                      </div>
                    </div>

                    <div className="min-w-0 space-y-1.5">
                      <StatusBadge label={formatTaskStatusLabel(task.status)} tone={mapTaskStatusTone(task.status)} />
                      <div className="truncate text-xs text-zinc-500">
                        {latestRun
                          ? `${buildRunMicroSummary(latestRun)} · ${formatDateTime(latestRun.created_at)}`
                          : "暂无运行"}
                      </div>
                    </div>

                    <div data-testid={`home-task-estimated-cost-${task.id}`} className="font-mono text-sm text-zinc-300">
                      {latestRun ? formatNullableCurrencyUsd(latestRun.estimated_cost) : "-"}
                    </div>

                    <div className="flex flex-wrap gap-1 lg:justify-end" onClick={(event) => event.stopPropagation()}>
                      {props.onNavigateToTask ? (
                        <button
                          type="button"
                          onClick={() => props.onNavigateToTask?.(task.id, { runId: latestRun?.id ?? null })}
                          className={tableActionButtonClass}
                        >
                          查看任务
                        </button>
                      ) : null}
                      {latestRun?.id && props.onNavigateToRun ? (
                        <button
                          type="button"
                          onClick={() => (latestRun.id ? props.onNavigateToRun?.(latestRun.id, task.id) : undefined)}
                          className={tableActionButtonClass}
                        >
                          查看运行
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
                          查看项目上下文
                        </button>
                      ) : null}
                    </div>
                  </article>
                );
              })
            ) : (
              <div className="py-12 text-center text-sm text-zinc-500">
                暂无任务。
              </div>
            )}
          </div>

          <div className="flex shrink-0 flex-col gap-3 border-t border-[#333333] px-2 py-3 text-sm text-zinc-500 sm:flex-row sm:items-center sm:justify-between sm:px-3">
            <span>
              共 {props.tasks.length} 条任务
              {props.tasks.length ? `，${pageStart}-${pageEnd}` : ""}
            </span>
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

function formatPriorityLabel(priority: string): string {
  const labels: Record<string, string> = {
    P0: "最高", "0": "最高",
    P1: "高", "1": "高",
    P2: "中", "2": "中",
    P3: "低", "3": "低",
    critical: "最高", high: "高", medium: "中", low: "低",
  };
  return labels[priority] ?? priority;
}

function formatFailureCategoryLabel(category: string | null | undefined) {
  switch (category) {
    case "verification_configuration_failed": return "验证配置失败";
    case "verification_failed": return "验证失败";
    case "execution_failed": return "执行失败";
    case "daily_budget_exceeded": return "日预算超限";
    case "session_budget_exceeded": return "会话预算超限";
    case "retry_limit_exceeded": return "重试达到上限";
    default: return category ?? "";
  }
}

function buildRunMicroSummary(run: NonNullable<ConsoleTask["latest_run"]>) {
  const gate =
    run.quality_gate_passed === true
      ? "质检通过"
      : run.quality_gate_passed === false
        ? "质检阻断"
        : "质检未知";
  const failure = run.failure_category
    ? ` · ${formatFailureCategoryLabel(run.failure_category)}`
    : "";
  return `${gate}${failure}`;
}
