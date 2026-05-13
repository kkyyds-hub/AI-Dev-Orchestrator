export function MemorySearchPromptState(props: { projectName: string | null }) {
  const examples = ["审批意见", "失败模式", "交付摘要"];

  return (
    <div className="space-y-3 py-4 text-sm leading-6 text-zinc-500">
      <div>
        <h3 className="text-base font-semibold text-zinc-100">输入关键词开始检索</h3>
        <p className="mt-1">
          当前项目为 <span className="text-zinc-200">{props.projectName ?? "未命名项目"}</span>。
          使用上方控制条输入关键词后，这里会展示最相关的项目记忆。
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {examples.map((example) => (
          <span key={example} className="rounded-full border border-[#333333] px-2.5 py-1 text-xs text-zinc-400">
            {example}
          </span>
        ))}
      </div>
    </div>
  );
}
