import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import {
  DELIVERABLE_TYPE_LABELS,
  type TaskRelatedDeliverable,
} from "../../deliverables/types";
import type { TaskDetailSurfaceVariant } from "./TaskDetailField";

export function TaskDetailRelatedDeliverablesSection(props: {
  relatedDeliverables: TaskRelatedDeliverable[] | undefined;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string;
  surfaceVariant?: TaskDetailSurfaceVariant;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
}) {
  const count = props.relatedDeliverables?.length ?? 0;
  const isLine = props.surfaceVariant === "line";

  return (
    <section className={isLine ? "border-b border-[#333333] pb-5" : "rounded-xl border border-[#333333] bg-transparent p-4"}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className={`text-base font-semibold ${isLine ? "text-zinc-100" : "text-zinc-100"}`}>关联交付件</h3>
          <p className={`mt-1 text-sm leading-6 ${isLine ? "text-zinc-500" : "text-zinc-400"}`}>
            反查当前任务及其运行记录对应的 PRD、设计稿、代码计划或验收结论快照。
          </p>
        </div>
        <StatusBadge label={`${count} 条关联`} tone="info" />
      </div>

      {props.isLoading && !props.relatedDeliverables ? (
        <p className={`mt-4 text-sm leading-6 ${isLine ? "text-zinc-500" : "text-zinc-400"}`}>正在查询关联交付件...</p>
      ) : props.isError ? (
        <p className="mt-4 text-sm leading-6 text-rose-200">
          关联交付件加载失败：{props.errorMessage}
        </p>
      ) : props.relatedDeliverables && props.relatedDeliverables.length > 0 ? (
        <div className={isLine ? "mt-4 divide-y divide-[#333333] border-y border-[#333333]" : "mt-4 space-y-3"}>
          {props.relatedDeliverables.map((relatedItem) => (
            <RelatedDeliverableCard
              key={`${relatedItem.deliverable_id}-${relatedItem.matched_version.id}`}
              item={relatedItem}
              surfaceVariant={props.surfaceVariant}
              onNavigateToDeliverable={props.onNavigateToDeliverable}
            />
          ))}
        </div>
      ) : (
        <div className={isLine ? "mt-4 border-y border-dashed border-[#333333] py-6 text-sm leading-6 text-zinc-500" : "mt-4 rounded-xl border border-dashed border-[#333333] bg-transparent p-4 text-sm leading-6 text-zinc-400"}>
          当前任务或其运行记录还没有关联的交付件快照。
        </div>
      )}
    </section>
  );
}

function RelatedDeliverableCard(props: {
  item: TaskRelatedDeliverable;
  surfaceVariant?: TaskDetailSurfaceVariant;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
}) {
  const isLine = props.surfaceVariant === "line";

  return (
    <div className={isLine ? "py-4" : "rounded-xl border border-[#333333] bg-transparent p-4"}>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className={`text-sm font-medium ${isLine ? "text-zinc-100" : "text-zinc-100"}`}>{props.item.title}</div>
            <StatusBadge label={DELIVERABLE_TYPE_LABELS[props.item.type]} tone="info" />
            <StatusBadge label={`v${props.item.matched_version.version_number}`} tone="neutral" />
          </div>
          <p className={`mt-2 text-sm leading-6 ${isLine ? "text-zinc-300" : "text-zinc-400"}`}>
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

      <div className={`mt-3 flex flex-wrap gap-3 text-xs ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>
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
            className={isLine ? "rounded-md border border-[#333333] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:bg-[#2f2f2f]" : "rounded-lg border border-cyan-400/30 bg-transparent px-4 py-2 text-sm text-zinc-100 transition hover:bg-transparent"}
          >
            跳到交付件中心
          </button>
        ) : null}
        {props.item.matched_version.source_run_id ? (
          <code className={isLine ? "border-l border-[#333333] px-3 py-2 text-xs text-zinc-500" : "rounded-lg border border-[#333333] bg-transparent px-3 py-2 text-xs text-zinc-400"}>
            Run {props.item.matched_version.source_run_id}
          </code>
        ) : null}
      </div>
    </div>
  );
}
