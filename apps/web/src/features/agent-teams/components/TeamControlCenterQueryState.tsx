export function TeamControlCenterLoadingState() {
  return (
    <div className="border-y border-dashed border-[#333333] py-5 text-sm text-zinc-400">
      正在加载团队设置...
    </div>
  );
}

export function TeamControlCenterErrorState(props: { message: string }) {
  return (
    <div className="border-y border-rose-500/30 py-5 text-sm text-rose-100">
      团队设置加载失败：{props.message}
    </div>
  );
}

export function TeamControlCenterFeedback(props: { text: string }) {
  return (
    <div
      data-testid="team-control-center-feedback"
      className="border-l border-emerald-500/50 py-1 pl-3 text-sm text-emerald-100"
    >
      {props.text}
    </div>
  );
}
