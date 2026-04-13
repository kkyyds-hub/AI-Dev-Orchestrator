import { useEffect, useMemo, useState } from "react";

import { MetricCard } from "../components/MetricCard";
import { StatusBadge } from "../components/StatusBadge";
import { BudgetOverviewPanel } from "../features/budget/BudgetOverviewPanel";
import { ConsoleMetricsPanel } from "../features/console-metrics/ConsoleMetricsPanel";
import { DecisionHintPanel } from "../features/console-metrics/DecisionHintPanel";
import { FailureDistributionPanel } from "../features/console-metrics/FailureDistributionPanel";
import { ReviewClustersPanel } from "../features/console-metrics/ReviewClustersPanel";
import { useReviewClusters } from "../features/console-metrics/decision-hooks";
import { useBackendHealth, useConsoleOverview } from "../features/console/hooks";
import { ProjectOverviewPage } from "../features/projects/ProjectOverviewPage";
import { WorkerSlotPanel } from "../features/console-metrics/WorkerSlotPanel";
import type { ConsoleTask } from "../features/console/types";
import { useConsoleEventStream } from "../features/events/hooks";
import { TaskDetailPanel } from "../features/task-detail/TaskDetailPanel";
import { useRunWorkerOnce, useRunWorkerPoolOnce } from "../features/task-actions/hooks";
import { WorkerMemoryRecallCard } from "../features/task-actions/WorkerMemoryRecallCard";
import { WorkerProviderPromptTokenCard } from "../features/task-actions/WorkerProviderPromptTokenCard";
import { formatCurrencyUsd, formatDateTime, formatTokenCount } from "../lib/format";
import { mapRunStatusTone, mapTaskStatusTone } from "../lib/status";

