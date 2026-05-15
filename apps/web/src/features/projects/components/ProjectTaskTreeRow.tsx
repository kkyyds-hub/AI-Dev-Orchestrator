import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { mapTaskStatusTone } from "../../../lib/status";
import { ROLE_CODE_LABELS } from "../../roles/types";
import type { ProjectDetailTaskItem } from "../types";
import {
  HUMAN_STATUS_LABELS,
  TASK_PRIORITY_LABELS,
  TASK_RISK_LABELS,
  TASK_STATUS_LABELS,
} from "../types";

export function ProjectTaskTreeRow(props: { task: ProjectDetailTaskItem }) {
  const indent = Math.min(props.task.depth, 5) * 18;
  const dependencyText =
    props.task.depends_on_task_ids.length > 0
      ? `依赖 ${props.task.depends_on_task_ids.join(", ")}`
      : "根任务";

  return (
    <div
      className="border border-[#333333] bg-transparent/60 px-4 py-4"
      style={{ marginLeft: `${indent}px` }}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-zinc-100">
              {props.task.title}
            </span>
            <StatusBadge
              label={TASK_STATUS_LABELS[props.task.status] ?? props.task.status}
              tone={mapTaskStatusTone(props.task.status)}
            />
            <StatusBadge
              label={
                TASK_PRIORITY_LABELS[props.task.priority] ?? props.task.priority
              }
              tone="info"
            />
            {props.task.owner_role_code ? (
              <StatusBadge
                label={`责任 ${ROLE_CODE_LABELS[props.task.owner_role_code] ?? props.task.owner_role_code}`}
                tone="success"
              />
            ) : null}
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-400">
            {props.task.input_summary}
          </p>
        </div>

        <div className="flex flex-wrap gap-2 text-xs">
          <StatusBadge
            label={TASK_RISK_LABELS[props.task.risk_level] ?? props.task.risk_level}
            tone="warning"
          />
          <StatusBadge
            label={
              HUMAN_STATUS_LABELS[props.task.human_status] ??
              props.task.human_status
            }
            tone={props.task.human_status === "none" ? "neutral" : "warning"}
          />
          <StatusBadge
            label={
              props.task.source_draft_id
                ? `草案 ${props.task.source_draft_id}`
                : "手动创建"
            }
            tone={props.task.source_draft_id ? "info" : "neutral"}
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-3 text-xs text-zinc-500">
        <span>{dependencyText}</span>
        <span>子任务 {props.task.child_task_ids.length} 个</span>
        <span>更新时间 {formatDateTime(props.task.updated_at)}</span>
        {props.task.upstream_role_code ? (
          <span>
            上游 {ROLE_CODE_LABELS[props.task.upstream_role_code] ?? props.task.upstream_role_code}
          </span>
        ) : null}
        {props.task.downstream_role_code ? (
          <span>
            下游{" "}
            {ROLE_CODE_LABELS[props.task.downstream_role_code] ?? props.task.downstream_role_code}
          </span>
        ) : null}
      </div>

      {props.task.acceptance_criteria.length > 0 ? (
        <ul className="mt-3 space-y-2 text-sm leading-6 text-zinc-400">
          {props.task.acceptance_criteria.map((criterion) => (
            <li
              key={criterion}
              className="rounded-xl border border-[#333333] bg-transparent/60 px-3 py-2"
            >
              {criterion}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
