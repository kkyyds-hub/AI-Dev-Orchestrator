import { formatTokenCount } from "../../../lib/format";
import type { ProjectCostDashboardSnapshot } from "../types";
import { formatUsd } from "./costDashboardFormat";

type CostDashboardModeCacheGridProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardCostSourcePanel(props: CostDashboardModeCacheGridProps) {
  const { mode_breakdown: modeBreakdown } = props.snapshot;

  return (
    <section className="border-b border-[#333333] pb-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold text-zinc-50">数据来源</h3>
          <p className="mt-1 text-sm leading-6 text-zinc-500">
            按计费模式汇总运行成本、提示词令牌与补全令牌。
          </p>
        </div>
        <div className="text-xs text-zinc-500">任务 {props.snapshot.task_count_with_runs}/{props.snapshot.task_count}</div>
      </div>

      <div className="mt-4 max-h-[360px] overflow-auto overscroll-contain border-y border-[#333333]">
        <table className="w-full min-w-[860px] text-left text-xs text-zinc-300">
          <thead className="sticky top-0 z-10 border-b border-[#333333] bg-[#171717]/95 text-[11px] uppercase tracking-[0.12em] text-zinc-500 backdrop-blur">
            <tr>
              <th className="px-3 py-2 font-medium">计费模式</th>
              <th className="px-3 py-2 text-right font-medium">运行次数</th>
              <th className="px-3 py-2 text-right font-medium">成本</th>
              <th className="px-3 py-2 text-right font-medium">提示词令牌</th>
              <th className="px-3 py-2 text-right font-medium">补全令牌</th>
              <th className="px-3 py-2 text-right font-medium">总令牌</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#333333]">
            {modeBreakdown.map((item) => (
              <tr key={item.mode} className="hover:bg-white/[0.02]">
                <td className="max-w-[180px] truncate px-3 py-2 font-medium text-zinc-100" title={item.mode || "未标记"}>{item.mode || "未标记"}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatTokenCount(item.run_count)}</td>
                <td className="px-3 py-2 text-right font-medium tabular-nums text-zinc-100">
                  {formatUsd(item.total_estimated_cost_usd)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{formatTokenCount(item.prompt_tokens)}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatTokenCount(item.completion_tokens)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{formatTokenCount(item.total_tokens)}</td>
              </tr>
            ))}
            {modeBreakdown.length === 0 ? (
              <tr>
                <td className="px-3 py-5 text-center text-zinc-500" colSpan={6}>
                  当前项目还没有可汇总的数据来源。
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function CostDashboardCacheSummaryPanel(props: CostDashboardModeCacheGridProps) {
  const { cache_summary: cacheSummary } = props.snapshot;

  return (
    <section className="border-b border-[#333333] pb-5 text-sm text-zinc-400">
      <h3 className="text-sm font-semibold text-zinc-200">缓存信号</h3>
      <p className="mt-2 max-h-28 overflow-y-auto break-words pr-2 text-xs leading-5 text-zinc-500">
        {cacheSummary.cache_signal_note}
      </p>

      <dl className="mt-4 space-y-3 border-t border-[#333333] pt-3">
        <div className="flex items-center justify-between gap-3">
          <dt className="text-xs text-zinc-500">记忆总数</dt>
          <dd className="font-medium tabular-nums text-zinc-200">
            {formatTokenCount(cacheSummary.total_memories)}
          </dd>
        </div>
        {cacheSummary.memory_type_counts.map((item) => (
          <div key={item.memory_type} className="flex items-center justify-between gap-3">
            <dt className="truncate text-xs text-zinc-500">{item.memory_type}</dt>
            <dd className="font-medium tabular-nums text-zinc-300">{formatTokenCount(item.count)}</dd>
          </div>
        ))}
      </dl>

      {cacheSummary.memory_type_counts.length === 0 ? (
        <p className="mt-4 border-t border-[#333333] pt-3 text-xs text-zinc-500">暂无缓存统计数据。</p>
      ) : null}
    </section>
  );
}
