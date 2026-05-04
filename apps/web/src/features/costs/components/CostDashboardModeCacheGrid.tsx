import type { ProjectCostDashboardSnapshot } from "../types";
import { formatUsd } from "./costDashboardFormat";

type CostDashboardModeCacheGridProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardModeCacheGrid(props: CostDashboardModeCacheGridProps) {
  return (
    <section className="grid gap-4 xl:grid-cols-2">
      <CostDashboardModeBreakdown snapshot={props.snapshot} />
      <CostDashboardCacheSummary snapshot={props.snapshot} />
    </section>
  );
}

function CostDashboardModeBreakdown(props: CostDashboardModeCacheGridProps) {
  const { mode_breakdown: modeBreakdown } = props.snapshot;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="text-sm font-semibold text-slate-100">令牌计费模式聚合</h3>
      <div className="mt-3 space-y-2 text-sm">
        {modeBreakdown.map((item) => (
          <div
            key={item.mode}
            className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2 text-slate-300"
          >
            <div className="font-medium text-slate-100">{item.mode}</div>
            <div className="mt-1 text-xs text-slate-400">
              运行={item.run_count} | 成本={formatUsd(item.total_estimated_cost_usd)} |
              令牌={item.total_tokens}
            </div>
          </div>
        ))}
        {modeBreakdown.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-700 px-3 py-4 text-xs text-slate-500">
            当前项目还没有可聚合的运行数据。
          </div>
        ) : null}
      </div>
    </div>
  );
}

function CostDashboardCacheSummary(props: CostDashboardModeCacheGridProps) {
  const { cache_summary: cacheSummary } = props.snapshot;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="text-sm font-semibold text-slate-100">缓存（memory）聚合信号</h3>
      <p className="mt-2 text-xs text-slate-400">{cacheSummary.cache_signal_note}</p>
      <div className="mt-2 text-sm text-slate-300">
        记忆总数={cacheSummary.total_memories}
      </div>
      <div className="mt-3 space-y-2 text-xs text-slate-300">
        {cacheSummary.memory_type_counts.map((item) => (
          <div
            key={item.memory_type}
            className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
          >
            {item.memory_type}: {item.count}
          </div>
        ))}
        {cacheSummary.memory_type_counts.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-700 px-3 py-4 text-slate-500">
            暂无 memory 统计数据。
          </div>
        ) : null}
      </div>
    </div>
  );
}
