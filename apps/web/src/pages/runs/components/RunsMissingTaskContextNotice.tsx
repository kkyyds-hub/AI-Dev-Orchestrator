export function RunsMissingTaskContextNotice() {
  return (
    <section className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
      当前运行 URL 缺少稳定的任务上下文。建议使用包含
      <code className="mx-1 rounded bg-slate-950/40 px-1.5 py-0.5">taskId</code>
      的地址访问该运行，以便稳定承接运行详情与日志视图。
    </section>
  );
}
