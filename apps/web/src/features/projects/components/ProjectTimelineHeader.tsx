export function ProjectTimelineHeader(props: {
  projectName: string | null;
  totalEvents: number;
  visibleEventCount: number;
}) {
  return (
    <header className="border-b border-[#333333] pb-5">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(360px,460px)] xl:items-end">
        <div className="min-w-0">
          <p className="text-xs font-medium tracking-[0.24em] text-zinc-500">
            时间线
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-100">
            项目事件流
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">
            按时间聚合阶段、交付、审批与运行决策；左侧浏览事件，右侧查看上下文与跳转入口。
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
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
    <div className="min-w-0 border border-[#333333] px-3 py-3">
      <div className="text-xs tracking-[0.16em] text-zinc-500">
        {props.label}
      </div>
      <div className="mt-1 truncate text-sm font-medium text-zinc-100" title={props.value}>
        {props.value}
      </div>
    </div>
  );
}
