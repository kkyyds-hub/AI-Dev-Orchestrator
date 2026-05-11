export function TeamControlCenterLoadingState() {
  return (
    <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/30 px-4 py-5 text-sm text-slate-400">
      正在加载团队设置...
    </div>
  );
}

export function TeamControlCenterErrorState(props: { message: string }) {
  return (
    <div className="rounded-xl border border-rose-500/30 bg-rose-950/20 px-4 py-5 text-sm text-rose-100">
      团队设置加载失败：{props.message}
    </div>
  );
}

export function TeamControlCenterFeedback(props: { text: string }) {
  return (
    <div
      data-testid="team-control-center-feedback"
      className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 px-4 py-3 text-sm text-emerald-100"
    >
      {props.text}
    </div>
  );
}
