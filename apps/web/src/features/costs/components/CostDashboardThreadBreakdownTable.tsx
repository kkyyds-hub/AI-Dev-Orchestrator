import type { ProjectCostDashboardSnapshot } from "../types";
import { formatUsd } from "./costDashboardFormat";

type CostDashboardThreadBreakdownTableProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardThreadBreakdownTable(
  props: CostDashboardThreadBreakdownTableProps,
) {
  const { thread_breakdown: threadBreakdown } = props.snapshot;

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="text-sm font-semibold text-slate-100">线程（agent session）维度聚合</h3>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full text-left text-xs text-slate-300">
          <thead className="text-slate-400">
            <tr>
              <th className="px-2 py-1">会话 ID</th>
              <th className="px-2 py-1">阶段</th>
              <th className="px-2 py-1">状态</th>
              <th className="px-2 py-1">角色</th>
              <th className="px-2 py-1">成本（USD）</th>
              <th className="px-2 py-1">令牌</th>
            </tr>
          </thead>
          <tbody>
            {threadBreakdown.map((item) => (
              <tr key={item.session_id} className="border-t border-slate-800">
                <td className="px-2 py-1 font-mono">{item.session_id.slice(0, 8)}...</td>
                <td className="px-2 py-1">{item.current_phase}</td>
                <td className="px-2 py-1">
                  {item.status} / {item.review_status}
                </td>
                <td className="px-2 py-1">{item.owner_role_code}</td>
                <td className="px-2 py-1">{formatUsd(item.total_estimated_cost_usd)}</td>
                <td className="px-2 py-1">{item.total_tokens}</td>
              </tr>
            ))}
            {threadBreakdown.length === 0 ? (
              <tr className="border-t border-slate-800">
                <td className="px-2 py-2 text-slate-500" colSpan={6}>
                  当前没有线程维度可聚合数据。
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
