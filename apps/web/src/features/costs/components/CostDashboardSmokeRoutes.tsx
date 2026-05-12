import type { ProjectCostDashboardSnapshot } from "../types";

type CostDashboardSmokeRoutesProps = {
  snapshot: ProjectCostDashboardSnapshot;
};

export function CostDashboardSmokeRoutes(props: CostDashboardSmokeRoutesProps) {
  return (
    <section className="border-b border-[#333333] pb-5 text-sm text-zinc-400">
      <h3 className="text-sm font-semibold text-zinc-200">数据记录</h3>
      <p className="mt-1 text-xs text-zinc-500">展示最近一次成本数据检查记录。</p>
      <div className="mt-3 space-y-2">
        {props.snapshot.day15_smoke_routes.map((route, index) => (
          <code
            key={route}
            className="block truncate border-l border-[#333333] py-1 pl-2 text-[11px] text-zinc-500"
          >
            检查记录 {index + 1}
          </code>
        ))}
        {props.snapshot.day15_smoke_routes.length === 0 ? (
          <p className="text-xs text-zinc-500">暂无检查记录。</p>
        ) : null}
      </div>
    </section>
  );
}