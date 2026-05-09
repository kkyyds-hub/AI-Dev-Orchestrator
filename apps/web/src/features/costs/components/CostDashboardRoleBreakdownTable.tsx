import { formatTokenCount } from "../../../lib/format";
import type { ProjectCostDashboardSnapshot } from "../types";
import { formatUsd } from "./costDashboardFormat";

type CostDashboardRoleBreakdownTableProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardRoleBreakdownTable(props: CostDashboardRoleBreakdownTableProps) {
  const { role_breakdown: roleBreakdown } = props.snapshot;

  return (
    <section className="border-t border-slate-800/80 pt-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-100">角色成本明细</h3>
        <p className="mt-1 text-xs text-slate-500">按角色聚合运行次数、成本与令牌消耗。</p>
      </div>

      <div className="mt-4 max-h-[360px] overflow-auto overscroll-contain border-y border-slate-800/80">
        <table className="w-full min-w-[820px] text-left text-xs text-slate-300">
          <thead className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/95 text-[11px] uppercase tracking-[0.12em] text-slate-500 backdrop-blur">
            <tr>
              <th className="px-3 py-2 font-medium">角色代码</th>
              <th className="px-3 py-2 text-right font-medium">运行次数</th>
              <th className="px-3 py-2 text-right font-medium">成本</th>
              <th className="px-3 py-2 text-right font-medium">提示词令牌</th>
              <th className="px-3 py-2 text-right font-medium">补全令牌</th>
              <th className="px-3 py-2 text-right font-medium">总令牌</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80">
            {roleBreakdown.map((item) => (
              <tr key={item.role_code} className="hover:bg-slate-800/25">
                <td className="max-w-[160px] truncate px-3 py-2 font-mono text-[11px] font-medium text-slate-100" title={item.role_code || "未分配"}>{item.role_code || "未分配"}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatTokenCount(item.run_count)}</td>
                <td className="px-3 py-2 text-right font-medium tabular-nums text-slate-100">
                  {formatUsd(item.total_estimated_cost_usd)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{formatTokenCount(item.prompt_tokens)}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatTokenCount(item.completion_tokens)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{formatTokenCount(item.total_tokens)}</td>
              </tr>
            ))}
            {roleBreakdown.length === 0 ? (
              <tr>
                <td className="px-3 py-5 text-center text-slate-500" colSpan={6}>
                  当前没有角色维度可汇总数据。
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
