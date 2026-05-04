import type { ProjectCostDashboardSnapshot } from "../types";

type CostDashboardSmokeRoutesProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardSmokeRoutes(props: CostDashboardSmokeRoutesProps) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="text-sm font-semibold text-slate-100">Day15 冒烟路由</h3>
      <div className="mt-2 flex flex-wrap gap-2">
        {props.snapshot.day15_smoke_routes.map((route) => (
          <code
            key={route}
            className="rounded-lg border border-slate-700 bg-slate-950/70 px-2 py-1 text-xs text-slate-300"
          >
            {route}
          </code>
        ))}
      </div>
    </section>
  );
}
