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
    <section className="border-b border-[#333333] pb-5">
      <div>
        <h3 className="text-lg font-semibold text-zinc-50">线程成本明细</h3>
        <p className="mt-1 text-sm leading-6 text-zinc-500">按协作线程查看阶段、状态、责任角色与成本消耗。</p>
      </div>

      <div className="mt-4 max-h-[420px] overflow-auto overscroll-contain border-y border-[#333333]">
        <table className="w-full min-w-[1120px] text-left text-xs text-zinc-300">
          <thead className="sticky top-0 z-10 border-b border-[#333333] bg-[#171717]/95 text-[11px] uppercase tracking-[0.12em] text-zinc-500 backdrop-blur">
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
          <tbody className="divide-y divide-[#333333]">
            {threadBreakdown.map((item) => (
              <tr key={`${item.session_id}-${item.run_id}`} className="hover:bg-white/[0.02]">
                <td className="px-3 py-2 font-mono text-[11px] text-zinc-200" title={item.session_id}>
                  {shortId(item.session_id)}
                </td>
                <td className="px-3 py-2 font-mono text-[11px]" title={item.task_id}>
                  {shortId(item.task_id)}
                </td>
                <td className="px-3 py-2 font-mono text-[11px]" title={item.run_id}>
                  {shortId(item.run_id)}
                </td>
                <td className="max-w-[120px] truncate px-3 py-2" title={item.current_phase || "-"}>{item.current_phase || "-"}</td>
                <td className="max-w-[120px] truncate px-3 py-2" title={item.status || "-"}>{item.status || "-"}</td>
                <td className="max-w-[120px] truncate px-3 py-2" title={item.review_status || "-"}>{item.review_status || "-"}</td>
                <td className="max-w-[140px] truncate px-3 py-2" title={item.owner_role_code || "未分配"}>{item.owner_role_code || "未分配"}</td>
                <td className="px-3 py-2 text-right font-medium tabular-nums text-zinc-100">
                  {formatUsd(item.total_estimated_cost_usd)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{formatTokenCount(item.total_tokens)}</td>
                <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(item.updated_at)}</td>
              </tr>
            ))}
            {threadBreakdown.length === 0 ? (
              <tr>
                <td className="px-3 py-5 text-center text-zinc-500" colSpan={10}>
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