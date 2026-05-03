import type { BudgetPolicy } from "../types";

export function BudgetPolicyEditorCard(props: {
  policy: BudgetPolicy;
  onChange: (policy: BudgetPolicy) => void;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">预算策略</div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          <span>每日预算美元（daily_budget_usd）</span>
          <input
            type="number"
            value={props.policy.daily_budget_usd}
            onChange={(event) =>
              props.onChange({
                ...props.policy,
                daily_budget_usd: Number(event.target.value || 0),
              })
            }
            className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          <span>单次运行预算美元（per_run_budget_usd）</span>
          <input
            type="number"
            value={props.policy.per_run_budget_usd}
            onChange={(event) =>
              props.onChange({
                ...props.policy,
                per_run_budget_usd: Number(event.target.value || 0),
              })
            }
            className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          />
        </label>
      </div>
    </section>
  );
}
