export function ProjectTimelineHeader(props: {
  projectName: string | null;
  totalEvents: number;
  visibleEventCount: number;
}) {
  return (
    <header className="border-b border-[#333333] pb-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-500">
            时间线
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-50">
            项目事件流
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            按时间聚合阶段、交付、审批与运行决策；左侧浏览事件，右侧查看上下文与跳转入口。
          </p>
        </div>

        <div className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-3 lg:text-right">
          <TimelineMetric label="当前项目" value={props.projectName ?? "未选择"} />
          <TimelineMetric label="事件总数" value={String(props.totalEvents)} />
          <TimelineMetric label="当前可见" value={String(props.visibleEventCount)} />
        </div>
      </div>
    </header>
  );
}

function TimelineMetric(props: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-1 truncate text-sm font-medium text-slate-100">
        {props.value}
      </div>
    </div>
  );
}
