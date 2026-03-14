import { StatusBadge } from "../../components/StatusBadge";
import { formatCurrencyUsd, formatDateTime, formatTokenCount } from "../../lib/format";
import { useConsoleBudgetHealth, useConsoleMetricsOverview } from "./hooks";

export function ConsoleMetricsPanel() {
  const metricsQuery = useConsoleMetricsOverview();
  const budgetHealthQuery = useConsoleBudgetHealth();

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-50">观测指标总览</h2>
          <p className="mt-1 text-sm text-slate-400">
            汇总运行数量、成本和预算压力，作为 Day09 管理视图基线。
          </p>
        </div>
        <StatusBadge
          label={
            metricsQuery.isLoading
              ? "加载中"
              : metricsQuery.isError
                ? "加载失败"
                : "已接通"
          }
          tone={
            metricsQuery.isLoading
              ? "warning"
              : metricsQuery.isError
                ? "danger"
                : "success"
          }
        />
      </div>

      {metricsQuery.isError ? (
        <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          无法加载观测指标：{metricsQuery.error.message}
        </div>
      ) : null}

      {metricsQuery.data ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Metric label="总运行数" value={String(metricsQuery.data.total_runs)} />
          <Metric
            label="排队 / 运行中"
            value={`${metricsQuery.data.queued_runs} / ${metricsQuery.data.running_runs}`}
          />
          <Metric
            label="成功 / 失败 / 取消"
            value={`${metricsQuery.data.succeeded_runs} / ${metricsQuery.data.failed_runs} / ${metricsQuery.data.cancelled_runs}`}
          />
          <Metric
            label="累计估算成本"
            value={formatCurrencyUsd(metricsQuery.data.total_estimated_cost)}
            hint={`平均：${formatCurrencyUsd(metricsQuery.data.avg_estimated_cost)}`}
          />
          <Metric
            label="Prompt / Completion"
            value={`${formatTokenCount(metricsQuery.data.total_prompt_tokens)} / ${formatTokenCount(metricsQuery.data.total_completion_tokens)}`}
            hint={`平均：${Math.round(metricsQuery.data.avg_prompt_tokens)} / ${Math.round(metricsQuery.data.avg_completion_tokens)}`}
          />
          <Metric
            label="最近运行时间"
            value={
              metricsQuery.data.latest_run_created_at
                ? formatDateTime(metricsQuery.data.latest_run_created_at)
                : "暂无"
            }
          />
        </div>
      ) : null}

      {budgetHealthQuery.data ? (
        <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              label={pressureLevelLabel(budgetHealthQuery.data.pressure_level)}
              tone={pressureLevelTone(budgetHealthQuery.data.pressure_level)}
            />
            <StatusBadge
              label={`策略：${budgetHealthQuery.data.strategy_code}`}
              tone="info"
            />
          </div>
          <p className="mt-2 text-xs text-slate-400">
            {budgetHealthQuery.data.strategy_summary}
          </p>
        </div>
      ) : null}
    </section>
  );
}

function Metric(props: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 break-all text-sm font-medium text-slate-100">{props.value}</div>
      {props.hint ? <div className="mt-1 text-xs text-slate-500">{props.hint}</div> : null}
    </div>
  );
}

function pressureLevelLabel(level: "normal" | "warning" | "critical" | "blocked") {
  switch (level) {
    case "normal":
      return "预算正常";
    case "warning":
      return "预算预警";
    case "critical":
      return "预算临界";
    case "blocked":
      return "预算阻断";
  }
}

function pressureLevelTone(level: "normal" | "warning" | "critical" | "blocked") {
  switch (level) {
    case "normal":
      return "success" as const;
    case "warning":
    case "critical":
      return "warning" as const;
    case "blocked":
      return "danger" as const;
  }
}
