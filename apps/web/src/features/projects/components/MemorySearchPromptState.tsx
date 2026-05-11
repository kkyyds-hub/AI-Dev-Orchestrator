export function MemorySearchPromptState(props: { projectName: string | null }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-sm leading-6 text-slate-400">
      当前项目为 <span className="text-slate-200">{props.projectName ?? "未命名项目"}</span>。
      输入关键词后，将在本项目沉淀的记忆中检索相关内容。
    </div>
  );
}
