export function AgentThreadSessionsLoadingState() {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-6 text-sm text-slate-400">
      正在加载 Day11 会话契约...
    </div>
  );
}

export function AgentThreadSessionsErrorState(props: { message: string }) {
  return (
    <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-6 text-sm text-rose-100">
      会话加载失败：{props.message}
    </div>
  );
}

export function AgentThreadTimelineErrorState(props: { message: string }) {
  return (
    <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-6 text-sm text-rose-100">
      时间线加载失败：{props.message}
    </div>
  );
}

export function AgentThreadInterventionsErrorState(props: { message: string }) {
  return (
    <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-6 text-sm text-rose-100">
      介入记录加载失败：{props.message}
    </div>
  );
}
