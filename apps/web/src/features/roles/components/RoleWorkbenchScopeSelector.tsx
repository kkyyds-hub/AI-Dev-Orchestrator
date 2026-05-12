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
    <section className="border-b border-[#333333] pb-5">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">项目范围</div>
          <p className="mt-2 text-sm leading-6 text-zinc-400">
            选择项目后，工作台会聚焦展示该项目下的角色协作情况。
          </p>
        </div>
        <div className="text-xs text-zinc-500">
          {props.selectedProjectName ? "项目视角" : "全局视角"}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {props.projectOptions.map((project) => {
          const selected = project.id === props.selectedProjectId;
          return (
            <button
              key={project.id}
              type="button"
              onClick={() => props.onNavigateToProject?.(project.id)}
              className={`border-l px-4 py-3 text-left transition ${
                selected
                  ? "border-zinc-300 bg-white/[0.035] text-zinc-50"
                  : "border-[#333333] text-zinc-300 hover:border-zinc-500 hover:text-zinc-50"
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