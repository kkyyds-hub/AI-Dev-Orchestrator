import { StatusBadge } from "../../../components/StatusBadge";
import type { SkillRegistrySnapshot } from "../types";

type SkillRegistryHeaderProps = {
  selectedProjectName: string | null;
  registry: SkillRegistrySnapshot | null;
};

export function SkillRegistryHeader(props: SkillRegistryHeaderProps) {
  return (
    <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
          V3 Day13 Skill Registry
        </p>
        <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
          Skill 注册中心与角色绑定
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-slate-300">
          Day13 把 Day05 的默认 Skill 槽位升级为正式注册中心：Skill 具备名称、版本、用途、适用角色和启停状态，并且可以在项目内绑定到具体角色。
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
        <StatusBadge
          label={props.selectedProjectName ? `当前项目：${props.selectedProjectName}` : "当前未选项目"}
          tone={props.selectedProjectName ? "info" : "neutral"}
        />
        <StatusBadge
          label={props.registry ? `已加载 ${props.registry.total_skill_count} 个 Skill` : "注册中心加载中"}
          tone={props.registry ? "success" : "warning"}
        />
      </div>
    </header>
  );
}
