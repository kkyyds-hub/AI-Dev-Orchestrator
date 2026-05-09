export function TeamControlCenterLoadingState() {
  return (
    <div className="border-y border-dashed border-[#333333] px-1 py-5 text-sm text-slate-400">
      正在加载团队控制中心快照...
    </div>
  );
}

export function TeamControlCenterErrorState(props: { message: string }) {
  return (
    <div className="border-y border-rose-500/30 px-1 py-5 text-sm text-rose-100">
      团队控制中心加载失败：{props.message}
    </div>
  );
}

export function TeamControlCenterFeedback(props: { text: string }) {
  return (
    <div
      data-testid="team-control-center-feedback"
      className="border-l border-emerald-500/50 pl-3 text-sm text-emerald-100"
    >
      {props.text}
    </div>
  );
}
