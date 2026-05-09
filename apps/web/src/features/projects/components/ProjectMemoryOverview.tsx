import { formatDateTime } from "../../../lib/format";
import type { ProjectMemoryCount } from "../types";
import { PROJECT_MEMORY_KIND_LABELS } from "../types";

export function ProjectMemoryOverview(props: {
  generatedAt: string | null;
  counts: ProjectMemoryCount[];
}) {
  return (
    <section className="border-b border-[#333333] pb-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-50">记忆概览</h3>
          <p className="mt-1 text-sm text-slate-400">
            结构化统计当前项目已沉淀的四类经验。
          </p>
        </div>
        <div className="text-sm text-slate-400">
          生成时间：
          {props.generatedAt ? formatDateTime(props.generatedAt) : "—"}
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {props.counts.map((count) => (
          <ProjectMemoryCountCard key={count.memory_type} item={count} />
        ))}
      </div>
    </section>
  );
}

function ProjectMemoryCountCard(props: { item: ProjectMemoryCount }) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
        {PROJECT_MEMORY_KIND_LABELS[props.item.memory_type]}
      </div>
      <div className="mt-2 text-2xl font-semibold text-slate-50">{props.item.count}</div>
    </div>
  );
}
