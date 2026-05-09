import { formatDateTime, formatTokenCount } from "../../../lib/format";
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
    <section className="rounded-xl border border-slate-800 bg-slate-900/35 p-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-100">线程成本明细</h3>
        <p className="mt-1 text-xs text-slate-500">按协作线程查看阶段、状态、责任角色与成本消耗。</p>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-xs text-slate-300">
          <thead className="border-b border-slate-800 text-[11px] uppercase tracking-[0.12em] text-slate-500">
            <tr>
              <th className="px-3 py-2 font-medium">线程 ID</th>
              <th className="px-3 py-2 font-medium">任务 ID</th>
              <th className="px-3 py-2 font-medium">运行 ID</th>
              <th className="px-3 py-2 font-medium">阶段</th>
              <th className="px-3 py-2 font-medium">状态</th>
              <th className="px-3 py-2 font-medium">评审</th>
              <th className="px-3 py-2 font-medium">角色</th>
              <th className="px-3 py-2 text-right font-medium">成本</th>
              <th className="px-3 py-2 text-right font-medium">总令牌</th>
              <th className="px-3 py-2 font-medium">更新时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80">
            {threadBreakdown.map((item) => (
              <tr key={`${item.session_id}-${item.run_id}`} className="hover:bg-slate-800/25">
                <td className="px-3 py-2 font-mono text-[11px] text-slate-200" title={item.session_id}>
                  {shortId(item.session_id)}
                </td>
                <td className="px-3 py-2 font-mono text-[11px]" title={item.task_id}>
                  {shortId(item.task_id)}
                </td>
                <td className="px-3 py-2 font-mono text-[11px]" title={item.run_id}>
                  {shortId(item.run_id)}
                </td>
                <td className="px-3 py-2">{item.current_phase || "-"}</td>
                <td className="px-3 py-2">{item.status || "-"}</td>
                <td className="px-3 py-2">{item.review_status || "-"}</td>
                <td className="px-3 py-2">{item.owner_role_code || "未分配"}</td>
                <td className="px-3 py-2 text-right font-medium tabular-nums text-slate-100">
                  {formatUsd(item.total_estimated_cost_usd)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{formatTokenCount(item.total_tokens)}</td>
                <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(item.updated_at)}</td>
              </tr>
            ))}
            {threadBreakdown.length === 0 ? (
              <tr>
                <td className="px-3 py-5 text-center text-slate-500" colSpan={10}>
                  当前没有线程维度可汇总数据。
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function shortId(value: string) {
  if (!value) {
    return "-";
  }

  return value.length > 12 ? `${value.slice(0, 8)}...` : value;
}
