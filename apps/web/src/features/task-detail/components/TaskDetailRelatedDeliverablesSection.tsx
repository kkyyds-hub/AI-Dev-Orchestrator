import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import {
  DELIVERABLE_TYPE_LABELS,
  type TaskRelatedDeliverable,
} from "../../deliverables/types";

export function TaskDetailRelatedDeliverablesSection(props: {
  relatedDeliverables: TaskRelatedDeliverable[] | undefined;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
}) {
  const count = props.relatedDeliverables?.length ?? 0;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-50">关联交付件</h3>
          <p className="mt-1 text-sm text-slate-400">
            反查当前任务及其运行记录对应的 PRD、设计稿、代码计划或验收结论快照。
          </p>
        </div>
        <StatusBadge label={`${count} 条关联`} tone="info" />
      </div>

      {props.isLoading && !props.relatedDeliverables ? (
        <p className="mt-4 text-sm leading-6 text-slate-400">正在查询关联交付件...</p>
      ) : props.isError ? (
        <p className="mt-4 text-sm leading-6 text-rose-200">
          关联交付件加载失败：{props.errorMessage}
        </p>
      ) : props.relatedDeliverables && props.relatedDeliverables.length > 0 ? (
        <div className="mt-4 space-y-3">
          {props.relatedDeliverables.map((relatedItem) => (
            <RelatedDeliverableCard
              key={`${relatedItem.deliverable_id}-${relatedItem.matched_version.id}`}
              item={relatedItem}
              onNavigateToDeliverable={props.onNavigateToDeliverable}
            />
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-4 text-sm leading-6 text-slate-400">
          当前任务或其运行记录还没有关联的交付件快照。
        </div>
      )}
    </div>
  );
}

function RelatedDeliverableCard(props: {
  item: TaskRelatedDeliverable;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-sm font-medium text-slate-50">{props.item.title}</div>
            <StatusBadge label={DELIVERABLE_TYPE_LABELS[props.item.type]} tone="info" />
            <StatusBadge label={`v${props.item.matched_version.version_number}`} tone="neutral" />
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            {props.item.matched_version.summary}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusBadge label={props.item.stage} tone="neutral" />
          {props.item.matched_version.source_run_id ? (
            <StatusBadge label="来自运行快照" tone="success" />
          ) : (
            <StatusBadge label="来自任务快照" tone="warning" />
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
        <span>交付件 ID：{props.item.deliverable_id}</span>
        <span>最新版本：v{props.item.current_version_number}</span>
        <span>快照时间：{formatDateTime(props.item.matched_version.created_at)}</span>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        {props.onNavigateToDeliverable ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToDeliverable?.({
                projectId: props.item.project_id,
                deliverableId: props.item.deliverable_id,
              })
            }
            className="rounded-lg border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
          >
            跳到交付件中心
          </button>
        ) : null}
        {props.item.matched_version.source_run_id ? (
          <code className="rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2 text-xs text-slate-400">
            Run {props.item.matched_version.source_run_id}
          </code>
        ) : null}
      </div>
    </div>
  );
}
