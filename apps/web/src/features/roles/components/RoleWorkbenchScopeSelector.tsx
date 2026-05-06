import { StatusBadge } from "../../../components/StatusBadge";
import { PROJECT_STAGE_LABELS, PROJECT_STATUS_LABELS } from "../../projects/types";

export type RoleWorkbenchProjectOption = {
  id: string;
  name: string;
  stage: string;
  status: string;
};

type RoleWorkbenchScopeSelectorProps = {
  selectedProjectId: string | null;
  selectedProjectName: string | null;
  projectOptions: RoleWorkbenchProjectOption[];
  onNavigateToProject?: (projectId: string) => void;
};

export function RoleWorkbenchScopeSelector(props: RoleWorkbenchScopeSelectorProps) {
  if (!props.projectOptions.length) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">工作台范围</div>
          <p className="mt-2 text-sm text-slate-300">
            切换项目后，角色工作台、项目详情和任务跳转会同步聚焦到同一条项目链路。
          </p>
        </div>
        <StatusBadge
          label={props.selectedProjectName ? "项目视角" : "全局视角"}
          tone={props.selectedProjectName ? "success" : "neutral"}
        />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {props.projectOptions.map((project) => {
          const selected = project.id === props.selectedProjectId;
          return (
            <button
              key={project.id}
              type="button"
              onClick={() => props.onNavigateToProject?.(project.id)}
              className={`rounded-xl border px-4 py-3 text-left transition ${
                selected
                  ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-50"
                  : "border-slate-800 bg-slate-900/70 text-slate-300 hover:border-slate-700 hover:bg-slate-900"
              }`}
            >
              <div className="text-sm font-medium">{project.name}</div>
              <div className="mt-2 flex flex-wrap gap-2">
                <StatusBadge
                  label={PROJECT_STAGE_LABELS[project.stage] ?? project.stage}
                  tone="info"
                />
                <StatusBadge
                  label={PROJECT_STATUS_LABELS[project.status] ?? project.status}
                  tone="neutral"
                />
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
