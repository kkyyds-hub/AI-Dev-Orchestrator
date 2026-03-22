import { useMemo, useState } from "react";

import { MetricCard } from "../../components/MetricCard";
import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { RoleEditorDrawer } from "./RoleEditorDrawer";
import {
  useProjectRoleCatalog,
  useSystemRoleCatalog,
  useUpdateProjectRoleConfig,
} from "./hooks";
import type {
  ProjectRoleConfig,
  ProjectRoleUpdateInput,
  SystemRoleCatalogItem,
} from "./types";
import { ROLE_CODE_LABELS } from "./types";

type RoleCatalogPageProps = {
  selectedProjectId: string | null;
  selectedProjectName: string | null;
};

export function RoleCatalogPage(props: RoleCatalogPageProps) {
  const systemRoleQuery = useSystemRoleCatalog();
  const projectRoleQuery = useProjectRoleCatalog(props.selectedProjectId);
  const updateRoleMutation = useUpdateProjectRoleConfig(props.selectedProjectId);
  const [editingRoleCode, setEditingRoleCode] = useState<string | null>(null);

  const systemRoles = systemRoleQuery.data ?? [];
  const projectRoles = projectRoleQuery.data?.roles ?? [];
  const editingRole =
    projectRoles.find((role) => role.role_code === editingRoleCode) ?? null;
  const editingSystemRole =
    systemRoles.find((role) => role.code === editingRoleCode) ?? null;

  const disabledRoleCount = useMemo(() => {
    if (!projectRoleQuery.data) {
      return systemRoles.filter((role) => !role.enabled_by_default).length;
    }

    return (
      projectRoleQuery.data.available_role_count - projectRoleQuery.data.enabled_role_count
    );
  }, [projectRoleQuery.data, systemRoles]);

  const handleSaveRole = async (payload: ProjectRoleUpdateInput) => {
    if (!editingRole) {
      throw new Error("当前没有可保存的角色配置。");
    }

    await updateRoleMutation.mutateAsync({
      roleCode: editingRole.role_code,
      payload,
    });
  };

  return (
    <section className="space-y-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-xl shadow-slate-950/20">
      <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
            V3 Day05 Role Catalog
          </p>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-50">
            角色目录与身份配置模型
          </h2>
          <p className="max-w-3xl text-sm leading-6 text-slate-300">
            Day05 把“谁负责什么”变成正式配置对象：系统提供最小角色目录，项目可以选择启用哪些角色，并查看/编辑职责边界、输入输出边界和默认 Skill 占位。
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <StatusBadge
            label={props.selectedProjectName ? `当前项目：${props.selectedProjectName}` : "当前未选项目"}
            tone={props.selectedProjectName ? "info" : "neutral"}
          />
          <StatusBadge
            label={projectRoleQuery.data ? "项目角色配置已接入" : "系统目录只读模式"}
            tone={projectRoleQuery.data ? "success" : "warning"}
          />
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="系统角色数"
          value={String(systemRoles.length)}
          hint="Day05 的最小内置角色目录"
          tone="info"
        />
        <MetricCard
          label="项目已启用"
          value={String(projectRoleQuery.data?.enabled_role_count ?? 0)}
          hint={props.selectedProjectName ? "当前项目启用的角色数" : "选择项目后可查看"}
          tone="success"
        />
        <MetricCard
          label="项目未启用"
          value={String(disabledRoleCount)}
          hint="可在角色编辑抽屉中启用或停用"
          tone="warning"
        />
        <MetricCard
          label="目录模式"
          value={props.selectedProjectName ? "项目配置" : "系统只读"}
          hint="Day05 不涉及任务调度与 Skill 引擎"
        />
      </div>

      {systemRoleQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          系统角色目录加载失败：{systemRoleQuery.error.message}
        </div>
      ) : null}

      {props.selectedProjectId && projectRoleQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm leading-6 text-rose-100">
          项目角色配置加载失败：{projectRoleQuery.error.message}
        </div>
      ) : null}

      {!props.selectedProjectId ? (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-4 text-sm leading-6 text-slate-400">
          还没有选中项目。当前先展示系统内置角色目录；在上方老板首页中选择项目后，就可以进入该项目的角色启用与身份配置编辑。
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        {(props.selectedProjectId ? projectRoles : systemRoles).map((role) => {
          const projectRole = isProjectRoleConfig(role) ? role : null;
          const systemOnlyRole: SystemRoleCatalogItem | null =
            projectRole === null ? (role as SystemRoleCatalogItem) : null;
          const systemRole: SystemRoleCatalogItem | null = projectRole
            ? systemRoles.find((item) => item.code === projectRole.role_code) ?? null
            : systemOnlyRole;

          return (
            <RoleCard
              key={projectRole ? projectRole.id : systemOnlyRole?.code ?? roleNameFallback(role)}
              projectRole={projectRole}
              systemRole={systemRole}
              projectSelected={props.selectedProjectId !== null}
              onEdit={() =>
                setEditingRoleCode(projectRole?.role_code ?? systemOnlyRole?.code ?? null)
              }
            />
          );
        })}
      </div>

      {props.selectedProjectId && projectRoleQuery.isLoading && !projectRoleQuery.data ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4 text-sm leading-6 text-slate-400">
          正在加载项目角色目录...
        </div>
      ) : null}

      {systemRoleQuery.isLoading && !systemRoleQuery.data ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4 text-sm leading-6 text-slate-400">
          正在加载系统内置角色目录...
        </div>
      ) : null}

      <RoleEditorDrawer
        open={editingRole !== null}
        role={editingRole}
        systemRole={editingSystemRole}
        projectName={props.selectedProjectName}
        isSaving={updateRoleMutation.isPending}
        onClose={() => setEditingRoleCode(null)}
        onSave={handleSaveRole}
      />
    </section>
  );
}

