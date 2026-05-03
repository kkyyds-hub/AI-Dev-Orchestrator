import type { TeamPolicy } from "../types";

export function TeamPolicyEditorCard(props: {
  policy: TeamPolicy;
  onChange: (policy: TeamPolicy) => void;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">团队策略</div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          <span>协作模式（collaboration_mode）</span>
          <input
            value={props.policy.collaboration_mode}
            onChange={(event) =>
              props.onChange({
                ...props.policy,
                collaboration_mode: event.target.value,
              })
            }
            className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          <span>介入模式（intervention_mode）</span>
          <input
            value={props.policy.intervention_mode}
            onChange={(event) =>
              props.onChange({
                ...props.policy,
                intervention_mode: event.target.value,
              })
            }
            className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          />
        </label>
      </div>
    </section>
  );
}
