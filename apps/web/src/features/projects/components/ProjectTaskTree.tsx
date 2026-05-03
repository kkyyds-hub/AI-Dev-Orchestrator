import type { ProjectDetailTaskItem } from "../types";
import { ProjectTaskTreeRow } from "./ProjectTaskTreeRow";

export function ProjectTaskTree(props: {
  tasks: ProjectDetailTaskItem[];
  isLoading: boolean;
  errorMessage: string | null;
}) {
  return (
    <section
      data-testid="project-detail-task-tree"
      className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
          任务树与草案来源
        </div>
        <span className="text-xs text-slate-500">
          {props.tasks.length} 个任务
        </span>
      </div>

      {props.isLoading ? (
        <p className="mt-3 text-sm leading-6 text-slate-400">
          正在加载项目任务树...
        </p>
      ) : props.errorMessage ? (
        <p className="mt-3 text-sm leading-6 text-rose-200">
          项目详情加载失败：{props.errorMessage}
        </p>
      ) : props.tasks.length > 0 ? (
        <div className="mt-4 space-y-3">
          {props.tasks.map((task) => (
            <ProjectTaskTreeRow key={task.id} task={task} />
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-slate-400">
          当前还没有项目级任务树；可以先通过上方规划入口生成草案并应用到项目。
        </p>
      )}
    </section>
  );
}
