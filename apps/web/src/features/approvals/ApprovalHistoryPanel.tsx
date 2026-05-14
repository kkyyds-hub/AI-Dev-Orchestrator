import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { PROJECT_STAGE_LABELS } from "../projects/types";
import { ROLE_CODE_LABELS } from "../roles/types";
import { useApprovalHistory } from "./hooks";
import type { ApprovalHistoryStep, ApprovalHistoryReworkStatus } from "./types";
import {
  APPROVAL_ACTION_LABELS,
  APPROVAL_HISTORY_EVENT_LABELS,
  APPROVAL_REWORK_STATUS_LABELS,
  APPROVAL_STATUS_LABELS,
} from "./types";

type ApprovalHistoryPanelProps = {
  approvalId: string | null;
  open?: boolean;
};

export function ApprovalHistoryPanel(props: ApprovalHistoryPanelProps) {
  const historyQuery = useApprovalHistory(props.approvalId, props.open ?? true);

  if (!props.approvalId) {
    return null;
  }

  return (
    <section className="border-b border-[#333333] pb-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-slate-100">审批记录与版本回放</div>
          <div className="mt-1 text-xs leading-5 text-slate-400">
            串联同一交付件的提交、审批、补充和重提记录，方便回看每一轮处理结果。
          </div>
        </div>
      </div>

      {historyQuery.isLoading && !historyQuery.data ? (
        <div className="mt-4 border border-dashed border-[#3a3a3a] px-4 py-6 text-sm text-slate-400">
          正在加载审批记录...
        </div>
      ) : historyQuery.isError ? (
        <div className="mt-4 border-l border-rose-500/50 px-4 py-6 text-sm text-rose-100">
          审批记录加载失败：{historyQuery.error.message}
        </div>
      ) : historyQuery.data ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <HistoryStat
              label="当前返工状态"
              value={APPROVAL_REWORK_STATUS_LABELS[historyQuery.data.rework_status]}
              tone={mapReworkStatusTone(historyQuery.data.rework_status)}
            />
            <HistoryStat
              label="审批请求数"
              value={String(historyQuery.data.total_requests)}
            />
            <HistoryStat
              label="驳回 / 补充次数"
              value={String(historyQuery.data.negative_decision_count)}
              tone={historyQuery.data.negative_decision_count > 0 ? "warning" : "neutral"}
            />
            <HistoryStat
              label="重提轮次"
              value={String(historyQuery.data.rework_round_count)}
              tone={historyQuery.data.rework_round_count > 0 ? "info" : "neutral"}
            />
          </div>

          <div className="mt-4 border-l border-[#333333] px-4 py-4">
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-300">
              <span className="font-medium text-slate-100">
                {historyQuery.data.deliverable_title}
              </span>
              <StatusBadge
                label={
                  PROJECT_STAGE_LABELS[historyQuery.data.deliverable_stage] ??
                  historyQuery.data.deliverable_stage
                }
                tone="info"
              />
              {historyQuery.data.latest_approval_status ? (
                <StatusBadge
                  label={
                    APPROVAL_STATUS_LABELS[historyQuery.data.latest_approval_status] ??
                    historyQuery.data.latest_approval_status
                  }
                  tone={mapApprovalStatusTone(historyQuery.data.latest_approval_status)}
                />
              ) : null}
              <span className="text-xs text-slate-500">
                当前版本 v{historyQuery.data.current_version_number}
              </span>
            </div>
          </div>

          <div className="mt-4 divide-y divide-[#333333] border-y border-[#333333]">
            {historyQuery.data.steps.map((step, index) => (
              <HistoryStepCard
                key={step.id}
                index={index + 1}
                step={step}
                isLast={index === historyQuery.data.steps.length - 1}
              />
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}

function HistoryStat(props: {
  label: string;
  value: string;
  tone?: "neutral" | "info" | "success" | "warning" | "danger";
}) {
  return (
    <div className="border-l border-[#333333] px-4 py-2">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{props.label}</div>
      <div className="mt-2">
        {props.tone ? (
          <StatusBadge label={props.value} tone={props.tone} />
        ) : (
          <span className="text-sm font-medium text-slate-100">{props.value}</span>
        )}
      </div>
    </div>
  );
}

function HistoryStepCard(props: {
  index: number;
  step: ApprovalHistoryStep;
  isLast: boolean;
}) {
  const actorLabel = props.step.actor_name
    ? props.step.actor_name
    : props.step.requester_role_code
      ? ROLE_CODE_LABELS[props.step.requester_role_code] ?? props.step.requester_role_code
      : props.step.author_role_code
        ? ROLE_CODE_LABELS[props.step.author_role_code] ?? props.step.author_role_code
        : null;

  return (
    <div className="relative px-0 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full border border-[#4a4a4a] bg-transparent text-xs font-semibold text-slate-300">
            {props.index}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                label={APPROVAL_HISTORY_EVENT_LABELS[props.step.event_kind]}
                tone={mapEventTone(props.step)}
              />
              <StatusBadge label={`v${props.step.deliverable_version_number}`} tone="neutral" />
              {props.step.decision_action ? (
                <StatusBadge
                  label={APPROVAL_ACTION_LABELS[props.step.decision_action]}
                  tone={mapDecisionTone(props.step.decision_action)}
                />
              ) : null}
              {props.step.approval_status ? (
                <StatusBadge
                  label={APPROVAL_STATUS_LABELS[props.step.approval_status]}
                  tone={mapApprovalStatusTone(props.step.approval_status)}
                />
              ) : null}
              {props.step.is_rework ? <StatusBadge label="返工链路" tone="warning" /> : null}
            </div>
            <div className="mt-2 text-sm font-medium text-slate-100">{props.step.summary}</div>
          </div>
        </div>

        <div className="text-right text-xs text-slate-500">
          <div>{formatDateTime(props.step.occurred_at)}</div>
          {actorLabel ? <div className="mt-1">责任方：{actorLabel}</div> : null}
        </div>
      </div>

      {props.step.request_note ? (
        <p className="mt-3 text-sm leading-6 text-slate-300">提交说明：{props.step.request_note}</p>
      ) : null}
      {props.step.comment ? (
        <p className="mt-3 text-sm leading-6 text-slate-300">补充备注：{props.step.comment}</p>
      ) : null}

      {props.step.requested_changes.length > 0 ? (
        <TagList title="改动方向" items={props.step.requested_changes} tone="info" />
      ) : null}
      {props.step.highlighted_risks.length > 0 ? (
        <TagList title="关键风险" items={props.step.highlighted_risks} tone="warning" />
      ) : null}
    </div>
  );
}

function TagList(props: {
  title: string;
  items: string[];
  tone: "info" | "warning";
}) {
  return (
    <div className="mt-4">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{props.title}</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {props.items.map((item) => (
          <StatusBadge key={item} label={item} tone={props.tone} />
        ))}
      </div>
    </div>
  );
}

function mapDecisionTone(action: NonNullable<ApprovalHistoryStep["decision_action"]>) {
  switch (action) {
    case "approve":
      return "success" as const;
    case "reject":
      return "danger" as const;
    case "request_changes":
      return "warning" as const;
    default:
      return "neutral" as const;
  }
}

function mapApprovalStatusTone(status: NonNullable<ApprovalHistoryStep["approval_status"]>) {
  switch (status) {
    case "approved":
      return "success" as const;
    case "rejected":
      return "danger" as const;
    case "changes_requested":
      return "warning" as const;
    case "pending_approval":
      return "info" as const;
    default:
      return "neutral" as const;
  }
}

function mapEventTone(step: ApprovalHistoryStep) {
  if (step.event_kind === "rework_version_submitted") {
    return "warning" as const;
  }
  if (step.decision_action === "approve") {
    return "success" as const;
  }
  if (step.decision_action === "reject") {
    return "danger" as const;
  }
  if (step.decision_action === "request_changes") {
    return "warning" as const;
  }
  return "info" as const;
}

function mapReworkStatusTone(status: ApprovalHistoryReworkStatus) {
  switch (status) {
    case "clean":
      return "success" as const;
    case "pending_approval":
    case "resubmitted":
      return "info" as const;
    case "approved_after_rework":
      return "success" as const;
    case "rework_required":
      return "danger" as const;
    case "reworking":
      return "warning" as const;
    default:
      return "neutral" as const;
  }
}
