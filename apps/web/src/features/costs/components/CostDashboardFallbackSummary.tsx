import { formatTokenCount } from "../../../lib/format";
import type { ProjectCostDashboardSnapshot } from "../types";

type CostDashboardFallbackSummaryProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardFallbackSummary(props: CostDashboardFallbackSummaryProps) {
  const { fallback_contract: fallbackContract } = props.snapshot;

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-400">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">成本估算说明</h3>
          <p className="mt-1 text-xs text-slate-500">当供应商数据暂缺时，系统会使用估算值保持成本视图可读。</p>
        </div>
        <span className="text-xs font-medium text-slate-400">
          {fallbackContract.fallback_active ? "估算中" : "已回传"}
        </span>
      </div>

      <p className="mt-3 max-h-28 overflow-y-auto break-words pr-2 text-xs leading-5 text-slate-500">
        {fallbackContract.fallback_reason}
      </p>

      <dl className="mt-4 space-y-3 border-t border-slate-800 pt-3">
        <FallbackRow label="供应商数据运行" value={fallbackContract.provider_reported_run_count} />
        <FallbackRow label="估算数据运行" value={fallbackContract.heuristic_run_count} />
        <FallbackRow label="待补齐运行" value={fallbackContract.missing_mode_run_count} />
      </dl>
    </section>
  );
}

function FallbackRow(props: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-xs text-slate-500">{props.label}</dt>
      <dd className="font-medium tabular-nums text-slate-300">{formatTokenCount(props.value)}</dd>
    </div>
  );
}
