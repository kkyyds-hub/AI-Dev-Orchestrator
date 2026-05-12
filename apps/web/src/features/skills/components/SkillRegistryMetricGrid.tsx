import type { ProjectSkillBindingSnapshot, SkillRegistrySnapshot } from "../types";

type SkillRegistryMetricGridProps = {
  registry: SkillRegistrySnapshot | null;
  bindingSnapshot: ProjectSkillBindingSnapshot | null;
  selectedProjectName: string | null;
};

export function SkillRegistryMetricGrid(props: SkillRegistryMetricGridProps) {
  const enabledSkillRatio = props.registry?.total_skill_count
    ? `${props.registry.enabled_skill_count} / ${props.registry.total_skill_count}`
    : "0 / 0";

  return (
    <dl className="grid gap-x-5 gap-y-3 border-b border-[#333333] pb-4 md:grid-cols-2 xl:grid-cols-4">
      <SkillRegistryStat
        label="Skill 总数"
        value={String(props.registry?.total_skill_count ?? 0)}
        hint="正式注册的能力条目"
      />
      <SkillRegistryStat
        label="已启用"
        value={enabledSkillRatio}
        hint="当前可用于角色绑定的 Skill / 全部 Skill"
      />
      <SkillRegistryStat
        label="版本记录"
        value={String(props.registry?.version_record_count ?? 0)}
        hint="用于回看 Skill 变更历史和项目所用版本"
      />
      <SkillRegistryStat
        label="当前项目绑定"
        value={String(props.bindingSnapshot?.total_bound_skills ?? 0)}
        hint={props.selectedProjectName ? "当前项目所有角色累计绑定的 Skill 数" : "选择项目后可查看角色绑定情况"}
      />
    </dl>
  );
}

function SkillRegistryStat(props: { label: string; value: string; hint: string }) {
  return (
    <div className="min-w-0 border-l border-[#333333] px-3 py-1">
      <dt className="text-xs uppercase tracking-[0.16em] text-zinc-500">{props.label}</dt>
      <dd className="mt-1 text-base font-semibold tracking-tight text-zinc-100">{props.value}</dd>
      <dd className="mt-1 text-xs leading-5 text-zinc-600">{props.hint}</dd>
    </div>
  );
}