function RoleCard(props: {
  projectRole: ProjectRoleConfig | null;
  systemRole: SystemRoleCatalogItem | null;
  projectSelected: boolean;
  onEdit: () => void;
}) {
  const roleName = props.projectRole?.name ?? props.systemRole?.name ?? "角色";
  const roleCode = props.projectRole?.role_code ?? props.systemRole?.code ?? "unknown";
  const summary = props.projectRole?.summary ?? props.systemRole?.summary ?? "—";
  const responsibilities =
    props.projectRole?.responsibilities ?? props.systemRole?.responsibilities ?? [];
  const inputBoundary =
    props.projectRole?.input_boundary ?? props.systemRole?.input_boundary ?? [];
  const outputBoundary =
    props.projectRole?.output_boundary ?? props.systemRole?.output_boundary ?? [];
  const skillSlots =
    props.projectRole?.default_skill_slots ??
    props.systemRole?.default_skill_slots ??
    [];

  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-slate-50">{roleName}</h3>
            <StatusBadge
              label={ROLE_CODE_LABELS[roleCode] ?? roleCode}
              tone="info"
            />
            {props.projectRole ? (
              <StatusBadge
                label={props.projectRole.enabled ? "已启用" : "未启用"}
                tone={props.projectRole.enabled ? "success" : "neutral"}
              />
            ) : null}
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-300">{summary}</p>
        </div>

        <button
          type="button"
          onClick={props.onEdit}
          disabled={!props.projectSelected}
          className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900 disabled:text-slate-500"
        >
          {props.projectSelected ? "编辑角色" : "选择项目后可编辑"}
        </button>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <RoleListCard title="职责边界" items={responsibilities} />
        <RoleListCard title="默认 Skill 占位" items={skillSlots} chips />
        <RoleListCard title="输入边界" items={inputBoundary} />
        <RoleListCard title="输出边界" items={outputBoundary} />
      </div>

      {props.projectRole?.custom_notes ? (
        <section className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-amber-200">
            项目备注
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-200">
            {props.projectRole.custom_notes}
          </p>
        </section>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
        <span>角色代码：{roleCode}</span>
        {props.projectRole ? (
          <span>更新时间：{formatDateTime(props.projectRole.updated_at)}</span>
        ) : (
          <span>系统默认目录项</span>
        )}
      </div>
    </article>
  );
}

function RoleListCard(props: {
  title: string;
  items: string[];
  chips?: boolean;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.title}
      </div>
      {props.items.length > 0 ? (
        props.chips ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {props.items.map((item) => (
              <span
                key={item}
                className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100"
              >
                {item}
              </span>
            ))}
          </div>
        ) : (
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-300">
            {props.items.map((item) => (
              <li key={item} className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2">
                {item}
              </li>
            ))}
          </ul>
        )
      ) : (
        <p className="mt-3 text-sm text-slate-500">暂无配置。</p>
      )}
    </section>
  );
}

function isProjectRoleConfig(
  role: ProjectRoleConfig | SystemRoleCatalogItem,
): role is ProjectRoleConfig {
  return "role_code" in role;
}

function roleNameFallback(role: ProjectRoleConfig | SystemRoleCatalogItem) {
  return "role_code" in role ? role.role_code : role.code;
}
