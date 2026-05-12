import { StatusBadge } from "../../../components/StatusBadge";
import type { ProjectMemoryItem } from "../types";
import { ProjectMemoryCard } from "./ProjectMemoryCard";

export function ProjectMemoryLatestList(props: {
  projectId: string;
  latestItems: ProjectMemoryItem[];
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
    <section className="border-b border-[#333333] pb-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-zinc-50">最新沉淀</h3>
          <p className="mt-1 text-sm text-zinc-500">
            展示最近生成的项目记忆，帮助快速回看经验来源与上下游引用入口。
          </p>
        </div>
        <StatusBadge label={`${props.latestItems.length} 条`} tone="neutral" />
      </div>

      {props.latestItems.length > 0 ? (
        <div className="mt-4 divide-y divide-[#333333] border-y border-[#333333]">
          {props.latestItems.map((item) => (
            <ProjectMemoryCard
              key={item.memory_id}
              item={item}
              projectId={props.projectId}
              onNavigateToTask={props.onNavigateToTask}
              onNavigateToDeliverable={props.onNavigateToDeliverable}
              onNavigateToApproval={props.onNavigateToApproval}
            />
          ))}
        </div>
      ) : (
        <div className="mt-4 border-y border-dashed border-[#333333] py-6 text-sm leading-6 text-zinc-500">
          当前项目还没有可展示的记忆记录。可先通过运行、审批或交付件版本形成可沉淀证据，再回来刷新本面板。
        </div>
      )}
    </section>
  );
}
