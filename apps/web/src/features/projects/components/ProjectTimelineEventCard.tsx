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
      <aside className="min-w-0 border border-dashed border-[#3a3a3a] px-5 py-8 text-sm leading-6 text-zinc-400">
        选择左侧事件后，这里会展示事件详情、相关对象和操作入口。
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
  const visibleMetadataEntries = metadataEntries.slice(0, 4);
  const collapsedMetadataEntries = metadataEntries.slice(4);

  return (
    <aside className="min-w-0 space-y-5 border border-[#333333] px-5 py-5 xl:sticky xl:top-24 xl:max-h-[760px] xl:overflow-y-auto">
      <div className="border-b border-[#333333] pb-5">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={PROJECT_TIMELINE_EVENT_TYPE_LABELS[event.event_type] ?? event.label}
            tone={typeTone}
          />
          {event.stage ? (
            <StatusBadge
              label={PROJECT_STAGE_LABELS[event.stage] ?? "未知阶段"}
              tone="neutral"
            />
          ) : null}
          {isDeliverableType(deliverableType) ? (
            <StatusBadge label={DELIVERABLE_TYPE_LABELS[deliverableType]} tone="info" />
          ) : null}
          {approvalStatusLabel ? <StatusBadge label={approvalStatusLabel} tone="neutral" /> : null}
        </div>

        <h3 className="mt-4 break-words text-xl font-semibold leading-7 text-zinc-100">
          {event.title}
        </h3>
        <p className="mt-3 break-words text-sm leading-6 text-zinc-400">{event.summary}</p>
      </div>

      <section className="space-y-3 border-b border-[#333333] pb-5">
        <DetailRow label="发生时间" value={formatDateTime(event.occurred_at)} />
        {event.task_title ? <DetailRow label="任务" value={event.task_title} /> : null}
        {roleActor ? <DetailRow label="角色" value={roleActor} /> : null}
        {event.deliverable_title ? (
          <DetailRow
            label="交付物"
            value={`${event.deliverable_title}${
              event.deliverable_version_number
                ? ` · v${event.deliverable_version_number}`
                : ""
            }`}
          />
        ) : null}
        {event.source_event ? <DetailRow label="源事件" value={event.source_event} /> : null}
      </section>

      <section className="border-b border-[#333333] pb-5">
        <div className="text-xs font-medium tracking-[0.18em] text-zinc-500">
          操作入口
        </div>
        <div className="mt-3 flex flex-wrap gap-3">
          {taskId && props.onNavigateToTask ? (
            <TimelineActionButton onClick={() => props.onNavigateToTask?.(taskId, { runId: null })}>
              查看任务
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
              查看运行
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
              查看交付物
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
              查看审批
            </TimelineActionButton>
          ) : null}
          {!taskId && !deliverableId && !approvalId ? (
            <span className="text-sm text-zinc-500">当前事件没有可跳转对象。</span>
          ) : null}
        </div>
      </section>

      {metadataEntries.length > 0 ? (
        <section>
          <div className="text-xs font-medium tracking-[0.18em] text-zinc-500">
            事件元数据
          </div>
          <div className="mt-3 space-y-2 text-xs leading-5 text-zinc-400">
            {visibleMetadataEntries.map(([key, value]) => (
              <DetailRow key={key} label={formatMetadataLabel(key)} value={formatMetadataValue(value)} />
            ))}
            {collapsedMetadataEntries.length > 0 ? (
              <details className="group border-t border-[#333333] pt-3">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-xs text-zinc-400 transition hover:text-zinc-200">
                  <span>展开更多元数据</span>
                  <span className="text-zinc-500 group-open:hidden">展开</span>
                  <span className="hidden text-zinc-500 group-open:inline">收起</span>
                </summary>
                <div className="mt-3 space-y-2">
                  {collapsedMetadataEntries.map(([key, value]) => (
                    <DetailRow key={key} label={formatMetadataLabel(key)} value={formatMetadataValue(value)} />
                  ))}
                </div>
              </details>
            ) : null}
          </div>
        </section>
      ) : null}
    </aside>
  );
}

function DetailRow(props: { label: string; value: string }) {
  return (
    <div className="grid min-w-0 gap-2 text-sm sm:grid-cols-[104px_minmax(0,1fr)]">
      <div className="min-w-0 break-words text-xs text-zinc-500">
        {props.label}
      </div>
      <div className="min-w-0 break-all text-zinc-400">{props.value}</div>
    </div>
  );
}

function TimelineActionButton(props: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className="rounded border border-[#4a4a4a] bg-transparent px-3 py-2 text-xs font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929]"
    >
      {props.children}
    </button>
  );
}

function formatMetadataLabel(key: string) {
  const labels: Record<string, string> = {
    approval_id: "审批编号",
    approval_status: "审批状态",
    completion_tokens: "输出令牌",
    deliverable_id: "交付物编号",
    deliverable_title: "交付物",
    deliverable_type: "交付类型",
    deliverable_version_id: "版本编号",
    deliverable_version_number: "版本号",
    from_stage: "原阶段",
    next_stage: "下一阶段",
    model_name: "模型名称",
    prompt_tokens: "输入令牌",
    project_id: "项目编号",
    role_code: "角色",
    route_reason: "路由原因",
    run_id: "运行编号",
    run_status: "运行状态",
    source_event: "源事件",
    task_id: "任务编号",
    task_status: "任务状态",
    task_title: "任务",
    to_stage: "目标阶段",
    estimated_cost: "预估成本",
  };

  return labels[key] ?? key.replace(/_/g, " ");
}

function formatMetadataValue(value: unknown) {
  if (typeof value === "string") {
    return translateKnownMetadataValue(value);
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function translateKnownMetadataValue(value: string) {
  const labels: Record<string, string> = {
    active: "进行中",
    archived: "已归档",
    blocked: "阻塞",
    cancelled: "已取消",
    completed: "已完成",
    danger: "阻塞",
    delivery: "交付中",
    execution: "执行中",
    failed: "失败",
    healthy: "健康",
    intake: "需求入口",
    on_hold: "挂起",
    paused: "已暂停",
    pending: "待处理",
    planning: "规划中",
    running: "执行中",
    succeeded: "成功",
    verification: "验证中",
    waiting_human: "待人工",
    warning: "需关注",
  };

  return labels[value] ?? value;
}
