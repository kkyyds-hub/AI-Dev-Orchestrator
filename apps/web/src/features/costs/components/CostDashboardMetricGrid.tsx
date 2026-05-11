import { formatDateTime, formatTokenCount } from "../../../lib/format";
import type { ProjectCostDashboardSnapshot } from "../types";
import { formatUsd } from "./costDashboardFormat";

type CostDashboardMetricGridProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardMetricGrid(props: CostDashboardMetricGridProps) {
  const { snapshot } = props;

  const metrics = [
    { label: "预估总成本", value: formatUsd(snapshot.total_estimated_cost_usd) },
    { label: "平均单次运行", value: formatUsd(snapshot.avg_estimated_cost_per_run_usd) },
    { label: "运行次数", value: formatTokenCount(snapshot.run_count) },
    { label: "线程数量", value: formatTokenCount(snapshot.thread_count) },
    { label: "总令牌", value: formatTokenCount(snapshot.total_tokens) },
    { label: "生成时间", value: formatDateTime(snapshot.generated_at) },
  ];

  return (
    <section
      aria-label="关键成本指标摘要"
      className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/35"
    >
      <div className="grid divide-y divide-slate-800 sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-6">
        {metrics.map((metric) => (
          <div key={metric.label} className="px-4 py-3">
            <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-500">
              {metric.label}
            </div>
            <div className="mt-1 text-sm font-semibold text-slate-100">{metric.value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
