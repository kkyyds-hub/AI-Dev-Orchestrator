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
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-zinc-50">最新沉淀</h3>
          <p className="mt-1 text-sm text-zinc-500">
            以线条列表展示最近生成的项目记忆，保留来源与跳转入口。
          </p>
        </div>
        <StatusBadge label={String(props.latestItems.length) + " 条"} tone="neutral" />
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
          <h4 className="text-base font-semibold text-zinc-100">暂无最新沉淀</h4>
          <p className="mt-2">
            当前项目还没有可展示的记忆记录。完成运行、审批或交付件版本沉淀后，可回来刷新查看。
          </p>
        </div>
      )}
    </section>
  );
}
