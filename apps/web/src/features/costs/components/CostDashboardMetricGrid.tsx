import { formatDateTime, formatTokenCount } from "../../../lib/format";
import type { ProjectCostDashboardSnapshot } from "../types";
import { formatUsd } from "./costDashboardFormat";

type CostDashboardMetricGridProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardMetricGrid(props: CostDashboardMetricGridProps) {
  const { snapshot } = props;

  const metrics = [
    { label: "预估总成本", value: formatUsd(snapshot.total_estimated_cost_usd), hint: "项目累计" },
    { label: "平均单次运行", value: formatUsd(snapshot.avg_estimated_cost_per_run_usd), hint: "按运行均摊" },
    { label: "运行次数", value: formatTokenCount(snapshot.run_count), hint: "已记录运行" },
    { label: "线程数量", value: formatTokenCount(snapshot.thread_count), hint: "协作线程" },
    { label: "总令牌", value: formatTokenCount(snapshot.total_tokens), hint: "Prompt + Completion" },
    { label: "生成时间", value: formatDateTime(snapshot.generated_at), hint: "最近更新" },
  ];

  return (
    <section
      aria-label="关键成本指标摘要"
      className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/35"
    >
      <div className="grid gap-px bg-slate-800/70 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
        {metrics.map((metric) => (
          <div key={metric.label} className="bg-slate-950/70 px-4 py-4">
            <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-500">
              {metric.label}
            </div>
            <div className="mt-2 text-base font-semibold text-slate-100">{metric.value}</div>
            <div className="mt-1 text-xs text-slate-600">{metric.hint}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
