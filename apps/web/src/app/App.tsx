import { useMemo } from "react";

import { MetricCard } from "../components/MetricCard";
import { StatusBadge } from "../components/StatusBadge";
import { useBackendHealth, useConsoleOverview } from "../features/console/hooks";
import { formatCurrencyUsd, formatDateTime, formatTokenCount } from "../lib/format";

export function App() {
  const overviewQuery = useConsoleOverview();
  const healthQuery = useBackendHealth();

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

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-2xl shadow-slate-950/40 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
              Day 10 Console
            </p>
            <h1 className="text-3xl font-semibold tracking-tight">
              AI Dev Orchestrator 最小控制台首页
            </h1>
            <p className="max-w-3xl text-sm text-slate-300">
              展示任务列表、任务状态和 Day 9 已落地的最小成本记录，作为后续观测面板的第一版入口。
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:items-end">
            <div className="flex items-center gap-3">
              <StatusBadge
                label={healthQuery.data?.status === "ok" ? "后端在线" : "后端未知"}
                tone={healthQuery.data?.status === "ok" ? "success" : "warning"}
              />
              <button
                type="button"
                onClick={() => void handleRefresh()}
                className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-200 transition hover:bg-cyan-500/20"
              >
                刷新首页
              </button>
            </div>
            <div className="text-right text-sm text-slate-400">
              <div>服务：{healthQuery.data?.service ?? "orchestrator-backend"}</div>
              <div>最近刷新：{lastUpdatedText}</div>
            </div>
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
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

        <section className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-50">任务列表</h2>
                <p className="text-sm text-slate-400">
                  展示任务状态、最新运行状态和 Day 9 成本记录。
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
                    {overviewQuery.data?.tasks.length ? (
                      overviewQuery.data.tasks.map((task) => (
                        <tr key={task.id} className="align-top">
                          <td className="py-4 pr-4">
                            <div className="space-y-1">
                              <div className="font-medium text-slate-100">{task.title}</div>
                              <div className="text-xs uppercase tracking-wide text-slate-500">
                                优先级：{task.priority}
                              </div>
                              <div className="max-w-md text-xs leading-5 text-slate-400">
                                {task.input_summary}
                              </div>
                            </div>
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
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-sm text-slate-500">
                          当前还没有任务。先在后端创建任务，再回到控制台查看状态与成本。
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <aside className="space-y-4">
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
                当前成本来自 Day 9 的启发式估算，用于 Day 10 首页展示，不等同于真实模型厂商账单。
              </p>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}

type BadgeTone = "neutral" | "info" | "success" | "warning" | "danger";

function mapTaskStatusTone(status: string): BadgeTone {
  switch (status) {
    case "completed":
      return "success";
    case "running":
      return "info";
    case "failed":
      return "danger";
    case "blocked":
      return "warning";
    default:
      return "neutral";
  }
}

function mapRunStatusTone(status: string): BadgeTone {
  switch (status) {
    case "succeeded":
      return "success";
    case "running":
      return "info";
    case "failed":
      return "danger";
    case "cancelled":
      return "warning";
    default:
      return "neutral";
  }
}

function OverviewRow(props: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <span className="text-slate-400">{props.label}</span>
      <span className="font-medium text-slate-100">{props.value}</span>
    </div>
  );
}
