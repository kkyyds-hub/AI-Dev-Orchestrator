import { ProjectMemoryMiniStat } from "./ProjectMemoryShared";

export function ProjectMemoryHeader(props: {
  projectName: string | null;
  totalMemories: number;
  onRefresh: () => void;
}) {
  return (
    <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
          V3 Day14 Project Memory
        </p>
        <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
          项目记忆与可检索经验沉淀
        </h2>
        <p className="max-w-3xl text-sm leading-6 text-slate-300">
          把运行结论、失败复盘、审批意见与交付件摘要沉淀成结构化项目记忆，供后续检索、复盘和上下文构建继续消费。
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
          className="rounded-2xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
        >
          刷新沉淀
        </button>
      </div>
    </header>
  );
}
