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
  const hasHits = props.hits.length > 0;

  return (
    <section className="space-y-4" aria-label="检索结果">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-zinc-50">结果区</h3>
          <p className="mt-1 text-sm text-zinc-500">
            “{props.submittedQuery}” 共命中 {props.totalMatches} 条，当前展示 {props.hits.length} 条。
          </p>
        </div>
        <StatusBadge label={hasHits ? "已收敛结果" : "暂无结果"} tone={hasHits ? "info" : "neutral"} />
      </div>

      {hasHits ? (
        <div className="space-y-3">
          {props.hits.map((hit) => (
            <MemorySearchResultCard
              key={hit.item.memory_id + "-" + String(hit.score)}
              hit={hit}
              projectId={props.projectId}
              onNavigateToTask={props.onNavigateToTask}
              onNavigateToDeliverable={props.onNavigateToDeliverable}
              onNavigateToApproval={props.onNavigateToApproval}
            />
          ))}
        </div>
      ) : (
        <div className="border-y border-dashed border-[#333333] py-6 text-sm leading-6 text-zinc-500">
          没有找到匹配的项目记忆。可以换一个更贴近交付摘要、审批意见、失败模式或运行结论的关键词。
        </div>
      )}
    </section>
  );
}
