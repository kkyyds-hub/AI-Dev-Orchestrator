import type { TeamControlCenterSnapshot } from "../types";

export function TeamControlDay14Prerequisites(props: {
  snapshot: TeamControlCenterSnapshot;
}) {
  return (
    <section
      data-testid="team-control-day14-prerequisites"
      className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-xs text-slate-300"
    >
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        Day14 前置条件
      </div>
      <div className="mt-2">
        已启用角色代码：{props.snapshot.day14_prerequisites.enabled_role_codes.join(", ") || "无"}
      </div>
      <div className="mt-1">
        预算策略字段：{props.snapshot.day14_prerequisites.budget_policy_keys.join(", ") || "无"}
      </div>
      <div className="mt-1">
        运行时消费路径：{props.snapshot.runtime_consumption_boundary.role_model_policy_paths.join(" ; ")}
      </div>
    </section>
  );
}
