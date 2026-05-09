import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { ROLE_CODE_LABELS } from "../../roles/types";
import {
  DELIVERABLE_CONTENT_FORMAT_LABELS,
  DELIVERABLE_TYPE_LABELS,
  type DeliverableSummary,
  type DeliverableVersion,
} from "../types";

type DeliverableVersionCardProps = {
  deliverableType: DeliverableSummary["type"];
  version: DeliverableVersion;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function DeliverableVersionCard(props: DeliverableVersionCardProps) {
  return (
    <article className="px-0 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-base font-semibold text-slate-50">
              {DELIVERABLE_TYPE_LABELS[props.deliverableType]} · v
              {props.version.version_number}
            </div>
            <StatusBadge
              label={
                DELIVERABLE_CONTENT_FORMAT_LABELS[props.version.content_format] ??
                props.version.content_format
              }
              tone="neutral"
            />
            <StatusBadge
              label={
                ROLE_CODE_LABELS[props.version.author_role_code] ??
                props.version.author_role_code
              }
              tone="success"
            />
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            {props.version.summary}
          </p>
        </div>

        <div className="text-sm text-slate-400">
          {formatDateTime(props.version.created_at)}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        {props.version.source_task_id && props.onNavigateToTask ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToTask?.(props.version.source_task_id as string, {
                runId: null,
              })
            }
            className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
          >
            查看来源任务
          </button>
        ) : null}
        {props.version.source_task_id &&
        props.version.source_run_id &&
        props.onNavigateToTask ? (
          <button
            type="button"
            onClick={() =>
              props.onNavigateToTask?.(props.version.source_task_id as string, {
                runId: props.version.source_run_id,
              })
            }
            className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 transition hover:bg-emerald-500/20"
          >
            查看来源运行
          </button>
        ) : null}
        {props.version.source_task_id ? (
          <code className="rounded-xl border border-slate-800 bg-slate-900/80 px-3 py-2 text-xs text-slate-400">
            Task {props.version.source_task_id}
          </code>
        ) : null}
        {props.version.source_run_id ? (
          <code className="rounded-xl border border-slate-800 bg-slate-900/80 px-3 py-2 text-xs text-slate-400">
            Run {props.version.source_run_id}
          </code>
        ) : null}
      </div>
    </article>
  );
}
