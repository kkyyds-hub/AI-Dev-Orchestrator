import type { BudgetPolicy } from "../types";

export function BudgetPolicyEditorCard(props: {
  policy: BudgetPolicy;
  onChange: (policy: BudgetPolicy) => void;
}) {
  return (
    <section className="border-b border-[#333333] pb-5">
      <div>
        <h3 className="text-sm font-semibold text-slate-100">预算策略</h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          设置运行预算、硬停止和预算压力模式。
        </p>
      </div>
      <div className="mt-4 divide-y divide-[#333333]">
        <label className="grid gap-3 py-3 text-sm md:grid-cols-[220px_minmax(0,1fr)]">
          <span className="text-slate-300">每日预算美元</span>
          <input
            type="number"
            value={props.policy.daily_budget_usd}
            onChange={(event) =>
              props.onChange({
                ...props.policy,
                daily_budget_usd: Number(event.target.value || 0),
              })
            }
            className="w-40 rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-slate-500"
          />
        </label>
        <label className="grid gap-3 py-3 text-sm md:grid-cols-[220px_minmax(0,1fr)]">
          <span className="text-slate-300">单次运行预算美元</span>
          <input
            type="number"
            value={props.policy.per_run_budget_usd}
            onChange={(event) =>
              props.onChange({
                ...props.policy,
                per_run_budget_usd: Number(event.target.value || 0),
              })
            }
            className="w-40 rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-slate-500"
          />
        </label>
        <label className="grid gap-3 py-3 text-sm md:grid-cols-[220px_minmax(0,1fr)]">
          <span className="text-slate-300">硬停止</span>
          <span className="inline-flex items-center gap-2 text-slate-300">
            <input
              type="checkbox"
              checked={props.policy.hard_stop_enabled}
              onChange={(event) =>
                props.onChange({
                  ...props.policy,
                  hard_stop_enabled: event.target.checked,
                })
              }
            />
            达到预算后停止
          </span>
        </label>
        <label className="grid gap-3 py-3 text-sm md:grid-cols-[220px_minmax(0,1fr)]">
          <span className="text-slate-300">压力模式</span>
          <input
            value={props.policy.pressure_mode}
            onChange={(event) =>
              props.onChange({
                ...props.policy,
                pressure_mode: event.target.value,
              })
            }
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-slate-500"
          />
        </label>
      </div>
    </section>
  );
}
