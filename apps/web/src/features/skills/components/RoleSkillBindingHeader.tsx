import { MetricCard } from "../../../components/MetricCard";
import type { ProjectSkillBindingSnapshot } from "../types";

type RoleSkillBindingHeaderProps = {
  bindingSnapshot: ProjectSkillBindingSnapshot | null;
  projectName: string | null;
};

export function RoleSkillBindingHeader(props: RoleSkillBindingHeaderProps) {
  return (
    <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
          V3 Day13 Role Skill Binding
        </p>
        <h3 className="text-2xl font-semibold tracking-tight text-slate-50">
          项目详情中的角色 Skill 绑定
        </h3>
        <p className="max-w-3xl text-sm leading-6 text-slate-300">
          每个角色都可以绑定一个或多个 Skill，并保留自己当前使用的版本；当注册中心里的 Skill 升级后，这里也会标出哪些绑定需要手动同步到最新版。
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="当前项目"
          value={props.projectName ?? props.bindingSnapshot?.project_name ?? "未命名项目"}
          hint="当前展示的项目详情"
          tone="info"
        />
        <MetricCard
          label="角色数"
          value={String(props.bindingSnapshot?.total_roles ?? 0)}
          hint="项目角色目录中的总角色数"
        />
        <MetricCard
          label="绑定 Skill"
          value={String(props.bindingSnapshot?.total_bound_skills ?? 0)}
          hint="当前项目所有角色累计绑定的 Skill 数量"
          tone="success"
        />
        <MetricCard
          label="待升级绑定"
          value={String(props.bindingSnapshot?.outdated_binding_count ?? 0)}
          hint="当前绑定版本落后于注册中心最新版本的 Skill 数量"
          tone="warning"
        />
      </div>
    </header>
  );
}