export function App() {
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });
  const reviewClustersQuery = useReviewClusters();
  const healthQuery = useBackendHealth();
  const runWorkerOnceMutation = useRunWorkerOnce();
  const runWorkerPoolOnceMutation = useRunWorkerPoolOnce();
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [requestedRunId, setRequestedRunId] = useState<string | null>(null);

  const tasks = overviewQuery.data?.tasks ?? [];

  useEffect(() => {
    if (!tasks.length) {
      if (selectedTaskId !== null) {
        setSelectedTaskId(null);
      }
      return;
    }

    const hasSelection = tasks.some((task) => task.id === selectedTaskId);
    if (!selectedTaskId || !hasSelection) {
      setSelectedTaskId(tasks[0].id);
      setRequestedRunId(null);
    }
  }, [tasks, selectedTaskId]);

  const selectedTask = useMemo<ConsoleTask | null>(
    () => tasks.find((task) => task.id === selectedTaskId) ?? null,
    [tasks, selectedTaskId],
  );

  const lastUpdatedText = useMemo(() => {
    if (!overviewQuery.dataUpdatedAt) {
      return "尚未刷新";
    }

    return formatDateTime(new Date(overviewQuery.dataUpdatedAt).toISOString());
  }, [overviewQuery.dataUpdatedAt]);

  const totalTokens =
    (overviewQuery.data?.total_prompt_tokens ?? 0) +
    (overviewQuery.data?.total_completion_tokens ?? 0);

  const handleRefresh = async () => {
    await Promise.all([overviewQuery.refetch(), healthQuery.refetch()]);
  };

  const handleNavigateToTaskDetail = (
    taskId: string,
    options?: { runId?: string | null },
  ) => {
    setSelectedTaskId(taskId);
    setRequestedRunId(options?.runId ?? null);

    const targetId = options?.runId ? "task-run-log-panel" : "task-detail-panel";
    requestAnimationFrame(() => {
      document.getElementById(targetId)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  const handleNavigateToDeliverable = (input: {
    projectId: string;
    deliverableId: string;
  }) => {
    window.dispatchEvent(
      new CustomEvent("deliverable:navigate", {
        detail: input,
      }),
    );

    requestAnimationFrame(() => {
      document.getElementById("deliverable-center")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
        <ProjectOverviewPage onNavigateToTask={handleNavigateToTaskDetail} />

        <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-2xl shadow-slate-950/40 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
              Day 15 Console
            </p>
            <h1 className="text-3xl font-semibold tracking-tight">
              AI Dev Orchestrator 预算守卫控制台
            </h1>
            <p className="max-w-3xl text-sm text-slate-300">
              在 Day 14 验证闸门基础上，补齐预算守卫、阻塞原因和失败重试边界。
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:items-end">
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge
                label={healthQuery.data?.status === "ok" ? "后端在线" : "后端未知"}
                tone={healthQuery.data?.status === "ok" ? "success" : "warning"}
              />
              <StatusBadge
                label={mapRealtimeLabel(realtime.status)}
                tone={mapRealtimeTone(realtime.status)}
              />
              <button
                type="button"
                onClick={() => runWorkerOnceMutation.mutate()}
                disabled={runWorkerOnceMutation.isPending}
                className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
              >
                {runWorkerOnceMutation.isPending ? "执行中..." : "执行 Worker 一次"}
              </button>
              <button
                type="button"
                onClick={() => runWorkerPoolOnceMutation.mutate()}
                disabled={runWorkerPoolOnceMutation.isPending}
                className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
              >
                {runWorkerPoolOnceMutation.isPending ? "并行执行中..." : "执行 Worker Pool"}
              </button>
              <button
                type="button"
                onClick={() => void handleRefresh()}
                className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-500 hover:bg-slate-800"
              >
                刷新控制台
              </button>
            </div>
            <div className="text-right text-sm text-slate-400">
              <div>服务：{healthQuery.data?.service ?? "orchestrator-backend"}</div>
              <div>最近刷新：{lastUpdatedText}</div>
              <div>
                最近事件：
                {realtime.lastEventType
                  ? `${realtime.lastEventType} @ ${formatDateTime(realtime.lastEventAt)}`
                  : "尚未收到"}
              </div>
            </div>
          </div>
        </header>

        {runWorkerOnceMutation.data || runWorkerOnceMutation.isError ? (
          <section
            className={`rounded-2xl border p-4 ${
              runWorkerOnceMutation.isError
                ? "border-rose-500/30 bg-rose-500/10"
                : runWorkerOnceMutation.data?.claimed
                  ? "border-emerald-500/30 bg-emerald-500/10"
                  : "border-amber-500/30 bg-amber-500/10"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-slate-50">最近一次手动执行</h2>
                <p
                  className={`mt-1 text-sm ${
                    runWorkerOnceMutation.isError
                      ? "text-rose-100"
                      : runWorkerOnceMutation.data?.claimed
                        ? "text-emerald-100"
                        : "text-amber-100"
                  }`}
                >
                  {runWorkerOnceMutation.isError
                    ? runWorkerOnceMutation.error.message
                    : runWorkerOnceMutation.data?.message}
                </p>
              </div>
              {!runWorkerOnceMutation.isError && runWorkerOnceMutation.data ? (
                <StatusBadge
                  label={runWorkerOnceMutation.data.claimed ? "已处理任务" : "未领取任务"}
                  tone={runWorkerOnceMutation.data.claimed ? "success" : "warning"}
                />
              ) : null}
            </div>

            {!runWorkerOnceMutation.isError && runWorkerOnceMutation.data?.task_title ? (
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MiniInfo
                  label="任务"
                  value={runWorkerOnceMutation.data.task_title}
                />
                <MiniInfo
                  label="运行状态"
                  value={runWorkerOnceMutation.data.run_status ?? "—"}
                />
                <MiniInfo
                  label="估算成本"
                  value={formatCurrencyUsd(runWorkerOnceMutation.data.estimated_cost ?? 0)}
                />
                <MiniInfo
                  label="路由分数"
                  value={
                    runWorkerOnceMutation.data.routing_score !== null
                    && runWorkerOnceMutation.data.routing_score !== undefined
                      ? String(runWorkerOnceMutation.data.routing_score)
                      : "—"
                  }
                />
              </div>
            ) : null}

            {!runWorkerOnceMutation.isError && runWorkerOnceMutation.data?.route_reason ? (
              <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">路由原因</div>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  {runWorkerOnceMutation.data.route_reason}
                </p>
              </div>
            ) : null}

            {!runWorkerOnceMutation.isError &&
            (runWorkerOnceMutation.data?.model_name ||
              runWorkerOnceMutation.data?.selected_skill_names.length) ? (
              <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  策略引擎结果
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <MiniInfo
                    label="模型"
                    value={
                      runWorkerOnceMutation.data?.model_name
                        ? `${runWorkerOnceMutation.data.model_name}${runWorkerOnceMutation.data.model_tier ? ` (${runWorkerOnceMutation.data.model_tier})` : ""}`
                        : "—"
                    }
                  />
                  <MiniInfo
                    label="策略代码"
                    value={runWorkerOnceMutation.data?.strategy_code ?? "—"}
                  />
                </div>
                {runWorkerOnceMutation.data?.strategy_summary ? (
                  <p className="mt-3 text-sm leading-6 text-slate-300">
                    {runWorkerOnceMutation.data.strategy_summary}
                  </p>
                ) : null}
                {runWorkerOnceMutation.data?.selected_skill_names.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {runWorkerOnceMutation.data.selected_skill_names.map((skillName) => (
                      <span
                        key={`${skillName}-${runWorkerOnceMutation.data?.run_id ?? "run"}`}
                        className="rounded-full border border-cyan-400/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100"
                      >
                        {skillName}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            {!runWorkerOnceMutation.isError && runWorkerOnceMutation.data ? (
              <WorkerProviderPromptTokenCard {...runWorkerOnceMutation.data} />
            ) : null}

            {!runWorkerOnceMutation.isError && runWorkerOnceMutation.data ? (
              <WorkerMemoryRecallCard {...runWorkerOnceMutation.data} />
            ) : null}
          </section>
        ) : null}

        {runWorkerPoolOnceMutation.data || runWorkerPoolOnceMutation.isError ? (
          <section
            className={`rounded-2xl border p-4 ${
              runWorkerPoolOnceMutation.isError
                ? "border-rose-500/30 bg-rose-500/10"
                : "border-cyan-500/30 bg-cyan-500/10"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-slate-50">最近一次 Worker Pool 执行</h2>
                <p
                  className={`mt-1 text-sm ${
                    runWorkerPoolOnceMutation.isError ? "text-rose-100" : "text-cyan-100"
                  }`}
                >
                  {runWorkerPoolOnceMutation.isError
                    ? runWorkerPoolOnceMutation.error.message
                    : `请求 ${runWorkerPoolOnceMutation.data?.requested_workers} 个槽位，启动 ${runWorkerPoolOnceMutation.data?.launched_workers} 个 worker，实际领取 ${runWorkerPoolOnceMutation.data?.claimed_runs} 条任务。`}
                </p>
              </div>
              {!runWorkerPoolOnceMutation.isError && runWorkerPoolOnceMutation.data ? (
                <StatusBadge
                  label={`${runWorkerPoolOnceMutation.data.slot_snapshot.running_slots} 个槽位运行中`}
                  tone="info"
                />
              ) : null}
            </div>
          </section>
        ) : null}

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <MetricCard
            label="任务总数"
            value={String(overviewQuery.data?.total_tasks ?? 0)}
            hint="当前系统内已创建的任务数"
          />
          <MetricCard
            label="运行中 / 待处理"
            value={`${overviewQuery.data?.running_tasks ?? 0} / ${overviewQuery.data?.pending_tasks ?? 0}`}
            hint="最小 Worker 当前可见的工作量"
            tone="info"
          />
          <MetricCard
            label="暂停 / 待人工"
            value={`${overviewQuery.data?.paused_tasks ?? 0} / ${overviewQuery.data?.waiting_human_tasks ?? 0}`}
            hint="显式暂停和人工介入状态"
            tone="warning"
          />
          <MetricCard
            label="已完成 / 失败"
            value={`${overviewQuery.data?.completed_tasks ?? 0} / ${overviewQuery.data?.failed_tasks ?? 0}`}
            hint="成功与失败任务数量"
            tone="success"
          />
          <MetricCard
            label="累计估算成本"
            value={formatCurrencyUsd(overviewQuery.data?.total_estimated_cost ?? 0)}
            hint={`总 token：${formatTokenCount(totalTokens)}`}
            tone="warning"
          />
        </section>

        <section className="grid gap-4 lg:grid-cols-[1.45fr_1fr]">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-50">任务列表</h2>
                <p className="text-sm text-slate-400">
                  展示任务状态、最新运行状态，并支持直接打开详情、日志与任务操作侧板。
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
                无法加载控制台首页数据，请确认后端已启动并可访问 `GET /tasks/console`。
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-800 text-sm">
                  <thead className="text-left text-slate-400">
                    <tr>
                      <th className="py-3 pr-4 font-medium">任务</th>
                      <th className="py-3 pr-4 font-medium">任务状态</th>
                      <th className="py-3 pr-4 font-medium">最新运行</th>
                      <th className="py-3 pr-4 font-medium">成本</th>
                      <th className="py-3 pr-4 font-medium">日志</th>
                      <th className="py-3 font-medium">更新时间</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80">
                    {tasks.length ? (
                      tasks.map((task) => {
                        const isSelected = selectedTaskId === task.id;

                        return (
                          <tr
                            key={task.id}
                            className={`align-top transition ${
                              isSelected ? "bg-slate-950/60" : "hover:bg-slate-950/40"
                            }`}
                          >
                            <td className="py-4 pr-4">
                              <button
                                type="button"
                                    onClick={() => {
                                      setSelectedTaskId(task.id);
                                      setRequestedRunId(null);
                                    }}
                                className="w-full text-left"
                              >
                                <div className="space-y-2">
                                  <div className="flex items-center gap-2">
                                    <div className="font-medium text-slate-100">{task.title}</div>
                                    <span
                                      className={`rounded-full px-2 py-1 text-[11px] font-medium ${
                                        isSelected
                                          ? "bg-cyan-500/15 text-cyan-200"
                                          : "bg-slate-800 text-slate-400"
                                      }`}
                                    >
                                      {isSelected ? "详情中" : "查看详情"}
                                    </span>
                                  </div>
                                  <div className="text-xs uppercase tracking-wide text-slate-500">
                                    优先级：{task.priority}
                                  </div>
                                  <div className="max-w-md text-xs leading-5 text-slate-400">
                                    {task.input_summary}
                                  </div>
                                </div>
                              </button>
                            </td>
                            <td className="py-4 pr-4">
                              <StatusBadge label={task.status} tone={mapTaskStatusTone(task.status)} />
                            </td>
                            <td className="py-4 pr-4">
                              {task.latest_run ? (
                                <div className="space-y-2">
                                  <StatusBadge
                                    label={task.latest_run.status}
                                    tone={mapRunStatusTone(task.latest_run.status)}
                                  />
                                  <div className="text-xs text-slate-400">
                                    <div>
                                      token：{formatTokenCount(task.latest_run.prompt_tokens)} /{" "}
                                      {formatTokenCount(task.latest_run.completion_tokens)}
                                    </div>
                                    <div>
                                      闸门：
                                      {task.latest_run.quality_gate_passed === true
                                        ? "放行"
                                        : task.latest_run.quality_gate_passed === false
                                          ? "拦截"
                                          : "未知"}
                                    </div>
                                    {task.latest_run.failure_category ? (
                                      <div>失败分类：{task.latest_run.failure_category}</div>
                                    ) : null}
                                    <div className="max-w-xs">
                                      {task.latest_run.result_summary ?? "暂无运行摘要"}
                                    </div>
                                  </div>
                                </div>
                              ) : (
                                <span className="text-xs text-slate-500">尚未运行</span>
                              )}
                            </td>
                            <td className="py-4 pr-4 text-slate-200">
                              {task.latest_run
                                ? formatCurrencyUsd(task.latest_run.estimated_cost)
                                : formatCurrencyUsd(0)}
                            </td>
                            <td className="py-4 pr-4">
                              {task.latest_run?.log_path ? (
                                <code className="break-all text-xs text-cyan-200">
                                  {task.latest_run.log_path}
                                </code>
                              ) : (
                                <span className="text-xs text-slate-500">暂无日志</span>
                              )}
                            </td>
                            <td className="py-4 text-slate-400">
                              {formatDateTime(task.updated_at)}
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-sm text-slate-500">
                          当前还没有任务。先在后端创建任务，再回到控制台查看状态、成本、日志和详情上下文。
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <aside className="space-y-4">
            <TaskDetailPanel
              panelId="task-detail-panel"
              runLogPanelId="task-run-log-panel"
              requestedRunId={requestedRunId}
              selectedTask={selectedTask}
              budget={overviewQuery.data?.budget ?? null}
              realtimeStatus={realtime.status}
              onNavigateToDeliverable={handleNavigateToDeliverable}
            />

            {overviewQuery.data?.budget ? (
              <BudgetOverviewPanel
                budget={overviewQuery.data.budget}
                blockedTasks={overviewQuery.data.blocked_tasks}
              />
            ) : null}

            <ConsoleMetricsPanel />

            <FailureDistributionPanel />

            <ReviewClustersPanel
              clusters={reviewClustersQuery.data ?? []}
              isLoading={reviewClustersQuery.isLoading && !reviewClustersQuery.data}
              errorMessage={
                reviewClustersQuery.isError ? reviewClustersQuery.error.message : null
              }
            />

            <DecisionHintPanel />

            <WorkerSlotPanel />

            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
              <h2 className="text-lg font-semibold text-slate-50">运行概览</h2>
              <div className="mt-4 space-y-3 text-sm text-slate-300">
                <OverviewRow
                  label="待处理"
                  value={String(overviewQuery.data?.pending_tasks ?? 0)}
                />
                <OverviewRow
                  label="运行中"
                  value={String(overviewQuery.data?.running_tasks ?? 0)}
                />
                <OverviewRow
                  label="已完成"
                  value={String(overviewQuery.data?.completed_tasks ?? 0)}
                />
                <OverviewRow
                  label="失败"
                  value={String(overviewQuery.data?.failed_tasks ?? 0)}
                />
                <OverviewRow
                  label="阻塞"
                  value={String(overviewQuery.data?.blocked_tasks ?? 0)}
                />
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
              <h2 className="text-lg font-semibold text-slate-50">成本统计</h2>
              <div className="mt-4 space-y-3 text-sm text-slate-300">
                <OverviewRow
                  label="Prompt Tokens"
                  value={formatTokenCount(overviewQuery.data?.total_prompt_tokens ?? 0)}
                />
                <OverviewRow
                  label="Completion Tokens"
                  value={formatTokenCount(overviewQuery.data?.total_completion_tokens ?? 0)}
                />
                <OverviewRow
                  label="估算成本"
                  value={formatCurrencyUsd(overviewQuery.data?.total_estimated_cost ?? 0)}
                />
              </div>
              <p className="mt-4 text-xs leading-5 text-slate-500">
                当前成本来自 Day 9 的启发式估算，用于控制台展示，不等同于真实模型厂商账单。
              </p>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}

function OverviewRow(props: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <span className="text-slate-400">{props.label}</span>
      <span className="font-medium text-slate-100">{props.value}</span>
    </div>
  );
}

function MiniInfo(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}

function mapRealtimeTone(status: string) {
  switch (status) {
    case "open":
      return "success" as const;
    case "reconnecting":
      return "warning" as const;
    case "unsupported":
      return "danger" as const;
    default:
      return "info" as const;
  }
}

function mapRealtimeLabel(status: string) {
  switch (status) {
    case "open":
      return "实时已连接";
    case "reconnecting":
      return "实时重连中";
    case "unsupported":
      return "SSE 不可用";
    default:
      return "实时连接中";
  }
}
