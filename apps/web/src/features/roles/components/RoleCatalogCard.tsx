import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { ProjectRoleConfig, SystemRoleCatalogItem } from "../types";
import { ROLE_CODE_LABELS } from "../types";
import { RoleCatalogListCard } from "./RoleCatalogListCard";

type RoleCatalogCardProps = {
  projectRole: ProjectRoleConfig | null;
  systemRole: SystemRoleCatalogItem | null;
  projectSelected: boolean;
  onEdit: () => void;
};

export function RoleCatalogCard(props: RoleCatalogCardProps) {
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
    <article className="py-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-zinc-50">{roleName}</h3>
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
          <p className="mt-3 max-w-4xl text-sm leading-6 text-zinc-400">{summary}</p>
        </div>

        <button
          type="button"
          onClick={props.onEdit}
          disabled={!props.projectSelected}
          className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm font-medium text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50 disabled:cursor-not-allowed disabled:border-[#2a2a2a] disabled:text-zinc-600"
        >
          {props.projectSelected ? "编辑角色" : "选择项目后可编辑"}
        </button>
      </div>

      <div className="mt-5 grid gap-x-6 gap-y-5 border-t border-[#333333] pt-5 lg:grid-cols-2">
        <RoleCatalogListCard title="职责边界" items={responsibilities} />
        <RoleCatalogListCard title="默认 Skill 占位" items={skillSlots} chips />
        <RoleCatalogListCard title="输入边界" items={inputBoundary} />
        <RoleCatalogListCard title="输出边界" items={outputBoundary} />
      </div>

      {props.projectRole?.custom_notes ? (
        <section className="mt-5 border-l border-amber-700/60 pl-4">
          <div className="text-xs font-medium uppercase tracking-[0.16em] text-amber-300">
            项目备注
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-300">
            {props.projectRole.custom_notes}
          </p>
        </section>
      ) : null}

      <div className="mt-5 flex flex-wrap gap-4 text-xs text-zinc-600">
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
