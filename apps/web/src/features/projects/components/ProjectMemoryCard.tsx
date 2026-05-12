import { useState } from "react";

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
  const [isDetailExpanded, setIsDetailExpanded] = useState(false);

  return (
    <article className="py-5">
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

        <div className="text-xs text-zinc-600">
          {formatDateTime(item.created_at)}
        </div>
      </div>

      <div className="mt-3 max-w-4xl break-words text-base font-semibold text-zinc-50">
        {item.title}
      </div>
      <p className="mt-2 max-w-4xl whitespace-pre-wrap break-words text-sm leading-6 text-zinc-400">
        {item.summary}
      </p>

      {item.detail ? (
        <div className="mt-4 max-w-4xl">
          <button
            type="button"
            onClick={() => setIsDetailExpanded((current) => !current)}
            className="text-xs font-medium text-zinc-400 transition hover:text-zinc-100"
            aria-expanded={isDetailExpanded}
          >
            {isDetailExpanded ? "收起详情" : "展开详情"}
          </button>
          {isDetailExpanded ? (
            <div className="mt-3 max-h-60 overflow-y-auto overscroll-contain whitespace-pre-wrap break-words border-l border-[#333333] pl-4 pr-3 text-sm leading-6 text-zinc-300">
              {item.detail}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-3 text-xs text-zinc-500">
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
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
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
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
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
            className="rounded border border-[#3a3a3a] bg-transparent px-4 py-2 text-sm text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-50"
          >
            查看审批
          </button>
        ) : null}
      </div>
    </article>
  );
}
