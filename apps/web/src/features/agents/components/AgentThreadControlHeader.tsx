import { StatusBadge } from "../../../components/StatusBadge";

export function AgentThreadControlHeader(props: {
  projectLabel: string;
  sessionCount: number;
  timelineCount: number;
  interventionCount: number;
  onRefresh: () => void;
}) {
  return (
    <header className="relative overflow-hidden rounded-3xl border border-slate-700/70 bg-slate-900/75 p-4 shadow-lg shadow-slate-950/20 sm:p-5">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/60 to-transparent" />
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold tracking-[0.22em] text-cyan-200">
            协作线程控制台
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-50 sm:text-3xl">
            会话、时间线与人工介入
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
            当前项目：
            <span className="font-medium text-slate-100">{props.projectLabel}</span>
            。集中查看智能体会话、消息流和人工介入结果。
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">
          <StatusBadge label={`会话 ${props.sessionCount}`} tone="info" />
          <StatusBadge label={`时间线 ${props.timelineCount}`} tone="success" />
          <StatusBadge label={`介入 ${props.interventionCount}`} tone="warning" />
          <button
            type="button"
            data-testid="agent-thread-refresh-btn"
            onClick={props.onRefresh}
            className="inline-flex items-center rounded-full border border-cyan-300/35 bg-cyan-400/10 px-3.5 py-1.5 text-xs font-semibold text-cyan-50 transition hover:border-cyan-200/60 hover:bg-cyan-400/20 focus:outline-none focus:ring-2 focus:ring-cyan-300/40"
          >
            刷新数据
          </button>
        </div>
      </div>
    </header>
  );
}