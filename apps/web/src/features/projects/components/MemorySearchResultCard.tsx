import { useState } from "react";

import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { ROLE_CODE_LABELS } from "../../roles/types";
import type { ProjectMemorySearchHit } from "../types";
import {
  PROJECT_MEMORY_KIND_LABELS,
  PROJECT_MEMORY_SOURCE_KIND_LABELS,
  PROJECT_STAGE_LABELS,
} from "../types";
import { mapMemoryTone } from "./ProjectMemoryShared";

export function MemorySearchResultCard(props: {
  hit: ProjectMemorySearchHit;
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
  const item = props.hit.item;
  const taskId = item.task_id;
  const deliverableId = item.deliverable_id;
  const approvalId = item.approval_id;
  const [isDetailExpanded, setIsDetailExpanded] = useState(false);

  return (
    <article className="py-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={PROJECT_MEMORY_KIND_LABELS[item.memory_type]}
            tone={mapMemoryTone(item.memory_type)}
          />
          <StatusBadge
            label={
              PROJECT_MEMORY_SOURCE_KIND_LABELS[item.source_kind] ??
              item.source_kind
            }
            tone="neutral"
          />
        </div>
        <div className="text-xs text-zinc-600">
          相关度 {props.hit.score.toFixed(1)} · {formatDateTime(item.created_at)}
        </div>
      </div>

      <h4 className="mt-3 max-w-4xl break-words text-base font-semibold text-zinc-50">
        {item.title}
      </h4>
      <p className="mt-2 max-w-4xl whitespace-pre-wrap break-words text-sm leading-6 text-zinc-400">
        {item.summary}
      </p>

      <div className="mt-3 flex flex-wrap gap-3 text-xs text-zinc-500">
        {item.stage ? <span>阶段 {PROJECT_STAGE_LABELS[item.stage] ?? item.stage}</span> : null}
        {item.role_code ? <span>角色 {ROLE_CODE_LABELS[item.role_code] ?? item.role_code}</span> : null}
        {item.actor_name ? <span>参与者 {item.actor_name}</span> : null}
        <span>来源 {item.source_label}</span>
      </div>

      {props.hit.matched_terms.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {props.hit.matched_terms.slice(0, 4).map((term) => (
            <StatusBadge key={item.memory_id + "-" + term} label={"命中 " + term} tone="info" />
          ))}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {item.detail ? (
          <button
            type="button"
            onClick={() => setIsDetailExpanded((current) => !current)}
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
            aria-expanded={isDetailExpanded}
          >
            {isDetailExpanded ? "收起详情" : "展开详情"}
          </button>
        ) : null}

        {taskId ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToTask?.(taskId, {
                runId: item.run_id,
              })
            }
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
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
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
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
            className="rounded border border-[#3a3a3a] bg-transparent px-3 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
          >
            查看审批
          </button>
        ) : null}
      </div>

      {isDetailExpanded && item.detail ? (
        <div className="mt-4 max-h-52 overflow-y-auto overscroll-contain whitespace-pre-wrap break-words border-l border-[#333333] pl-4 pr-3 text-sm leading-6 text-zinc-300">
          {item.detail}
        </div>
      ) : null}
    </article>
  );
}
