import type { ProjectCostDashboardSnapshot } from "../types";
import { formatUsd } from "./costDashboardFormat";

type CostDashboardRoleBreakdownTableProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardRoleBreakdownTable(props: CostDashboardRoleBreakdownTableProps) {
  const { role_breakdown: roleBreakdown } = props.snapshot;

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="text-sm font-semibold text-slate-100">角色维度成本聚合</h3>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full text-left text-xs text-slate-300">
          <thead className="text-slate-400">
            <tr>
              <th className="px-2 py-1">角色代码</th>
              <th className="px-2 py-1">运行次数</th>
              <th className="px-2 py-1">成本（USD）</th>
              <th className="px-2 py-1">令牌</th>
            </tr>
          </thead>
          <tbody>
            {roleBreakdown.map((item) => (
              <tr key={item.role_code} className="border-t border-slate-800">
                <td className="px-2 py-1">{item.role_code}</td>
                <td className="px-2 py-1">{item.run_count}</td>
                <td className="px-2 py-1">{formatUsd(item.total_estimated_cost_usd)}</td>
                <td className="px-2 py-1">{item.total_tokens}</td>
              </tr>
            ))}
            {roleBreakdown.length === 0 ? (
              <tr className="border-t border-slate-800">
                <td className="px-2 py-2 text-slate-500" colSpan={4}>
                  当前没有角色维度可聚合数据。
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
