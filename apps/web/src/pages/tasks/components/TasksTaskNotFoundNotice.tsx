type TasksTaskNotFoundNoticeProps = {
  taskId: string;
};

export function TasksTaskNotFoundNotice(props: TasksTaskNotFoundNoticeProps) {
  return (
    <section className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
      当前 URL 中的任务 ID
      <code className="mx-1 rounded bg-slate-950/40 px-1.5 py-0.5">{props.taskId}</code>
      未出现在当前任务列表中。你仍然可以在左侧列表中重新选择一个任务。
    </section>
  );
}
