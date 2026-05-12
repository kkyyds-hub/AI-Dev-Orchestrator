import { ProjectMemoryMiniStat } from "./ProjectMemoryShared";

export function ProjectMemoryHeader(props: {
  projectName: string | null;
  totalMemories: number;
  onRefresh: () => void;
}) {
  return (
    <header className="flex flex-col gap-4 border-b border-[#333333] pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
          项目记忆
        </p>
        <h2 className="text-3xl font-semibold tracking-tight text-zinc-50">
          项目记忆沉淀
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
          把运行结论、失败复盘、审批意见与交付件摘要沉淀成结构化项目记忆；列表默认先看摘要，长详情可按需展开。
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <ProjectMemoryMiniStat
          label="当前项目"
          value={props.projectName ?? "未选择"}
        />
        <ProjectMemoryMiniStat
          label="记忆总数"
          value={String(props.totalMemories)}
        />
        <button
          type="button"
          onClick={props.onRefresh}
          className="rounded border border-[#3a3a3a] bg-transparent px-4 py-3 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
        >
          刷新沉淀
        </button>
      </div>
    </header>
  );
}
