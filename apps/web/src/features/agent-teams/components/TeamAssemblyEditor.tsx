import type { TeamAssemblyMember } from "../types";

type TeamAssemblyEditorProps = {
  members: TeamAssemblyMember[];
  onChange: (members: TeamAssemblyMember[]) => void;
};

export function TeamAssemblyEditor(props: TeamAssemblyEditorProps) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        Team Assembly
      </div>
      <p className="mt-2 text-xs text-slate-400">
        Day13 保存 team assembly 角色分工；Day14 将消费 enabled_role_codes 做聚合维度。
      </p>

      <div className="mt-3 space-y-3">
        {props.members.map((member, index) => (
          <div
            key={`${member.role_code}-${index}`}
            className="grid gap-2 rounded-xl border border-slate-800 bg-slate-950/70 p-3 sm:grid-cols-[1fr_120px_120px]"
          >
            <label className="flex flex-col gap-1 text-xs text-slate-400">
              <span>角色显示名</span>
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
                className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-400">
              <span>投入占比(%)</span>
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
                className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
              />
            </label>
            <label className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-200">
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
              启用 {member.role_code}
            </label>
          </div>
        ))}
      </div>
    </section>
  );
}
