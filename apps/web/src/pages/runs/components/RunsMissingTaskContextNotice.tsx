export function RunsMissingTaskContextNotice() {
  return (
    <section className="border-l border-amber-700/70 bg-transparent py-2 pl-4 text-sm leading-6 text-amber-200">
      当前运行 URL 缺少稳定的任务上下文。建议使用包含
      <code className="mx-1 rounded bg-[#1f1f1f] px-1.5 py-0.5 text-amber-100">taskId</code>
      的地址访问该运行，以便稳定承接运行详情与日志视图。
    </section>
  );
}
