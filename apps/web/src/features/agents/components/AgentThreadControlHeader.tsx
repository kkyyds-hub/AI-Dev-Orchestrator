import { StatusBadge } from "../../../components/StatusBadge";

export function AgentThreadControlHeader(props: {
  projectLabel: string;
  sessionCount: number;
  timelineCount: number;
  interventionCount: number;
  onRefresh: () => void;
}) {
  return (
    <header className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-cyan-300">Day12 Agent Thread</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-50">
            消息时间线与老板介入入口
          </h2>
          <p className="mt-2 text-sm text-slate-300">项目：{props.projectLabel}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label={`会话 ${props.sessionCount}`} tone="info" />
          <StatusBadge label={`时间线 ${props.timelineCount}`} tone="success" />
          <StatusBadge label={`介入 ${props.interventionCount}`} tone="warning" />
          <button
            type="button"
            data-testid="agent-thread-refresh-btn"
            onClick={props.onRefresh}
            className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-100 transition hover:bg-cyan-500/20"
          >
            刷新
          </button>
        </div>
      </div>
    </header>
  );
}
