import { formatDateTime } from "../../../lib/format";
import type { ProjectCostDashboardSnapshot } from "../types";
import { formatUsd } from "./costDashboardFormat";

type CostDashboardMetricGridProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardMetricGrid(props: CostDashboardMetricGridProps) {
  const { snapshot } = props;

  return (
    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="运行次数" value={String(snapshot.run_count)} />
      <MetricCard label="线程数量" value={String(snapshot.thread_count)} />
      <MetricCard label="预估总成本" value={formatUsd(snapshot.total_estimated_cost_usd)} />
      <MetricCard label="令牌总量" value={String(snapshot.total_tokens)} />
      <MetricCard label="生成时间" value={formatDateTime(snapshot.generated_at)} />
    </section>
  );
}

function MetricCard(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-lg font-semibold text-slate-50">{props.value}</div>
    </div>
  );
}
