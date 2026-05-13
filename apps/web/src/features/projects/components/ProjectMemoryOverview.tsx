import { formatDateTime } from "../../../lib/format";
import type { ProjectMemoryCount } from "../types";
import { PROJECT_MEMORY_KIND_LABELS } from "../types";

export function ProjectMemoryOverview(props: {
  generatedAt: string | null;
  counts: ProjectMemoryCount[];
}) {
  return (
    <section className="border-b border-[#333333] pb-5">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h3 className="text-base font-semibold text-zinc-50">记忆概览</h3>
          <p className="mt-1 text-sm text-zinc-500">
            按类型查看当前项目已沉淀的记忆规模。
          </p>
        </div>
        <div className="text-xs text-zinc-500">
          更新时间：{props.generatedAt ? formatDateTime(props.generatedAt) : "未记录"}
        </div>
      </div>

      {props.counts.length > 0 ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {props.counts.map((count) => (
            <ProjectMemoryCountCard key={count.memory_type} item={count} />
          ))}
        </div>
      ) : (
        <div className="mt-4 border-y border-dashed border-[#333333] py-4 text-sm text-zinc-500">
          暂无可统计的记忆类型。
        </div>
      )}
    </section>
  );
}

function ProjectMemoryCountCard(props: { item: ProjectMemoryCount }) {
  return (
    <div className="min-w-0 border-l border-[#333333] px-4 py-2">
      <div className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
        {PROJECT_MEMORY_KIND_LABELS[props.item.memory_type]}
      </div>
      <div className="mt-2 font-mono text-2xl font-semibold tracking-tight text-zinc-100">
        {props.item.count}
      </div>
    </div>
  );
}
