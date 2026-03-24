import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { useProjectChangeRework } from "./hooks";
import {
  CHANGE_REWORK_RECOMMENDATION_LABELS,
  CHANGE_REWORK_SOURCE_LABELS,
  CHANGE_REWORK_STAGE_LABELS,
  type ChangeReworkRecommendation,
  type ProjectChangeReworkItem,
} from "./types";

type ChangeReworkPanelProps = {
  projectId: string | null;
  projectName: string | null;
  onNavigateToApproval?: (input: { projectId: string; approvalId: string }) => void;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
};

export function ChangeReworkPanel(props: ChangeReworkPanelProps) {
  const query = useProjectChangeRework(props.projectId);

  if (!props.projectId) {
    return (
      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="text-base font-semibold text-slate-50">Day12 回退重做收口</div>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          先选择项目，再查看“计划 → 验证 → 驳回/失败 → 回退重做”全链路。
        </p>
      </section>
    );
  }

  const payload = query.data ?? null;
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">V4 Day12</div>
          <h3 className="mt-2 text-lg font-semibold text-slate-50">回退重做与仓库复盘收口</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            对验证失败与审批驳回进行显式收口，保留原批次、证据包与失败原因关联。
          </p>
        </div>
        <div className="text-xs text-slate-500">项目：{props.projectName ?? "未命名项目"}</div>
      </div>

      {query.isLoading && !payload ? (
        <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/40 px-4 py-6 text-sm text-slate-400">
          正在汇总回退重做链路...
        </div>
      ) : query.isError ? (
        <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-6 text-sm text-rose-100">
          回退重做链路加载失败：{query.error.message}
        </div>
      ) : payload ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MiniStat label="收口项总数" value={String(payload.summary.total_items)} />
            <MiniStat label="审批返工" value={String(payload.summary.approval_rework_items)} />
            <MiniStat
              label="验证返工"
              value={String(payload.summary.verification_rework_items)}
            />
            <MiniStat
              label="开放项"
              value={`${payload.summary.open_items}/${payload.summary.total_items}`}
            />
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <MiniStat
              label="回退建议"
              value={String(payload.summary.rollback_recommendations)}
            />
            <MiniStat
              label="重规划建议"
              value={String(payload.summary.replan_recommendations)}
            />
          </div>

          {payload.items.length > 0 ? (
            <div className="mt-5 space-y-4">
              {payload.items.map((item) => (
                <ChangeReworkCard
                  key={item.rework_id}
                  item={item}
                  projectId={props.projectId as string}
                  onNavigateToApproval={props.onNavigateToApproval}
                  onNavigateToDeliverable={props.onNavigateToDeliverable}
                />
              ))}
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-sm text-slate-400">
              当前项目尚未出现需要回退重做的变更链路。
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}

function ChangeReworkCard(props: {
  item: ProjectChangeReworkItem;
  projectId: string;
  onNavigateToApproval?: (input: { projectId: string; approvalId: string }) => void;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
}) {
  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={CHANGE_REWORK_SOURCE_LABELS[props.item.chain_source]}
            tone="info"
          />
          <StatusBadge
            label={mapStatusLabel(props.item.status)}
            tone={mapStatusTone(props.item.status)}
          />
          <StatusBadge
            label={CHANGE_REWORK_RECOMMENDATION_LABELS[props.item.recommendation]}
            tone={mapRecommendationTone(props.item.recommendation)}
          />
          {props.item.closed ? (
            <StatusBadge label="已闭环" tone="success" />
          ) : (
            <StatusBadge label="待处理" tone="warning" />
          )}
        </div>
        <div className="text-xs text-slate-500">{formatDateTime(props.item.occurred_at)}</div>
      </div>

      <div className="mt-3 text-sm font-medium text-slate-100">{props.item.reason_summary}</div>
      {props.item.reason_comment ? (
        <p className="mt-2 text-sm leading-6 text-slate-300">{props.item.reason_comment}</p>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-400">
        {props.item.change_batch_title ? <span>批次：{props.item.change_batch_title}</span> : null}
        {props.item.deliverable_title ? <span>交付件：{props.item.deliverable_title}</span> : null}
        {props.item.latest_failure_category ? (
          <span>失败归因：{props.item.latest_failure_category}</span>
        ) : null}
        <span>
          验证失败 {props.item.verification_failed_runs}/{props.item.verification_total_runs}
        </span>
      </div>
      {props.item.evidence_package_key ? (
        <div className="mt-2 text-xs text-slate-500">
          证据包键：
          <code className="ml-1 rounded bg-slate-900 px-2 py-1 text-slate-300">
            {props.item.evidence_package_key}
          </code>
        </div>
      ) : null}

      {props.item.requested_changes.length > 0 ? (
        <TagList title="要求重做项" items={props.item.requested_changes} tone="info" />
      ) : null}
      {props.item.highlighted_risks.length > 0 ? (
        <TagList title="高亮风险" items={props.item.highlighted_risks} tone="warning" />
      ) : null}

      {props.item.steps.length > 0 ? (
        <div className="mt-4 space-y-2">
          {props.item.steps.map((step) => (
            <div
              key={step.step_id}
              className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <StatusBadge
                    label={CHANGE_REWORK_STAGE_LABELS[step.stage] ?? step.stage}
                    tone={mapStepTone(step.stage)}
                  />
                  <span className="text-sm font-medium text-slate-100">{step.label}</span>
                </div>
                <span className="text-xs text-slate-500">{formatDateTime(step.occurred_at)}</span>
              </div>
              <div className="mt-2 text-sm leading-6 text-slate-300">{step.summary}</div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-3">
        {props.item.deliverable_id && props.onNavigateToDeliverable ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToDeliverable?.({
                projectId: props.projectId,
                deliverableId: props.item.deliverable_id as string,
              })
            }
            className="rounded-xl border border-violet-400/30 bg-violet-500/10 px-4 py-2 text-sm text-violet-100 transition hover:bg-violet-500/20"
          >
            查看交付件
          </button>
        ) : null}
        {props.item.approval_id && props.onNavigateToApproval ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToApproval?.({
                projectId: props.projectId,
                approvalId: props.item.approval_id as string,
              })
            }
            className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-100 transition hover:bg-amber-500/20"
          >
            查看审批
          </button>
        ) : null}
      </div>
    </article>
  );
}

function MiniStat(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{props.label}</div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}

function TagList(props: {
  title: string;
  items: string[];
  tone: "info" | "warning";
}) {
  return (
    <div className="mt-3">
      <div className="mb-2 text-xs uppercase tracking-[0.16em] text-slate-500">{props.title}</div>
      <div className="flex flex-wrap gap-2">
        {props.items.map((item) => (
          <StatusBadge key={`${props.title}-${item}`} label={item} tone={props.tone} />
        ))}
      </div>
    </div>
  );
}

function mapStatusLabel(status: string) {
  switch (status) {
    case "rework_required":
      return "待重做";
    case "reworking":
      return "重做中";
    case "resubmitted_pending_approval":
      return "已重提待审批";
    case "approved_after_rework":
      return "重做后已通过";
    case "manual_rejected":
      return "人工驳回";
    case "verification_failed":
      return "验证失败";
    default:
      return status;
  }
}

function mapStatusTone(status: string) {
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

function mapRecommendationTone(recommendation: ChangeReworkRecommendation) {
  switch (recommendation) {
    case "rollback":
      return "danger" as const;
    case "replan":
      return "warning" as const;
    default:
      return "info" as const;
  }
}

function mapStepTone(stage: string) {
  switch (stage) {
    case "plan":
      return "neutral" as const;
    case "verification":
      return "warning" as const;
    case "decision":
      return "danger" as const;
    case "failure":
      return "danger" as const;
    case "rework":
      return "info" as const;
    default:
      return "neutral" as const;
  }
}
