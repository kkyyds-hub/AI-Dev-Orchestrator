export function RunsHistoryContextNotice() {
  return (
    <section className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-4 text-sm leading-6 text-cyan-100">
      当前运行来自任务历史记录，不一定出现在“最新运行列表”中；右侧详情仍会按 taskId +
      runId 承接该运行。
    </section>
  );
}
