import { MetricCard } from "../../../components/MetricCard";
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
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        label="Skill 总数"
        value={String(props.registry?.total_skill_count ?? 0)}
        hint="正式注册到 Day13 Skill 中心的能力条目"
        tone="info"
      />
      <MetricCard
        label="已启用"
        value={enabledSkillRatio}
        hint="当前可用于角色绑定的 Skill / 全部 Skill"
        tone="success"
      />
      <MetricCard
        label="版本记录"
        value={String(props.registry?.version_record_count ?? 0)}
        hint="用于回看 Skill 变更历史和项目所用版本"
        tone="warning"
      />
      <MetricCard
        label="当前项目绑定"
        value={String(props.bindingSnapshot?.total_bound_skills ?? 0)}
        hint={props.selectedProjectName ? "当前项目所有角色累计绑定的 Skill 数" : "选择项目后可查看角色绑定情况"}
      />
    </div>
  );
}
