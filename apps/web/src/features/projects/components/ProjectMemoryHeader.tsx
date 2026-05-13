import { ProjectMemoryMiniStat } from "./ProjectMemoryShared";

export function ProjectMemoryHeader(props: {
  projectName: string | null;
  totalMemories: number;
  onRefresh: () => void;
}) {
  return (
    <header className="border-b border-[#333333] pb-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-500">
            项目记忆
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-50">
            记忆概览
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-400">
            在当前父页面内查看项目沉淀的结论、复盘、审批意见与交付摘要；默认先看概览与最近沉淀，必要时再展开详情。
          </p>
        </div>

        <div className="flex flex-wrap items-start gap-3">
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
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
          >
            刷新
          </button>
        </div>
      </div>
    </header>
  );
}
