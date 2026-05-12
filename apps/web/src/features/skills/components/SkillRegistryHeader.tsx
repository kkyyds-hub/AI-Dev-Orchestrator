import type { SkillRegistrySnapshot } from "../types";

type SkillRegistryHeaderProps = {
  selectedProjectName: string | null;
  registry: SkillRegistrySnapshot | null;
};

export function SkillRegistryHeader(props: SkillRegistryHeaderProps) {
  return (
    <header className="flex flex-col gap-4 border-b border-[#333333] pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
          技能
        </p>
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50">
          Skill 注册中心与角色绑定
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
          维护可复用的 Skill 能力条目，并在当前项目内绑定到具体角色，便于团队按职责选择合适的执行能力。
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <HeaderStat
          label="当前项目"
          value={props.selectedProjectName ?? "未选择项目"}
        />
        <HeaderStat
          label="注册 Skill"
          value={props.registry ? `${props.registry.total_skill_count} 个` : "加载中"}
        />
      </div>
    </header>
  );
}

function HeaderStat(props: { label: string; value: string }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-zinc-100">{props.value}</div>
    </div>
  );
}