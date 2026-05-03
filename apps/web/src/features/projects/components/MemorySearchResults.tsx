import { StatusBadge } from "../../../components/StatusBadge";
import type { ProjectMemorySearchHit } from "../types";
import { MemorySearchResultCard } from "./MemorySearchResultCard";

export function MemorySearchResults(props: {
  projectId: string;
  submittedQuery: string;
  totalMatches: number;
  hits: ProjectMemorySearchHit[];
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
  onNavigateToApproval?: (input: {
    projectId: string;
    approvalId: string;
  }) => void;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-50">搜索结果</h3>
          <p className="mt-1 text-sm text-slate-400">
            查询 “{props.submittedQuery}” ，共命中 {props.totalMatches} 条项目记忆。
          </p>
        </div>
        <StatusBadge label={`${props.hits.length} 条展示`} tone="neutral" />
      </div>

      {props.hits.length > 0 ? (
        <div className="mt-4 space-y-3">
          {props.hits.map((hit) => (
            <MemorySearchResultCard
              key={`${hit.item.memory_id}-${hit.score}`}
              hit={hit}
              projectId={props.projectId}
              onNavigateToTask={props.onNavigateToTask}
              onNavigateToDeliverable={props.onNavigateToDeliverable}
              onNavigateToApproval={props.onNavigateToApproval}
            />
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-sm leading-6 text-slate-400">
          当前查询没有命中项目记忆。可以换一个更接近交付件、审批意见、失败模式或运行结论的关键词。
        </div>
      )}
    </section>
  );
}
