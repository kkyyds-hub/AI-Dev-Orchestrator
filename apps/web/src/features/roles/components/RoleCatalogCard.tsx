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
  const summary = props.projectRole?.summary ?? props.systemRole?.summary ?? "?";
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
        <RoleCatalogListCard title="职责边界" items={responsibilities} />
        <RoleCatalogListCard title="默认 Skill 占位" items={skillSlots} chips />
        <RoleCatalogListCard title="输入边界" items={inputBoundary} />
        <RoleCatalogListCard title="输出边界" items={outputBoundary} />
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
