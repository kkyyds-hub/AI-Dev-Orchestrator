import type { TeamPolicy } from "../types";

export function TeamPolicyEditorCard(props: {
  policy: TeamPolicy;
  onChange: (policy: TeamPolicy) => void;
}) {
  return (
    <section id="team-collaboration-settings" className="scroll-mt-24 border-b border-[#333333] pb-5">
      <div>
        <h3 className="text-sm font-semibold text-slate-100">协作策略</h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          控制团队协作、交接和评审门禁方式。
        </p>
      </div>
      <div className="mt-4 divide-y divide-[#333333]">
        <label className="grid gap-3 py-3 text-sm md:grid-cols-[220px_minmax(0,1fr)]">
          <span className="text-slate-300">协作模式</span>
          <input
            value={props.policy.collaboration_mode}
            onChange={(event) =>
              props.onChange({
                ...props.policy,
                collaboration_mode: event.target.value,
              })
            }
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-slate-500"
          />
        </label>
        <label className="grid gap-3 py-3 text-sm md:grid-cols-[220px_minmax(0,1fr)]">
          <span className="text-slate-300">介入模式</span>
          <input
            value={props.policy.intervention_mode}
            onChange={(event) =>
              props.onChange({
                ...props.policy,
                intervention_mode: event.target.value,
              })
            }
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-slate-500"
          />
        </label>
        <label className="grid gap-3 py-3 text-sm md:grid-cols-[220px_minmax(0,1fr)]">
          <span className="text-slate-300">升级开关</span>
          <span className="inline-flex items-center gap-2 text-slate-300">
            <input
              type="checkbox"
              checked={props.policy.escalation_enabled}
              onChange={(event) =>
                props.onChange({
                  ...props.policy,
                  escalation_enabled: event.target.checked,
                })
              }
            />
            启用升级
          </span>
        </label>
        <label className="grid gap-3 py-3 text-sm md:grid-cols-[220px_minmax(0,1fr)]">
          <span className="text-slate-300">交接要求</span>
          <span className="inline-flex items-center gap-2 text-slate-300">
            <input
              type="checkbox"
              checked={props.policy.handoff_required}
              onChange={(event) =>
                props.onChange({
                  ...props.policy,
                  handoff_required: event.target.checked,
                })
              }
            />
            需要交接
          </span>
        </label>
        <label className="grid gap-3 py-3 text-sm md:grid-cols-[220px_minmax(0,1fr)]">
          <span className="text-slate-300">评审门禁</span>
          <input
            value={props.policy.review_gate}
            onChange={(event) =>
              props.onChange({
                ...props.policy,
                review_gate: event.target.value,
              })
            }
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-slate-500"
          />
        </label>
      </div>
    </section>
  );
}
