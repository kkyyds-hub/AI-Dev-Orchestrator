import type { TeamControlCenterSnapshot } from "../types";

export function TeamControlDay14Prerequisites(props: {
  snapshot: TeamControlCenterSnapshot;
}) {
  return (
    <section
      data-testid="team-control-day14-prerequisites"
      className="border-b border-[#333333] pb-4 text-xs text-slate-400"
    >
      <h3 className="text-sm font-semibold text-slate-100">运行前置条件</h3>
      <dl className="mt-3 space-y-3">
        <div>
          <dt className="text-slate-500">已启用角色代码</dt>
          <dd className="mt-1 max-h-24 overflow-y-auto break-words pr-2 leading-5 text-slate-300">
            {props.snapshot.day14_prerequisites.enabled_role_codes.join(", ") || "无"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">预算策略项</dt>
          <dd className="mt-1 max-h-24 overflow-y-auto break-words pr-2 leading-5 text-slate-300">
            {props.snapshot.day14_prerequisites.budget_policy_keys.join(", ") || "无"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">策略生效范围</dt>
          <dd className="mt-1 max-h-24 overflow-y-auto break-words pr-2 leading-5 text-slate-300">
            {props.snapshot.runtime_consumption_boundary.role_model_policy_paths.length} 项策略路径
          </dd>
        </div>
      </dl>
    </section>
  );
}
