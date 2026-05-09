import type { TeamAssemblyMember } from "../types";

type TeamAssemblyEditorProps = {
  members: TeamAssemblyMember[];
  onChange: (members: TeamAssemblyMember[]) => void;
};

export function TeamAssemblyEditor(props: TeamAssemblyEditorProps) {
  return (
    <section className="border-b border-[#333333] pb-5">
      <div>
        <h3 className="text-sm font-semibold text-slate-100">角色分工</h3>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          配置团队角色、投入占比和是否参与运行。
        </p>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[680px] text-left text-sm">
          <thead className="border-b border-[#333333] text-xs text-slate-500">
            <tr>
              <th className="py-2 pr-4 font-medium">角色代码</th>
              <th className="px-4 py-2 font-medium">显示名</th>
              <th className="px-4 py-2 font-medium">投入占比</th>
              <th className="pl-4 py-2 font-medium">启用</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#333333]">
            {props.members.map((member, index) => (
              <tr key={`${member.role_code}-${index}`}>
                <td className="py-3 pr-4 font-mono text-xs text-slate-400">
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
                    className="w-full rounded border border-[#3a3a3a] bg-transparent px-2 py-1.5 text-sm text-slate-100 outline-none transition focus:border-slate-500"
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
                    className="w-28 rounded border border-[#3a3a3a] bg-transparent px-2 py-1.5 text-sm text-slate-100 outline-none transition focus:border-slate-500"
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
