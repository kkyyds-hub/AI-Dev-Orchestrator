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
    <section className="border-b border-[#333333] pb-5">
      <div>
        <h3 className="text-sm font-semibold text-slate-100">模型策略</h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          为角色和阶段覆盖项选择模型档位。
        </p>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        保存后会写入 `/strategy/rules`，由 runtime strategy preview 与 worker 路由直接消费。
      </p>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead className="border-b border-[#333333] text-xs text-slate-500">
            <tr>
              <th className="py-2 pr-4 font-medium">角色</th>
              <th className="px-4 py-2 font-medium">模型档位</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#333333]">
            {props.rolePreferences.map((item, index) => (
              <tr key={`${item.role_code}-${index}`}>
                <td className="py-3 pr-4 font-mono text-xs text-slate-400">
                  {item.role_code}
                </td>
                <td className="px-4 py-3">
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
                    className="w-44 rounded border border-[#3a3a3a] bg-slate-950 px-2 py-1.5 text-sm text-slate-100 outline-none transition focus:border-slate-500"
                  >
                    {MODEL_TIERS.map((tier) => (
                      <option key={tier} value={tier}>
                        {tier}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {props.stageOverrides.length > 0 ? (
        <div className="mt-6 overflow-x-auto">
          <div className="text-xs font-medium text-slate-500">阶段覆盖</div>
          <table className="mt-2 w-full min-w-[620px] text-left text-sm">
            <thead className="border-b border-[#333333] text-xs text-slate-500">
              <tr>
                <th className="py-2 pr-4 font-medium">阶段</th>
                <th className="px-4 py-2 font-medium">角色</th>
                <th className="px-4 py-2 font-medium">模型档位</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#333333]">
              {props.stageOverrides.map((item, index) => (
                <tr key={`${item.stage}-${item.role_code}-${index}`}>
                  <td className="py-3 pr-4 text-slate-300">{item.stage}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400">
                    {item.role_code}
                  </td>
                  <td className="px-4 py-3">
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
                      className="w-44 rounded border border-[#3a3a3a] bg-slate-950 px-2 py-1.5 text-sm text-slate-100 outline-none transition focus:border-slate-500"
                    >
                      {MODEL_TIERS.map((tier) => (
                        <option key={tier} value={tier}>
                          {tier}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
      ) : null}
    </section>
  );
}
