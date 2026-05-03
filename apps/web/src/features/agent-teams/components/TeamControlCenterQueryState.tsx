export function TeamControlCenterLoadingState() {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-6 text-sm text-slate-400">
      正在加载团队控制中心快照...
    </div>
  );
}

export function TeamControlCenterErrorState(props: { message: string }) {
  return (
    <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-6 text-sm text-rose-100">
      团队控制中心加载失败：{props.message}
    </div>
  );
}

export function TeamControlCenterFeedback(props: { text: string }) {
  return (
    <div
      data-testid="team-control-center-feedback"
      className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100"
    >
      {props.text}
    </div>
  );
}
