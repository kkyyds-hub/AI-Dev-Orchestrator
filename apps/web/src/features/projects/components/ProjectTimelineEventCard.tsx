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
import { PROJECT_STAGE_LABELS, PROJECT_TIMELINE_EVENT_TYPE_LABELS } from "../types";

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
    event: ProjectTimelineEvent | null;
  },
) {
  if (!props.event) {
    return (
      <aside className="border border-dashed border-[#3a3a3a] px-5 py-8 text-sm leading-6 text-slate-400">
        Select an event on the left to inspect details, related objects, and actions.
      </aside>
    );
  }

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
  const metadataEntries = Object.entries(event.metadata).filter(
    ([, value]) => value !== null && value !== undefined && value !== "",
  );

  return (
    <aside className="space-y-5 border-t border-[#333333] pt-5 xl:sticky xl:top-24 xl:border-l xl:border-t-0 xl:pl-5 xl:pt-0">
      <div className="border-b border-[#333333] pb-5">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={PROJECT_TIMELINE_EVENT_TYPE_LABELS[event.event_type] ?? event.label}
            tone={typeTone}
          />
          {event.stage ? (
            <StatusBadge
              label={PROJECT_STAGE_LABELS[event.stage] ?? event.stage}
              tone="neutral"
            />
          ) : null}
          {isDeliverableType(deliverableType) ? (
            <StatusBadge label={DELIVERABLE_TYPE_LABELS[deliverableType]} tone="info" />
          ) : null}
          {approvalStatusLabel ? <StatusBadge label={approvalStatusLabel} tone="neutral" /> : null}
        </div>

        <h3 className="mt-4 text-xl font-semibold leading-7 text-slate-50">
          {event.title}
        </h3>
        <p className="mt-3 text-sm leading-6 text-slate-300">{event.summary}</p>
      </div>

      <section className="space-y-3 border-b border-[#333333] pb-5">
        <DetailRow label="Time" value={formatDateTime(event.occurred_at)} />
        {event.task_title ? <DetailRow label="Task" value={event.task_title} /> : null}
        {roleActor ? <DetailRow label="Actor" value={roleActor} /> : null}
        {event.deliverable_title ? (
          <DetailRow
            label="Deliverable"
            value={`${event.deliverable_title}${
              event.deliverable_version_number
                ? ` - v${event.deliverable_version_number}`
                : ""
            }`}
          />
        ) : null}
        {event.source_event ? <DetailRow label="Source" value={event.source_event} /> : null}
      </section>

      <section className="border-b border-[#333333] pb-5">
        <div className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
          Actions
        </div>
        <div className="mt-3 flex flex-wrap gap-3">
          {taskId && props.onNavigateToTask ? (
            <TimelineActionButton onClick={() => props.onNavigateToTask?.(taskId, { runId: null })}>
              View task
            </TimelineActionButton>
          ) : null}
          {taskId && runId && props.onNavigateToTask ? (
            <TimelineActionButton
              onClick={() =>
                props.onNavigateToTask?.(taskId, {
                  runId,
                })
              }
            >
              View run
            </TimelineActionButton>
          ) : null}
          {deliverableId && props.onNavigateToDeliverable ? (
            <TimelineActionButton
              onClick={() =>
                props.onNavigateToDeliverable?.({
                  projectId: props.projectId,
                  deliverableId,
                })
              }
            >
              View deliverable
            </TimelineActionButton>
          ) : null}
          {approvalId && props.onNavigateToApproval ? (
            <TimelineActionButton
              onClick={() =>
                props.onNavigateToApproval?.({
                  projectId: props.projectId,
                  approvalId,
                })
              }
            >
              View approval
            </TimelineActionButton>
          ) : null}
          {!taskId && !deliverableId && !approvalId ? (
            <span className="text-sm text-slate-500">No linked object for this event.</span>
          ) : null}
        </div>
      </section>

      {metadataEntries.length > 0 ? (
        <section>
          <div className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
            Metadata
          </div>
          <div className="mt-3 space-y-2 text-xs leading-5 text-slate-400">
            {metadataEntries.slice(0, 8).map(([key, value]) => (
              <DetailRow key={key} label={key} value={formatMetadataValue(value)} />
            ))}
          </div>
        </section>
      ) : null}
    </aside>
  );
}

function DetailRow(props: { label: string; value: string }) {
  return (
    <div className="grid gap-2 text-sm sm:grid-cols-[92px_minmax(0,1fr)]">
      <div className="text-xs uppercase tracking-[0.14em] text-slate-500">{props.label}</div>
      <div className="min-w-0 break-words text-slate-300">{props.value}</div>
    </div>
  );
}

function TimelineActionButton(props: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className="rounded border border-[#4a4a4a] bg-transparent px-3 py-2 text-xs font-medium text-zinc-100 transition hover:bg-[#292929]"
    >
      {props.children}
    </button>
  );
}

function formatMetadataValue(value: unknown) {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}
