export function ProjectTimelineLoadingState() {
  return (
    <div className="border border-dashed border-[#3a3a3a] px-4 py-8 text-center text-sm text-slate-400">
      正在汇总项目事件...
    </div>
  );
}

export function ProjectTimelineErrorState(props: { message: string }) {
  return (
    <div className="border-l-2 border-l-rose-400 py-4 pl-4 text-sm text-rose-100">
      项目事件加载失败：{props.message}
    </div>
  );
}
