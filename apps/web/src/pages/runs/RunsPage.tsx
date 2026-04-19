import { useEffect, useMemo } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { StatusBadge } from "../../components/StatusBadge";
import { useConsoleOverview } from "../../features/console/hooks";
import type { ConsoleRun, ConsoleTask } from "../../features/console/types";
import { useConsoleEventStream } from "../../features/events/hooks";
import { TaskDetailPanel } from "../../features/task-detail/TaskDetailPanel";
import { formatDateTime, formatNullableCurrencyUsd } from "../../lib/format";
import { buildRunRoute } from "../../lib/run-route";
import { mapRunStatusTone } from "../../lib/status";

type RunListItem = {
  task: ConsoleTask;
  run: ConsoleRun;
};

type BossDrilldownNavigateDetail = {
  source: "home_latest_run" | "home_manual_run";
  taskId: string;
  runId?: string | null;
};

function buildBossDrilldownHash(detail: BossDrilldownNavigateDetail) {
  const params = new URLSearchParams();
  params.set("source", detail.source);
  params.set("taskId", detail.taskId);

  if (detail.runId) {
    params.set("runId", detail.runId);
  }

  return `#boss-drilldown?${params.toString()}`;
}

export function RunsPage() {
  const navigate = useNavigate();
  const { runId } = useParams();
  const [searchParams] = useSearchParams();
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });

  const latestRuns = useMemo<RunListItem[]>(
    () =>
      (overviewQuery.data?.tasks ?? [])
        .filter((task): task is ConsoleTask & { latest_run: ConsoleRun } => Boolean(task.latest_run))
        .map((task) => ({
          task,
          run: task.latest_run,
        }))
        .sort((left, right) => right.run.created_at.localeCompare(left.run.created_at)),
    [overviewQuery.data?.tasks],
  );

  const routeTaskId = searchParams.get("taskId");
  const inferredTaskId = useMemo(
    () => latestRuns.find((item) => item.run.id === runId)?.task.id ?? null,
    [latestRuns, runId],
  );
  const effectiveTaskId = routeTaskId ?? inferredTaskId ?? null;
  const selectedTask = useMemo<ConsoleTask | null>(
    () => (overviewQuery.data?.tasks ?? []).find((task) => task.id === effectiveTaskId) ?? null,
    [effectiveTaskId, overviewQuery.data?.tasks],
  );
  const selectedRunInLatestList = latestRuns.some((item) => item.run.id === runId);

  useEffect(() => {
    if (runId && !routeTaskId && inferredTaskId) {
      navigate(
        buildRunRoute({
          runId,
          taskId: inferredTaskId,
          from: "runs",
        }),
        { replace: true },
      );
    }
  }, [inferredTaskId, navigate, routeTaskId, runId]);

  const handleNavigateToDeliverable = (input: {
    projectId: string;
    deliverableId: string;
  }) => {
    const nextSearchParams = new URLSearchParams();
    nextSearchParams.set("deliverableId", input.deliverableId);

    navigate(
      `/projects/${input.projectId}?${nextSearchParams.toString()}#project-overview?view=deliverable-center&targetId=deliverable-center`,
    );
  };

  const handleNavigateToProjectDrilldown = (detail: BossDrilldownNavigateDetail) => {
    navigate(`/projects${buildBossDrilldownHash(detail)}`);
  };

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-300">
              Runs
            </div>
            <h3 className="mt-2 text-xl font-semibold text-slate-50">运行中心</h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              在正式运行域中查看运行状态、决策回放、结构化日志事件与运行上下文。
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <SummaryCard label="可见运行" value={String(latestRuns.length)} />
            <SummaryCard label="当前运行" value={runId ?? "未选择"} />
            <SummaryCard label="连接状态" value={realtime.status} />
          </div>
        </div>
      </section>

      {runId && !effectiveTaskId ? (
        <section className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
          当前运行 URL 缺少稳定的任务上下文。建议使用包含
          <code className="mx-1 rounded bg-slate-950/40 px-1.5 py-0.5">taskId</code>
          的地址访问该运行，以便稳定承接运行详情与日志视图。
        </section>
      ) : null}

      {runId && effectiveTaskId && !selectedRunInLatestList ? (
        <section className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-4 text-sm leading-6 text-cyan-100">
          当前运行来自任务历史记录，不一定出现在“最新运行列表”中；右侧详情仍会按 taskId +
          runId 承接该运行。
        </section>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[1.05fr_minmax(380px,1fr)]">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-50">最新运行列表</h2>
              <p className="text-sm text-slate-400">
                基于当前任务总览聚合最近一轮运行，可直接进入正式运行详情页。
              </p>
            </div>
            <StatusBadge
              label={
                overviewQuery.isLoading
                  ? "加载中"
                  : overviewQuery.isError
                    ? "加载失败"
                    : "数据已就绪"
              }
              tone={
                overviewQuery.isLoading
                  ? "warning"
                  : overviewQuery.isError
                    ? "danger"
                    : "success"
              }
            />
          </div>

          {overviewQuery.isError ? (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
              无法加载运行列表，请确认后端已启动并可访问 <code>GET /tasks/console</code>。
            </div>
          ) : latestRuns.length ? (
            <div className="space-y-3">
              {latestRuns.map((item) => {
                const isSelected = item.run.id === runId;

                return (
                  <button
                    key={item.run.id}
                    type="button"
                    onClick={() =>
                      navigate(
                        buildRunRoute({
                          runId: item.run.id,
                          taskId: item.task.id,
                          from: "runs",
                        }),
                      )
                    }
                    className={`w-full rounded-2xl border p-4 text-left transition ${
                      isSelected
                        ? "border-cyan-500/40 bg-cyan-500/10"
                        : "border-slate-800 bg-slate-950/60 hover:border-slate-700 hover:bg-slate-950/80"
                    }`}
                  >
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="text-sm font-medium text-slate-100">{item.task.title}</div>
                          <StatusBadge
                            label={item.run.status}
                            tone={mapRunStatusTone(item.run.status)}
                          />
                        </div>
                        <div className="mt-2 text-xs text-slate-500">
                          Task {item.task.id} · Run {item.run.id}
                        </div>
                        <p className="mt-3 text-sm leading-6 text-slate-300">
                          {item.run.result_summary ?? "暂无运行摘要"}
                        </p>
                      </div>

                      <div className="grid gap-2 text-xs text-slate-400 sm:grid-cols-2 lg:min-w-[220px]">
                        <RunStat label="创建时间" value={formatDateTime(item.run.created_at)} />
                        <RunStat
                          label="估算成本"
                          value={formatNullableCurrencyUsd(item.run.estimated_cost)}
                        />
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-400">
              当前还没有可展示的最新运行记录。
            </div>
          )}
        </section>

        <TaskDetailPanel
          panelId="runs-task-detail-panel"
          runLogPanelId="runs-run-log-panel"
          requestedRunId={runId ?? null}
          selectedTask={selectedTask}
          budget={overviewQuery.data?.budget ?? null}
          realtimeStatus={realtime.status}
          onNavigateToDeliverable={handleNavigateToDeliverable}
          onNavigateToRun={(nextRunId, taskId) =>
            navigate(
              buildRunRoute({
                runId: nextRunId,
                taskId,
                from: "runs",
              }),
            )
          }
          onNavigateToStrategyPreview={({ taskId: nextTaskId, runId: nextRunId }) =>
            handleNavigateToProjectDrilldown({
              source: "home_latest_run",
              taskId: nextTaskId,
              runId: nextRunId,
            })
          }
        />
      </section>
    </div>
  );
}

function SummaryCard(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 break-all text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}

function RunStat(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{props.label}</div>
      <div className="mt-1 text-sm text-slate-200">{props.value}</div>
    </div>
  );
}
