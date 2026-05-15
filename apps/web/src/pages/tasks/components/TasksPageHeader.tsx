import { TasksSummaryCard } from "./TasksSummaryCard";

type TasksPageHeaderProps = {
  tasksCount: number;
  selectedTaskLabel: string;
  realtimeStatus: string;
};

function formatRealtimeStatus(status: string): string {
  const labels: Record<string, string> = {
    open: "已连接",
    connecting: "连接中",
    reconnecting: "正在重连",
    unsupported: "不支持实时连接",
  };
  return labels[status] ?? "未知状态";
}

export function TasksPageHeader(props: TasksPageHeaderProps) {
  return (
    <section className="border-b border-[#333333] pb-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
            任务中心
          </div>
          <h3 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-100">任务中心</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-500">
            统一查看任务列表、任务详情、运行记录与交付物关联。
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <TasksSummaryCard label="任务总数" value={String(props.tasksCount)} />
          <TasksSummaryCard label="当前选中" value={props.selectedTaskLabel} />
          <TasksSummaryCard label="连接状态" value={formatRealtimeStatus(props.realtimeStatus)} />
        </div>
      </div>
    </section>
  );
}
