import type { ProjectCostDashboardSnapshot } from "../types";

type CostDashboardSmokeRoutesProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardSmokeRoutes(props: CostDashboardSmokeRoutesProps) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/25 p-4 text-sm text-slate-400">
      <h3 className="text-sm font-semibold text-slate-200">数据记录</h3>
      <p className="mt-1 text-xs text-slate-500">保留最近一次成本数据更新记录。</p>
      <div className="mt-3 space-y-2">
        {props.snapshot.day15_smoke_routes.map((route, index) => (
          <code
            key={route}
            className="block truncate rounded-md border border-slate-800 bg-slate-950/50 px-2 py-1 text-[11px] text-slate-500"
          >
            检查记录 {index + 1}
          </code>
        ))}
        {props.snapshot.day15_smoke_routes.length === 0 ? (
          <p className="text-xs text-slate-500">暂无检查记录。</p>
        ) : null}
      </div>
    </section>
  );
}
