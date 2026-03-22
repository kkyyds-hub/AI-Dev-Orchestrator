import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { APPROVAL_STATUS_LABELS } from "../approvals/types";
import { DELIVERABLE_TYPE_LABELS } from "../deliverables/types";
import { ROLE_CODE_LABELS } from "../roles/types";
import { useProjectTimeline } from "./hooks";
import {
  PROJECT_STAGE_LABELS,
  PROJECT_TIMELINE_EVENT_TYPE_LABELS,
  type ProjectTimelineEvent,
  type ProjectTimelineEventType,
} from "./types";

type ProjectTimelinePageProps = {
  projectId: string | null;
  projectName: string | null;
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

export function ProjectTimelinePage(props: ProjectTimelinePageProps) {
  const timelineQuery = useProjectTimeline(props.projectId);
  const [activeFilters, setActiveFilters] = useState<ProjectTimelineEventType[]>([]);

  useEffect(() => {
    setActiveFilters([]);
  }, [props.projectId]);

  const visibleEvents = useMemo(() => {
    const events = timelineQuery.data?.events ?? [];
    if (!activeFilters.length) {
      return events;
    }

    return events.filter((event) => activeFilters.includes(event.event_type));
  }, [activeFilters, timelineQuery.data?.events]);

  const toggleFilter = (eventType: ProjectTimelineEventType) => {
    setActiveFilters((previous) =>
      previous.includes(eventType)
        ? previous.filter((item) => item !== eventType)
        : [...previous, eventType],
    );
  };

  if (!props.projectId) {
    return (
      <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
        <div className="text-lg font-semibold text-slate-50">项目时间线</div>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          请先选择一个项目，再查看阶段推进、角色交接、审批动作和交付件版本的统一时间线。
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-5 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
      <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
            V3 Day11 Project Timeline
          </p>
          <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
            项目时间线与交付件对比视图
          </h2>
          <p className="max-w-3xl text-sm leading-6 text-slate-300">
            以项目为单位汇总阶段推进、交付件版本、审批动作、角色交接和运行决策，方便从“过程”快速跳回“任务、运行、审批、交付件”。
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <MiniStat label="当前项目" value={props.projectName ?? "未选择"} />
          <MiniStat
            label="时间线事件"
            value={String(timelineQuery.data?.total_events ?? 0)}
          />
          <MiniStat
            label="当前筛选结果"
            value={String(visibleEvents.length)}
          />
        </div>
      </header>

      {timelineQuery.isLoading && !timelineQuery.data ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 px-4 py-8 text-center text-sm text-slate-400">
          正在汇总项目时间线…
        </div>
      ) : timelineQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-8 text-center text-sm text-rose-100">
          项目时间线加载失败：{timelineQuery.error.message}
        </div>
      ) : (
        <>
          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-50">事件筛选</h3>
                <p className="mt-1 text-sm text-slate-400">
                  支持按最小事件类型过滤，帮助老板快速聚焦“阶段 / 交付件 / 审批 / 角色交接 / 运行决策”。
                </p>
              </div>
              <div className="text-sm text-slate-400">
                生成时间：
                {timelineQuery.data?.generated_at
                  ? formatDateTime(timelineQuery.data.generated_at)
                  : "—"}
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => setActiveFilters([])}
                className={`rounded-full border px-4 py-2 text-sm transition ${
                  !activeFilters.length
                    ? "border-cyan-400/60 bg-cyan-500/10 text-cyan-100"
                    : "border-slate-700 bg-slate-950/70 text-slate-300 hover:border-slate-500"
                }`}
              >
                全部
              </button>
              {(timelineQuery.data?.event_type_counts ?? []).map((bucket) => {
                const isActive = activeFilters.includes(bucket.event_type);
                return (
                  <button
                    key={bucket.event_type}
                    type="button"
                    onClick={() => toggleFilter(bucket.event_type)}
                    className={`rounded-full border px-4 py-2 text-sm transition ${
                      isActive
                        ? "border-cyan-400/60 bg-cyan-500/10 text-cyan-100"
                        : "border-slate-700 bg-slate-950/70 text-slate-300 hover:border-slate-500"
                    }`}
                  >
                    {PROJECT_TIMELINE_EVENT_TYPE_LABELS[bucket.event_type] ??
                      bucket.label}
                    <span className="ml-2 text-slate-400">{bucket.count}</span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-slate-50">统一项目时间线</h3>
                <p className="mt-1 text-sm text-slate-400">
                  所有事件按时间倒序排列；每一条都尽量保留任务、运行、审批与交付件跳转入口。
                </p>
              </div>
              <StatusBadge label={`${visibleEvents.length} 条可见事件`} tone="neutral" />
            </div>

            {visibleEvents.length ? (
              <div className="mt-5 space-y-4">
                {visibleEvents.map((event) => (
                  <TimelineEventCard
                    key={event.id}
                    event={event}
                    projectId={props.projectId as string}
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
        </>
      )}
    </section>
  );
}

function TimelineEventCard(props: {
  projectId: string;
  event: ProjectTimelineEvent;
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
  const typeTone = props.event.tone ?? "neutral";
  const deliverableType = props.event.metadata.deliverable_type;
  const roleActor =
    props.event.actor && props.event.actor in ROLE_CODE_LABELS
      ? ROLE_CODE_LABELS[props.event.actor]
      : props.event.actor;

  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge label={props.event.label} tone={typeTone} />
            {props.event.stage ? (
              <StatusBadge
                label={PROJECT_STAGE_LABELS[props.event.stage] ?? props.event.stage}
                tone="neutral"
              />
            ) : null}
            {typeof deliverableType === "string" &&
            deliverableType in DELIVERABLE_TYPE_LABELS ? (
              <StatusBadge
                label={
                  DELIVERABLE_TYPE_LABELS[
                    deliverableType as keyof typeof DELIVERABLE_TYPE_LABELS
                  ]
                }
                tone="info"
              />
            ) : null}
            {props.event.approval_status ? (
              <StatusBadge
                label={
                  APPROVAL_STATUS_LABELS[
                    props.event.approval_status as keyof typeof APPROVAL_STATUS_LABELS
                  ] ?? props.event.approval_status
                }
                tone="neutral"
              />
            ) : null}
          </div>

          <h4 className="mt-3 text-lg font-semibold text-slate-50">
            {props.event.title}
          </h4>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            {props.event.summary}
          </p>

          <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
            <span>{formatDateTime(props.event.occurred_at)}</span>
            {props.event.task_title ? <span>任务：{props.event.task_title}</span> : null}
            {roleActor ? <span>角色 / 审批人：{roleActor}</span> : null}
            {props.event.deliverable_title ? (
              <span>
                交付件：{props.event.deliverable_title}
                {props.event.deliverable_version_number
                  ? ` v${props.event.deliverable_version_number}`
                  : ""}
              </span>
            ) : null}
            {props.event.source_event ? <span>源事件：{props.event.source_event}</span> : null}
          </div>
        </div>

        <div className="flex flex-wrap gap-3 xl:justify-end">
          {props.event.task_id && props.onNavigateToTask ? (
            <button
              type="button"
              onClick={() =>
                props.onNavigateToTask?.(props.event.task_id as string, { runId: null })
              }
              className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
            >
              查看任务
            </button>
          ) : null}
          {props.event.task_id && props.event.run_id && props.onNavigateToTask ? (
            <button
              type="button"
              onClick={() =>
                props.onNavigateToTask?.(props.event.task_id as string, {
                  runId: props.event.run_id,
                })
              }
              className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 transition hover:bg-emerald-500/20"
            >
              查看运行
            </button>
          ) : null}
          {props.event.deliverable_id && props.onNavigateToDeliverable ? (
            <button
              type="button"
              onClick={() =>
                props.onNavigateToDeliverable?.({
                  projectId: props.projectId,
                  deliverableId: props.event.deliverable_id as string,
                })
              }
              className="rounded-xl border border-violet-400/30 bg-violet-500/10 px-4 py-2 text-sm text-violet-100 transition hover:bg-violet-500/20"
            >
              查看交付件
            </button>
          ) : null}
          {props.event.approval_id && props.onNavigateToApproval ? (
            <button
              type="button"
              onClick={() =>
                props.onNavigateToApproval?.({
                  projectId: props.projectId,
                  approvalId: props.event.approval_id as string,
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

function MiniStat(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}
