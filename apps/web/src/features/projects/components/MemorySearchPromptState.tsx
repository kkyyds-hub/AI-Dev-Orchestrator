export function MemorySearchPromptState(props: { projectName: string | null }) {
  return (
    <div className="space-y-2 py-4 text-sm leading-6 text-zinc-500">
      <h3 className="text-base font-semibold text-zinc-100">输入关键词开始检索</h3>
      <p>
        当前项目为 <span className="text-zinc-200">{props.projectName ?? "未命名项目"}</span>。
        使用上方控制条输入关键词后，这里会展示最相关的项目记忆。
      </p>
    </div>
  );
}
