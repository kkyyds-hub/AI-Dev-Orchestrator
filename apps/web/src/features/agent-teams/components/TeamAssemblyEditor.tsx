import type { TeamAssemblyMember } from "../types";

type TeamAssemblyEditorProps = {
  members: TeamAssemblyMember[];
  onChange: (members: TeamAssemblyMember[]) => void;
};

export function TeamAssemblyEditor(props: TeamAssemblyEditorProps) {
  return (
    <section id="team-role-settings" className="scroll-mt-24 rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-100">角色分工</h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          配置团队角色、投入占比和是否参与运行。
        </p>
      </div>

      <div className="mt-4 max-h-[360px] min-w-0 overflow-auto overscroll-contain rounded-xl border border-slate-800 bg-slate-950/30">
        <table className="w-full min-w-[680px] text-left text-sm">
          <thead className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/95 text-xs text-slate-500 backdrop-blur">
            <tr>
              <th className="py-2 pr-4 font-medium">角色代码</th>
              <th className="px-4 py-2 font-medium">显示名</th>
              <th className="px-4 py-2 font-medium">投入占比</th>
              <th className="pl-4 py-2 font-medium">启用</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {props.members.map((member, index) => (
              <tr key={`${member.role_code}-${index}`}>
                <td className="max-w-[160px] truncate py-3 pr-4 font-mono text-xs text-slate-400" title={member.role_code}>
                  {member.role_code}
                </td>
                <td className="px-4 py-3">
                  <input
                    value={member.display_name}
                    onChange={(event) => {
                      const next = props.members.slice();
                      next[index] = {
                        ...member,
                        display_name: event.target.value,
                      };
                      props.onChange(next);
                    }}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950/60 px-2 py-1.5 text-sm text-slate-100 outline-none transition focus:border-slate-500"
                  />
                </td>
                <td className="px-4 py-3">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={member.allocation_percent}
                    onChange={(event) => {
                      const next = props.members.slice();
                      next[index] = {
                        ...member,
                        allocation_percent: Number(event.target.value || 0),
                      };
                      props.onChange(next);
                    }}
                    className="w-28 rounded-lg border border-slate-700 bg-slate-950/60 px-2 py-1.5 text-sm text-slate-100 outline-none transition focus:border-slate-500"
                  />
                </td>
                <td className="pl-4 py-3">
                  <label className="inline-flex items-center gap-2 text-sm text-slate-300">
                    <input
                      type="checkbox"
                      checked={member.enabled}
                      onChange={(event) => {
                        const next = props.members.slice();
                        next[index] = {
                          ...member,
                          enabled: event.target.checked,
                        };
                        props.onChange(next);
                      }}
                    />
                    参与
                  </label>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
