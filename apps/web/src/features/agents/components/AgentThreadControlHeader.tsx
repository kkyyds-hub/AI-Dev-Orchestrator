export function AgentThreadControlHeader(props: {
  projectLabel: string;
  sessionCount: number;
  timelineCount: number;
  interventionCount: number;
  onRefresh: () => void;
}) {
  return (
    <header className="border-b border-[#333333] pb-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium tracking-[0.18em] text-slate-500">
            协作
          </p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-50">
            协作线程
          </h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
            当前项目：
            <span className="text-slate-200">{props.projectLabel}</span>
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">
          <span className="text-xs text-slate-500">会话 {props.sessionCount}</span>
          <span className="text-xs text-slate-500">时间线 {props.timelineCount}</span>
          <span className="text-xs text-slate-500">介入 {props.interventionCount}</span>
          <button
            type="button"
            data-testid="agent-thread-refresh-btn"
            onClick={props.onRefresh}
            className="inline-flex items-center rounded border border-[#4a4a4a] bg-transparent px-3 py-1.5 text-xs font-medium text-zinc-100 transition hover:bg-[#292929] focus:outline-none focus:ring-2 focus:ring-slate-500/30"
          >
            刷新
          </button>
        </div>
      </div>
    </header>
  );
}
