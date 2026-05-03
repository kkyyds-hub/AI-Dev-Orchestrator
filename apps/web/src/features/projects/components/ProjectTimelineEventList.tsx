import { StatusBadge } from "../../../components/StatusBadge";
import type { ProjectTimelineEvent } from "../types";
import { ProjectTimelineEventCard } from "./ProjectTimelineEventCard";

export function ProjectTimelineEventList(props: {
  projectId: string;
  events: ProjectTimelineEvent[];
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-50">统一项目时间线</h3>
          <p className="mt-1 text-sm text-slate-400">
            所有事件按时间倒序排列；每一条都尽量保留任务、运行、审批与交付件跳转入口。
          </p>
        </div>
        <StatusBadge label={`${props.events.length} 条可见事件`} tone="neutral" />
      </div>

      {props.events.length ? (
        <div className="mt-5 space-y-4">
          {props.events.map((event) => (
            <ProjectTimelineEventCard
              key={event.id}
              event={event}
              projectId={props.projectId}
              onNavigateToTask={props.onNavigateToTask}
              onNavigateToDeliverable={props.onNavigateToDeliverable}
              onNavigateToApproval={props.onNavigateToApproval}
            />
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-800 bg-slate-950/40 px-4 py-8 text-center text-sm text-slate-400">
          当前筛选条件下没有匹配的时间线事件。
        </div>
      )}
    </section>
  );
}
