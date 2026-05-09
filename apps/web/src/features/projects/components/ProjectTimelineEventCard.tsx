import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import {
  APPROVAL_STATUS_LABELS,
  type ApprovalStatus,
} from "../../approvals/types";
import {
  DELIVERABLE_TYPE_LABELS,
  type DeliverableType,
} from "../../deliverables/types";
import { ROLE_CODE_LABELS } from "../../roles/types";
import type { ProjectTimelineEvent } from "../types";
import { PROJECT_STAGE_LABELS } from "../types";

type ProjectTimelineNavigationProps = {
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
  onNavigateToApproval?: (input: {
    projectId: string;
    approvalId: string;
  }) => void;
};

function isDeliverableType(value: unknown): value is DeliverableType {
  return (
    typeof value === "string" &&
    Object.prototype.hasOwnProperty.call(DELIVERABLE_TYPE_LABELS, value)
  );
}

function isApprovalStatus(value: string): value is ApprovalStatus {
  return Object.prototype.hasOwnProperty.call(APPROVAL_STATUS_LABELS, value);
}

export function ProjectTimelineEventCard(
  props: ProjectTimelineNavigationProps & {
    projectId: string;
    event: ProjectTimelineEvent;
  },
) {
  const event = props.event;
  const typeTone = event.tone ?? "neutral";
  const deliverableType = event.metadata.deliverable_type;
  const approvalStatus = event.approval_status;
  const approvalStatusLabel = approvalStatus
    ? isApprovalStatus(approvalStatus)
      ? APPROVAL_STATUS_LABELS[approvalStatus]
      : approvalStatus
    : null;
  const roleActor =
    event.actor && event.actor in ROLE_CODE_LABELS
      ? ROLE_CODE_LABELS[event.actor]
      : event.actor;
  const taskId = event.task_id;
  const runId = event.run_id;
  const deliverableId = event.deliverable_id;
  const approvalId = event.approval_id;

  return (
    <article className="px-0 py-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge label={event.label} tone={typeTone} />
            {event.stage ? (
              <StatusBadge
                label={PROJECT_STAGE_LABELS[event.stage] ?? event.stage}
                tone="neutral"
              />
            ) : null}
            {isDeliverableType(deliverableType) ? (
              <StatusBadge
                label={DELIVERABLE_TYPE_LABELS[deliverableType]}
                tone="info"
              />
            ) : null}
            {approvalStatusLabel ? (
              <StatusBadge label={approvalStatusLabel} tone="neutral" />
            ) : null}
          </div>

          <h4 className="mt-3 text-lg font-semibold text-slate-50">
            {event.title}
          </h4>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            {event.summary}
          </p>

          <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
            <span>{formatDateTime(event.occurred_at)}</span>
            {event.task_title ? <span>任务：{event.task_title}</span> : null}
            {roleActor ? <span>角色 / 审批人：{roleActor}</span> : null}
            {event.deliverable_title ? (
              <span>
                交付件：{event.deliverable_title}
                {event.deliverable_version_number
                  ? ` v${event.deliverable_version_number}`
                  : ""}
              </span>
            ) : null}
            {event.source_event ? <span>源事件：{event.source_event}</span> : null}
          </div>
        </div>

        <div className="flex flex-wrap gap-3 xl:justify-end">
          {taskId && props.onNavigateToTask ? (
            <button
              type="button"
              onClick={() => props.onNavigateToTask?.(taskId, { runId: null })}
              className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
            >
              查看任务
            </button>
          ) : null}
          {taskId && runId && props.onNavigateToTask ? (
            <button
              type="button"
              onClick={() =>
                props.onNavigateToTask?.(taskId, {
                  runId,
                })
              }
              className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 transition hover:bg-emerald-500/20"
            >
              查看运行
            </button>
          ) : null}
          {deliverableId && props.onNavigateToDeliverable ? (
            <button
              type="button"
              onClick={() =>
                props.onNavigateToDeliverable?.({
                  projectId: props.projectId,
                  deliverableId,
                })
              }
              className="rounded-xl border border-violet-400/30 bg-violet-500/10 px-4 py-2 text-sm text-violet-100 transition hover:bg-violet-500/20"
            >
              查看交付件
            </button>
          ) : null}
          {approvalId && props.onNavigateToApproval ? (
            <button
              type="button"
              onClick={() =>
                props.onNavigateToApproval?.({
                  projectId: props.projectId,
                  approvalId,
                })
              }
              className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-100 transition hover:bg-amber-500/20"
            >
              查看审批
            </button>
          ) : null}
        </div>
      </div>
    </article>
  );
}
