import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { PROJECT_STAGE_LABELS } from "./types";
import {
  APPROVAL_ACTION_LABELS,
  APPROVAL_STATUS_LABELS,
  PROJECT_APPROVAL_CYCLE_STATUS_LABELS,
} from "../approvals/types";
import { useProjectApprovalRetrospective } from "../approvals/hooks";

type ProjectRetrospectivePanelProps = {
  projectId: string | null;
  projectName: string | null;
  onNavigateToApproval?: (input: { projectId: string; approvalId: string }) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function ProjectRetrospectivePanel(props: ProjectRetrospectivePanelProps) {
  const retrospectiveQuery = useProjectApprovalRetrospective(props.projectId);

  if (!props.projectId) {
    return (
      <section className="rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
        <div className="text-lg font-semibold text-slate-50">项目复盘收口</div>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          先选择项目，再查看审批驳回、返工链路与失败复盘的收口结果。
        </p>
      </section>
    );
  }

  return (
    <section
      id="project-retrospective"
      className="space-y-5 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30"
    >
      <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
            V3 Day12 Project Retrospective
          </p>
          <h2 className="text-3xl font-semibold tracking-tight text-slate-50">
            审批回退重做与项目复盘收口
          </h2>
          <p className="max-w-3xl text-sm leading-6 text-slate-300">
            汇总项目内的关键审批失败、返工状态与失败运行复盘，帮助你确认“提交 - 审批 - 驳回/通过 - 重做”闭环是否已经真正打通。
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <RetroStat label="当前项目" value={props.projectName ?? "未选择"} />
          <RetroStat
            label="审批返工回路"
            value={String(retrospectiveQuery.data?.summary.negative_approval_cycles ?? 0)}
          />
          <RetroStat
            label="待收口返工"
            value={String(retrospectiveQuery.data?.summary.open_rework_cycles ?? 0)}
          />
          <RetroStat
            label="失败复盘"
            value={String(retrospectiveQuery.data?.summary.total_failure_reviews ?? 0)}
          />
        </div>
      </header>

      {retrospectiveQuery.isLoading && !retrospectiveQuery.data ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/40 px-4 py-8 text-center text-sm text-slate-400">
          正在汇总项目复盘结论...
        </div>
      ) : retrospectiveQuery.isError ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-8 text-center text-sm text-rose-100">
          项目复盘加载失败：{retrospectiveQuery.error.message}
        </div>
      ) : retrospectiveQuery.data ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <RetroStat
              label="审批请求数"
              value={String(retrospectiveQuery.data.summary.total_approval_requests)}
            />
            <RetroStat
              label="审批返工回路"
              value={String(retrospectiveQuery.data.summary.negative_approval_cycles)}
            />
            <RetroStat
              label="待收口返工"
              value={String(retrospectiveQuery.data.summary.open_rework_cycles)}
            />
            <RetroStat
              label="失败复盘总数"
              value={String(retrospectiveQuery.data.summary.total_failure_reviews)}
            />
            <RetroStat
              label="失败聚类"
              value={String(retrospectiveQuery.data.summary.failure_clusters)}
            />
          </div>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-slate-100">审批返工回路</div>
                <div className="mt-1 text-xs leading-5 text-slate-400">
                  聚焦所有被驳回或要求补充的审批，并标记它们目前处于待返工、返工中、已重提还是返工后通过。
                </div>
              </div>
              <div className="text-xs text-slate-500">
                生成时间：{formatDateTime(retrospectiveQuery.data.generated_at)}
              </div>
            </div>

            {retrospectiveQuery.data.approval_cycles.length > 0 ? (
              <div className="mt-4 space-y-3">
                {retrospectiveQuery.data.approval_cycles.map((cycle) => (
                  <article
                    key={cycle.cycle_id}
                    className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <StatusBadge
                            label={PROJECT_APPROVAL_CYCLE_STATUS_LABELS[cycle.status]}
                            tone={mapCycleTone(cycle.status)}
                          />
                          <StatusBadge
                            label={APPROVAL_ACTION_LABELS[cycle.decision_action]}
                            tone={mapDecisionTone(cycle.decision_action)}
                          />
                          <StatusBadge
                            label={PROJECT_STAGE_LABELS[cycle.deliverable_stage] ?? cycle.deliverable_stage}
                            tone="info"
                          />
                          <StatusBadge
                            label={`v${cycle.deliverable_version_number} -> v${cycle.current_version_number}`}
                            tone="neutral"
                          />
                          {cycle.latest_approval_status ? (
                            <StatusBadge
                              label={APPROVAL_STATUS_LABELS[cycle.latest_approval_status]}
                              tone={mapApprovalTone(cycle.latest_approval_status)}
                            />
                          ) : null}
                        </div>
                        <div className="mt-3 text-lg font-semibold text-slate-50">
                          {cycle.deliverable_title}
                        </div>
                        <p className="mt-2 text-sm leading-6 text-slate-300">{cycle.summary}</p>
                        {cycle.comment ? (
                          <p className="mt-2 text-sm leading-6 text-slate-400">{cycle.comment}</p>
                        ) : null}
                      </div>
                      <div className="text-right text-xs text-slate-500">
                        <div>驳回时间：{formatDateTime(cycle.decided_at)}</div>
                        {cycle.resubmitted_at ? (
                          <div className="mt-1">
                            最近重提：{formatDateTime(cycle.resubmitted_at)}
                          </div>
                        ) : null}
                      </div>
                    </div>

                    {cycle.requested_changes.length > 0 ? (
                      <TagList title="改动方向" items={cycle.requested_changes} tone="info" />
                    ) : null}
                    {cycle.highlighted_risks.length > 0 ? (
                      <TagList title="关键风险" items={cycle.highlighted_risks} tone="warning" />
                    ) : null}

                    <div className="mt-4 flex flex-wrap gap-3">
                      {props.onNavigateToApproval ? (
                        <button
                          type="button"
                          onClick={() =>
                            props.onNavigateToApproval?.({
                              projectId: props.projectId as string,
                              approvalId: cycle.approval_id,
                            })
                          }
                          className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-100 transition hover:bg-amber-500/20"
                        >
                          查看原审批
                        </button>
                      ) : null}
                      {props.onNavigateToApproval &&
                      cycle.latest_approval_id &&
                      cycle.latest_approval_id !== cycle.approval_id ? (
                        <button
                          type="button"
                          onClick={() =>
                            props.onNavigateToApproval?.({
                              projectId: props.projectId as string,
                              approvalId: cycle.latest_approval_id as string,
                            })
                          }
                          className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
                        >
                          查看最新重提
                        </button>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-sm leading-6 text-slate-400">
                当前项目还没有形成审批返工回路，说明审批暂未被驳回，或尚未提交审批。
              </div>
            )}
          </section>

          <div className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
            <section className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
              <div className="text-sm font-medium text-slate-100">失败复盘聚类</div>
              <div className="mt-1 text-xs leading-5 text-slate-400">
                结合 V2 的失败复盘记录，快速看到当前项目最常见的失败类别与样例任务。
              </div>

              {retrospectiveQuery.data.failure_clusters.length > 0 ? (
                <div className="mt-4 space-y-3">
                  {retrospectiveQuery.data.failure_clusters.map((cluster) => (
                    <article
                      key={cluster.cluster_key}
                      className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <StatusBadge label={cluster.failure_category} tone="danger" />
                          <StatusBadge label={`${cluster.count} 次`} tone="warning" />
                        </div>
                        <div className="text-xs text-slate-500">
                          最新时间：{formatDateTime(cluster.latest_run_created_at)}
                        </div>
                      </div>
                      {cluster.route_reason_excerpt ? (
                        <p className="mt-3 text-sm leading-6 text-slate-300">
                          {cluster.route_reason_excerpt}
                        </p>
                      ) : null}
                      {cluster.sample_task_titles.length > 0 ? (
                        <TagList
                          title="样例任务"
                          items={cluster.sample_task_titles}
                          tone="neutral"
                        />
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-sm leading-6 text-slate-400">
                  当前项目还没有落盘的失败复盘记录。
                </div>
              )}
            </section>

            <section className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
              <div className="text-sm font-medium text-slate-100">最近失败运行</div>
              <div className="mt-1 text-xs leading-5 text-slate-400">
                这里保留项目内最近的失败 / 取消运行，用于把审批闭环与执行失败复盘串联起来。
              </div>

              {retrospectiveQuery.data.recent_failures.length > 0 ? (
                <div className="mt-4 space-y-3">
                  {retrospectiveQuery.data.recent_failures.map((item) => (
                    <article
                      key={item.run_id}
                      className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <StatusBadge label={item.run_status} tone="danger" />
                          {item.failure_category ? (
                            <StatusBadge label={item.failure_category} tone="warning" />
                          ) : null}
                        </div>
                        <div className="text-xs text-slate-500">
                          {formatDateTime(item.created_at)}
                        </div>
                      </div>

                      <div className="mt-3 text-base font-semibold text-slate-50">
                        {item.task_title ?? item.task_id}
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-300">{item.headline}</p>
                      {item.review ? (
                        <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-900/60 px-3 py-3 text-sm leading-6 text-slate-300">
                          <div className="font-medium text-slate-100">{item.review.conclusion}</div>
                          <div className="mt-1 text-slate-400">处置摘要：{item.review.action_summary}</div>
                        </div>
                      ) : null}
                      {item.stages.length > 0 ? (
                        <TagList title="涉及阶段" items={item.stages} tone="neutral" />
                      ) : null}

                      <div className="mt-4 flex flex-wrap gap-3">
                        {props.onNavigateToTask ? (
                          <button
                            type="button"
                            onClick={() => props.onNavigateToTask?.(item.task_id, { runId: item.run_id })}
                            className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
                          >
                            查看运行
                          </button>
                        ) : null}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-sm leading-6 text-slate-400">
                  当前项目还没有失败 / 取消运行记录。
                </div>
              )}
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}

function RetroStat(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}

function TagList(props: {
  title: string;
  items: string[];
  tone: "neutral" | "info" | "warning";
}) {
  return (
    <div className="mt-4">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{props.title}</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {props.items.map((item) => (
          <StatusBadge key={`${props.title}-${item}`} label={item} tone={props.tone} />
        ))}
      </div>
    </div>
  );
}

function mapDecisionTone(action: "approve" | "reject" | "request_changes") {
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

function mapApprovalTone(status: "pending_approval" | "approved" | "rejected" | "changes_requested") {
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

function mapCycleTone(status: string) {
  switch (status) {
    case "approved_after_rework":
      return "success" as const;
    case "resubmitted_pending_approval":
      return "info" as const;
    case "reworking":
      return "warning" as const;
    default:
      return "danger" as const;
  }
}
