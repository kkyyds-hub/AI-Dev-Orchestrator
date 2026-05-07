export function TaskDetailErrorState(props: { message: string }) {
  return (
    <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
      无法加载任务详情：{props.message}
    </div>
  );
}
