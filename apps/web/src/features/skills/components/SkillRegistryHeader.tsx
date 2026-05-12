import type { SkillRegistrySnapshot } from "../types";

type SkillRegistryHeaderProps = {
  selectedProjectName: string | null;
  registry: SkillRegistrySnapshot | null;
};

export function SkillRegistryHeader(props: SkillRegistryHeaderProps) {
  return (
    <header className="flex flex-col gap-4 border-b border-[#333333] pb-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
          技能
        </p>
        <h2 className="text-xl font-semibold tracking-tight text-zinc-50">Skill 与角色绑定</h2>
        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
          在当前项目治理视图内维护 Skill 条目，并把可用能力绑定到对应角色。
        </p>
      </div>

      <dl className="grid gap-3 sm:grid-cols-2 lg:min-w-[320px]">
        <HeaderStat
          label="当前项目"
          value={props.selectedProjectName ?? "未选择项目"}
        />
        <HeaderStat
          label="注册 Skill"
          value={props.registry ? `${props.registry.total_skill_count} 个` : "加载中"}
        />
      </dl>
    </header>
  );
}

function HeaderStat(props: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-l border-[#333333] px-3 py-1">
      <dt className="text-xs uppercase tracking-[0.16em] text-zinc-500">{props.label}</dt>
      <dd className="mt-1 truncate text-sm font-medium text-zinc-100">{props.value}</dd>
    </div>
  );
}
