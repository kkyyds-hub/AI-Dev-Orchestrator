export function MemorySearchPromptState(props: { projectName: string | null }) {
  return (
    <div className="border-y border-dashed border-[#333333] py-5 text-sm leading-6 text-zinc-500">
      当前项目为 <span className="text-zinc-200">{props.projectName ?? "未命名项目"}</span>。
      输入关键词后，将在本项目沉淀的记忆中检索相关内容。
    </div>
  );
}
