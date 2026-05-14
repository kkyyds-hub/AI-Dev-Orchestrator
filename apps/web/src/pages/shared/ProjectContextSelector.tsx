import { Link } from "react-router-dom";

import { formatDateTime } from "../../lib/format";
import {
  PROJECT_STAGE_LABELS,
  type BossProjectItem,
} from "../../features/projects/types";

type ProjectContextSelectorProps = {
  eyebrow: string;
  title: string;
  description: string;
  projects: BossProjectItem[];
  selectedProjectId: string | null;
  hasInvalidRequestedProject: boolean;
  isLoading: boolean;
  errorMessage: string | null;
  onSelectProject: (projectId: string) => void;
};

export function ProjectContextSelector(props: ProjectContextSelectorProps) {
  const selectedProject =
    props.projects.find((project) => project.id === props.selectedProjectId) ?? null;

  return (
    <section className="border-y border-[#333333] py-5">
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
            项目上下文
          </div>
          <select
            value={props.selectedProjectId ?? ""}
            onChange={(event) => props.onSelectProject(event.target.value)}
            disabled={props.isLoading || props.projects.length === 0}
            className="mt-2 w-full border-x-0 border-b border-t-0 border-[#3a3a3a] bg-transparent px-0 py-2 text-sm leading-6 text-zinc-100 outline-none transition focus:border-zinc-500 disabled:cursor-not-allowed disabled:text-zinc-600"
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
        <div className="mt-4 border-l border-rose-500/50 px-4 py-3 text-sm leading-6 text-rose-100">
          项目列表加载失败：{props.errorMessage}
        </div>
      ) : null}

      {props.hasInvalidRequestedProject ? (
        <div className="mt-4 border-l border-amber-500/50 px-4 py-3 text-sm leading-6 text-amber-100">
          当前打开的项目不可用，已自动切换到一个可处理项目；如需处理其他项目，请在上方重新选择。
        </div>
      ) : null}

      {!props.isLoading && !props.errorMessage && props.projects.length === 0 ? (
        <div className="mt-4 border-l border-dashed border-[#3a3a3a] px-4 py-3 text-sm leading-6 text-zinc-500">
          当前还没有项目。请先到项目中心创建项目，创建后这里会自动出现可选项。
          <div className="mt-3">
            <Link
              to="/projects"
              className="inline-flex border-b border-zinc-500 pb-0.5 text-sm font-medium text-zinc-100 transition hover:border-zinc-200 hover:text-white"
            >
              去项目中心创建项目
            </Link>
          </div>
        </div>
      ) : null}

      {selectedProject ? (
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <InfoLine label="当前项目" value={selectedProject.name} />
          <InfoLine
            label="项目阶段"
            value={PROJECT_STAGE_LABELS[selectedProject.stage] ?? "未识别阶段"}
          />
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
