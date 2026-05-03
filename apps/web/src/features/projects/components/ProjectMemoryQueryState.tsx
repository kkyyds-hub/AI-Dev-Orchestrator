export function ProjectMemoryLoadingState() {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/40 px-4 py-8 text-center text-sm text-slate-400">
      正在汇总项目记忆…
    </div>
  );
}

export function ProjectMemoryErrorState(props: { message: string }) {
  return (
    <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-8 text-center text-sm text-rose-100">
      项目记忆加载失败：{props.message}
    </div>
  );
}
