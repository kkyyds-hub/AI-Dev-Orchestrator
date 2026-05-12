import type { ProjectSkillBindingSnapshot } from "../types";

type RoleSkillBindingHeaderProps = {
  bindingSnapshot: ProjectSkillBindingSnapshot | null;
  projectName: string | null;
};

export function RoleSkillBindingHeader(props: RoleSkillBindingHeaderProps) {
  return (
    <header className="flex flex-col gap-4 border-b border-[#333333] pb-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
          角色绑定
        </p>
        <h3 className="text-lg font-semibold tracking-tight text-zinc-50">项目角色 Skill 绑定</h3>
        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
          为项目角色分配可用 Skill，并保留当前绑定版本。
        </p>
      </div>

      <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <RoleSkillBindingStat
          label="当前项目"
          value={props.projectName ?? props.bindingSnapshot?.project_name ?? "未命名项目"}
          hint="当前展示的项目详情"
        />
        <RoleSkillBindingStat
          label="角色数"
          value={String(props.bindingSnapshot?.total_roles ?? 0)}
          hint="项目角色目录中的总角色数"
        />
        <RoleSkillBindingStat
          label="绑定 Skill"
          value={String(props.bindingSnapshot?.total_bound_skills ?? 0)}
          hint="当前项目所有角色累计绑定的 Skill 数量"
        />
        <RoleSkillBindingStat
          label="待升级绑定"
          value={String(props.bindingSnapshot?.outdated_binding_count ?? 0)}
          hint="当前绑定版本落后于注册中心最新版本的 Skill 数量"
        />
      </dl>
    </header>
  );
}

function RoleSkillBindingStat(props: { label: string; value: string; hint: string }) {
  return (
    <div className="min-w-0 border-l border-[#333333] px-3 py-1">
      <dt className="text-xs uppercase tracking-[0.16em] text-zinc-500">{props.label}</dt>
      <dd className="mt-1 truncate text-sm font-medium text-zinc-100">{props.value}</dd>
      <dd className="mt-1 text-xs leading-5 text-zinc-600">{props.hint}</dd>
    </div>
  );
}
