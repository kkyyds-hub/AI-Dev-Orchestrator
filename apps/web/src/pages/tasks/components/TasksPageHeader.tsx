type TasksPageHeaderProps = {
  total: number;
  waitingHuman: number;
  running: number;
  failed: number;
  completed: number;
  realtimeStatus: string;
};

export function TasksPageHeader(props: TasksPageHeaderProps) {
  const realtimeLabel =
    props.realtimeStatus === "open" ? "实时已连接" : "实时未连接";

  return (
    <header className="border-b border-[#333333] pb-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
            任务队列
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            待处理 {props.waitingHuman + props.running + props.failed} / 执行中{" "}
            {props.running} / 失败 {props.failed} / 已完成 {props.completed}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span className="inline-flex items-center gap-1 rounded-full border border-zinc-600 px-2.5 py-0.5 text-xs text-zinc-400">
            {realtimeLabel}
          </span>
        </div>
      </div>
    </header>
  );
}
