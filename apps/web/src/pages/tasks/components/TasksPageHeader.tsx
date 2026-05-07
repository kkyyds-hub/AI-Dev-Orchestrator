import { TasksSummaryCard } from "./TasksSummaryCard";

type TasksPageHeaderProps = {
  tasksCount: number;
  selectedTaskLabel: string;
  realtimeStatus: string;
};

export function TasksPageHeader(props: TasksPageHeaderProps) {
  return (
    <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-[0.24em] text-cyan-300">
            Tasks
          </div>
          <h3 className="mt-2 text-xl font-semibold text-slate-50">任务中心</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            在正式任务域中查看任务列表、任务详情、上下文摘要、运行记录与交付物关联。
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <TasksSummaryCard label="任务总数" value={String(props.tasksCount)} />
          <TasksSummaryCard label="当前选中" value={props.selectedTaskLabel} />
          <TasksSummaryCard label="连接状态" value={props.realtimeStatus} />
        </div>
      </div>
    </section>
  );
}
