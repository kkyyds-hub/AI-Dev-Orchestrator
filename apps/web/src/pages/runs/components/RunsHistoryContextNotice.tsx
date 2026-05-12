export function RunsHistoryContextNotice() {
  return (
    <section className="border-l border-[#666666] bg-transparent py-2 pl-4 text-sm leading-6 text-zinc-300">
      当前运行来自任务历史记录，不一定出现在“最新运行列表”中；右侧详情仍会按 taskId +
      runId 承接该运行。
    </section>
  );
}
