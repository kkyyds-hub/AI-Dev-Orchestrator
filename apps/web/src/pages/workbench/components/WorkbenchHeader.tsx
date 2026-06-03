import { StatusBadge } from "../../../components/StatusBadge";
import type { BossProjectItem } from "../../../features/projects/types";

type WorkbenchHeaderProps = {
  backendStatus: string | null | undefined;
  realtimeStatus: string;
  lastUpdatedText: string;
  selectedProjectName: string;
  selectedProjectId: string;
  mode: "new-project" | "project";
  projects: BossProjectItem[];
  projectsLoading: boolean;
  projectNotFound: boolean;
  onSelectContext: (value: string) => void;
};

function mapRealtimeTone(status: string) {
  switch (status) {
    case "open":
      return "success" as const;
    case "reconnecting":
      return "warning" as const;
    case "unsupported":
      return "danger" as const;
    default:
      return "info" as const;
  }
}

function mapRealtimeLabel(status: string) {
  switch (status) {
    case "open":
      return "实时已连接";
    case "reconnecting":
      return "实时重连中";
    case "unsupported":
      return "实时连接不可用";
    default:
      return "实时连接中";
  }
}

export function WorkbenchHeader({
  backendStatus,
  realtimeStatus,
  lastUpdatedText,
  selectedProjectName,
  selectedProjectId,
  mode,
  projects,
  projectsLoading,
  projectNotFound,
  onSelectContext,
}: WorkbenchHeaderProps) {
  const selectorValue =
    mode === "new-project" ? "new-project" : selectedProjectId === "all" ? "all" : selectedProjectId;

  return (
    <header
      data-testid="workbench-header"
      className="border-b border-[#333333] pb-5"
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
            AI 项目主管工作台
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            {mode === "new-project"
              ? "新项目会话：从目标澄清进入首次创建链路"
              : selectedProjectId === "all"
              ? "全部项目总览"
              : `当前项目：${selectedProjectName}`}
          </p>
          {projectNotFound ? (
            <p className="mt-2 text-xs text-amber-300">
              当前 URL / 本地记录中的项目不可用，请在右侧重新选择项目上下文。
            </p>
          ) : null}
        </div>

        <div className="flex w-full flex-col gap-3 lg:w-[420px] lg:items-end">
          <label className="w-full" data-testid="workbench-project-context-selector">
            <div className="mb-1 text-xs uppercase tracking-[0.2em] text-zinc-600">
              项目上下文
            </div>
            <select
              value={selectorValue}
              onChange={(event) => onSelectContext(event.target.value)}
              disabled={projectsLoading}
              className="w-full rounded border border-[#333333] bg-[#111111] px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-zinc-500 disabled:cursor-not-allowed disabled:text-zinc-600"
            >
              <option value="new-project">新项目会话（首次创建）</option>
              <option value="all">全部已有项目</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>

          <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400 lg:justify-end">
            <StatusBadge
              label={backendStatus === "ok" ? "后端在线" : "后端未知"}
              tone={backendStatus === "ok" ? "success" : "warning"}
            />
            <StatusBadge
              label={mapRealtimeLabel(realtimeStatus)}
              tone={mapRealtimeTone(realtimeStatus)}
            />
            <span className="text-zinc-600">更新 {lastUpdatedText}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
