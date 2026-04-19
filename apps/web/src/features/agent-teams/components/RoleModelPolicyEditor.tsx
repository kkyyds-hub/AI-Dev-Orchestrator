import type { RoleModelPreference, RoleModelStageOverride } from "../types";

const MODEL_TIERS: Array<"economy" | "balanced" | "premium"> = [
  "economy",
  "balanced",
  "premium",
];

type RoleModelPolicyEditorProps = {
  rolePreferences: RoleModelPreference[];
  stageOverrides: RoleModelStageOverride[];
  onChangeRolePreferences: (items: RoleModelPreference[]) => void;
  onChangeStageOverrides: (items: RoleModelStageOverride[]) => void;
};

export function RoleModelPolicyEditor(props: RoleModelPolicyEditorProps) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        Role Model Policy
      </div>
      <p className="mt-2 text-xs text-slate-400">
        保存后会写入 `/strategy/rules`，由 runtime strategy preview 与 worker 路由直接消费。
      </p>

      <div className="mt-3 space-y-3">
        {props.rolePreferences.map((item, index) => (
          <div
            key={`${item.role_code}-${index}`}
            className="grid gap-2 rounded-xl border border-slate-800 bg-slate-950/70 p-3 sm:grid-cols-[1fr_180px]"
          >
            <div className="text-sm text-slate-200">角色 {item.role_code}</div>
            <select
              value={item.model_tier}
              onChange={(event) => {
                const next = props.rolePreferences.slice();
                next[index] = {
                  ...item,
                  model_tier: event.target.value as RoleModelPreference["model_tier"],
                };
                props.onChangeRolePreferences(next);
              }}
              className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
            >
              {MODEL_TIERS.map((tier) => (
                <option key={tier} value={tier}>
                  {tier}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>

      {props.stageOverrides.length > 0 ? (
        <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
          <div className="text-xs text-slate-400">Stage Overrides</div>
          <div className="mt-2 space-y-2">
            {props.stageOverrides.map((item, index) => (
              <div
                key={`${item.stage}-${item.role_code}-${index}`}
                className="flex items-center justify-between gap-3 text-sm text-slate-200"
              >
                <span>
                  {item.stage} / {item.role_code}
                </span>
                <select
                  value={item.model_tier}
                  onChange={(event) => {
                    const next = props.stageOverrides.slice();
                    next[index] = {
                      ...item,
                      model_tier: event.target.value as RoleModelStageOverride["model_tier"],
                    };
                    props.onChangeStageOverrides(next);
                  }}
                  className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
                >
                  {MODEL_TIERS.map((tier) => (
                    <option key={tier} value={tier}>
                      {tier}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
