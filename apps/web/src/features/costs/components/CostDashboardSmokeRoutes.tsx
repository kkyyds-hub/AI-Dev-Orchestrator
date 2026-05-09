import type { ProjectCostDashboardSnapshot } from "../types";

type CostDashboardSmokeRoutesProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardSmokeRoutes(props: CostDashboardSmokeRoutesProps) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-950/25 p-4 text-sm text-slate-400">
      <h3 className="text-sm font-semibold text-slate-200">诊断路径</h3>
      <p className="mt-1 text-xs text-slate-500">用于排查聚合链路的弱化技术信息，不参与主要决策。</p>
      <div className="mt-3 space-y-2">
        {props.snapshot.day15_smoke_routes.map((route) => (
          <code
            key={route}
            className="block truncate rounded-md border border-slate-800 bg-slate-950/50 px-2 py-1 text-[11px] text-slate-500"
            title={route}
          >
            {route}
          </code>
        ))}
        {props.snapshot.day15_smoke_routes.length === 0 ? (
          <p className="text-xs text-slate-500">暂无诊断路径。</p>
        ) : null}
      </div>
    </section>
  );
}
