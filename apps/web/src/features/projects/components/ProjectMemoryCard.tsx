import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { ROLE_CODE_LABELS } from "../../roles/types";
import type { ProjectMemoryItem } from "../types";
import {
  PROJECT_MEMORY_KIND_LABELS,
  PROJECT_MEMORY_SOURCE_KIND_LABELS,
  PROJECT_STAGE_LABELS,
} from "../types";
import { mapMemoryTone } from "./ProjectMemoryShared";

export function ProjectMemoryCard(props: {
  item: ProjectMemoryItem;
  projectId: string;
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
  const item = props.item;
  const tone = mapMemoryTone(item.memory_type);
  const taskId = item.task_id;
  const deliverableId = item.deliverable_id;
  const approvalId = item.approval_id;

  return (
    <article className="px-0 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={PROJECT_MEMORY_KIND_LABELS[item.memory_type]}
            tone={tone}
          />
          <StatusBadge
            label={
              PROJECT_MEMORY_SOURCE_KIND_LABELS[item.source_kind] ??
              item.source_kind
            }
            tone="neutral"
          />
          {item.stage ? (
            <StatusBadge
              label={PROJECT_STAGE_LABELS[item.stage] ?? item.stage}
              tone="info"
            />
          ) : null}
        </div>

        <div className="text-xs text-slate-500">
          {formatDateTime(item.created_at)}
        </div>
      </div>

      <div className="mt-3 text-base font-semibold text-slate-50">
        {item.title}
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-300">{item.summary}</p>

      {item.detail ? (
        <div className="mt-3 border-l border-[#333333] px-3 py-2 text-sm leading-6 text-slate-300">
          {item.detail}
        </div>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
        {item.role_code ? (
          <span>
            角色 {ROLE_CODE_LABELS[item.role_code] ?? item.role_code}
          </span>
        ) : null}
        {item.actor_name ? <span>参与者 {item.actor_name}</span> : null}
        <span>来源 {item.source_label}</span>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        {taskId ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToTask?.(taskId, {
                runId: item.run_id,
              })
            }
            className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
          >
            查看任务 / 运行
          </button>
        ) : null}
        {deliverableId ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToDeliverable?.({
                projectId: props.projectId,
                deliverableId,
              })
            }
            className="rounded-xl border border-slate-700 bg-slate-900/80 px-4 py-2 text-sm text-slate-100 transition hover:border-slate-600"
          >
            查看交付件
          </button>
        ) : null}
        {approvalId ? (
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
    </article>
  );
}
