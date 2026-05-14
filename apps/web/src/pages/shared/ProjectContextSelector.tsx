import { formatDateTime } from "../../lib/format";
import type { BossProjectItem } from "../../features/projects/types";

type ProjectContextSelectorProps = {
  eyebrow: string;
  title: string;
  description: string;
  projects: BossProjectItem[];
  selectedProjectId: string | null;
  requestedProjectId: string;
  hasInvalidRequestedProject: boolean;
  isLoading: boolean;
  errorMessage: string | null;
  onSelectProject: (projectId: string) => void;
};

export function ProjectContextSelector(props: ProjectContextSelectorProps) {
  const selectedProject =
    props.projects.find((project) => project.id === props.selectedProjectId) ?? null;

  return (
    <section className="rounded-2xl border border-[#333333] bg-[#242424] p-6 shadow-sm shadow-black/20">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <div className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
            {props.eyebrow}
          </div>
          <h3 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-100">
            {props.title}
          </h3>
          <p className="mt-2 text-sm leading-6 text-zinc-500">
            {props.description}
          </p>
        </div>

        <label className="min-w-full lg:min-w-[320px]">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
            选择项目
          </div>
          <select
            value={props.selectedProjectId ?? ""}
            onChange={(event) => props.onSelectProject(event.target.value)}
            disabled={props.isLoading || props.projects.length === 0}
            className="mt-2 w-full border border-[#3a3a3a] bg-[#1f1f1f] px-3 py-2 text-sm leading-6 text-zinc-100 outline-none transition focus:border-zinc-500 disabled:cursor-not-allowed disabled:text-zinc-600"
          >
            <option value="">
              {props.isLoading ? "正在加载项目..." : "暂无可选项目"}
            </option>
            {props.projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {props.isLoading ? (
        <p className="mt-4 text-sm leading-6 text-zinc-500">正在加载项目列表...</p>
      ) : null}

      {props.errorMessage ? (
        <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm leading-6 text-rose-100">
          项目列表加载失败：{props.errorMessage}
        </div>
      ) : null}

      {props.hasInvalidRequestedProject ? (
        <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
          URL 中的项目 ID
          <code className="mx-1 rounded bg-black/20 px-1.5 py-0.5">
            {props.requestedProjectId}
          </code>
          不在当前项目列表中，已自动切换到一个可用项目；如需处理其他项目，请在上方重新选择。
        </div>
      ) : null}

      {!props.isLoading && !props.errorMessage && props.projects.length === 0 ? (
        <div className="mt-4 rounded-xl border border-dashed border-[#3a3a3a] p-4 text-sm leading-6 text-zinc-500">
          当前还没有项目。请先到项目中心创建项目，创建后这里会自动出现可选项。
        </div>
      ) : null}

      {selectedProject ? (
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <InfoLine label="当前项目" value={selectedProject.name} />
          <InfoLine label="项目阶段" value={selectedProject.stage} />
          <InfoLine label="最近更新" value={formatDateTime(selectedProject.updated_at)} />
        </div>
      ) : null}
    </section>
  );
}

function InfoLine(props: { label: string; value: string }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.2em] text-zinc-600">
        {props.label}
      </div>
      <div className="mt-2 break-all text-sm leading-6 text-zinc-100">
        {props.value}
      </div>
    </div>
  );
}
