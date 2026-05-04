import { StatusBadge } from "../../../components/StatusBadge";
import type { ProjectCostDashboardSnapshot } from "../types";

type CostDashboardFallbackSummaryProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardFallbackSummary(props: CostDashboardFallbackSummaryProps) {
  const { fallback_contract: fallbackContract } = props.snapshot;

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge
          label={fallbackContract.fallback_active ? "fallback 已启用" : "供应商已回传"}
          tone={fallbackContract.fallback_active ? "warning" : "success"}
        />
        <StatusBadge label={`任务数 ${props.snapshot.task_count}`} tone="info" />
        <StatusBadge
          label={`已有运行的任务 ${props.snapshot.task_count_with_runs}`}
          tone="neutral"
        />
      </div>
      <p className="mt-3 text-sm text-slate-300">{fallbackContract.fallback_reason}</p>
      <div className="mt-2 text-xs text-slate-400">
        供应商回传={fallbackContract.provider_reported_run_count} / 启发式估算=
        {fallbackContract.heuristic_run_count} / 缺失模式=
        {fallbackContract.missing_mode_run_count}
      </div>
    </section>
  );
}
