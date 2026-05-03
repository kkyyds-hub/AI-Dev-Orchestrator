export function ProjectRetrospectiveLoadingState() {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/40 px-4 py-8 text-center text-sm text-slate-400">
      正在汇总项目复盘结论...
    </div>
  );
}

export function ProjectRetrospectiveErrorState(props: { message: string }) {
  return (
    <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-8 text-center text-sm text-rose-100">
      项目复盘加载失败：{props.message}
    </div>
  );
}
