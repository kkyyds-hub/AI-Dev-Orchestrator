export function TaskDetailLoadingState(props: { title: string }) {
  return (
    <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm text-slate-300">
      正在加载 <span className="font-medium text-slate-100">{props.title}</span> 的详情数据。
    </div>
  );
}
