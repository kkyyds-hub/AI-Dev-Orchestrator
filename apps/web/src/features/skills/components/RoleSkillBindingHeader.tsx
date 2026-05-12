import type { ProjectSkillBindingSnapshot } from "../types";

type RoleSkillBindingHeaderProps = {
  bindingSnapshot: ProjectSkillBindingSnapshot | null;
  projectName: string | null;
};

export function RoleSkillBindingHeader(props: RoleSkillBindingHeaderProps) {
  return (
    <header className="flex flex-col gap-4 border-b border-[#333333] pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
          角色绑定
        </p>
        <h3 className="text-2xl font-semibold tracking-tight text-zinc-50">
          项目角色 Skill 绑定
        </h3>
        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
          为每个角色绑定一个或多个 Skill，并保留当前使用版本；注册中心升级后，可在这里查看并同步到最新版本。
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
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
      </div>
    </header>
  );
}

function RoleSkillBindingStat(props: { label: string; value: string; hint: string }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.16em] text-zinc-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-zinc-100">{props.value}</div>
      <div className="mt-1 text-xs leading-5 text-zinc-600">{props.hint}</div>
    </div>
  );
}