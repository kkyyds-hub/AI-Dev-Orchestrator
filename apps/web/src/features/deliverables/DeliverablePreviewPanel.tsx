import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { ROLE_CODE_LABELS } from "../roles/types";
import {
  DELIVERABLE_CONTENT_FORMAT_LABELS,
  type DeliverableVersion,
} from "./types";

type DeliverablePreviewPanelProps = {
  title: string;
  version: DeliverableVersion;
  tone?: "neutral" | "info" | "success" | "warning";
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function DeliverablePreviewPanel(props: DeliverablePreviewPanelProps) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-base font-semibold text-slate-50">{props.title}</h4>
            <StatusBadge
              label={`v${props.version.version_number}`}
              tone={props.tone ?? "neutral"}
            />
            <StatusBadge
              label={
                DELIVERABLE_CONTENT_FORMAT_LABELS[props.version.content_format] ??
                props.version.content_format
              }
              tone="neutral"
            />
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            {props.version.summary}
          </p>
        </div>

        <div className="space-y-2 text-xs text-slate-400 xl:text-right">
          <div>
            提交角色：
            {ROLE_CODE_LABELS[props.version.author_role_code] ??
              props.version.author_role_code}
          </div>
          <div>提交时间：{formatDateTime(props.version.created_at)}</div>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
          Snapshot Preview
        </div>
        {props.version.content_format === "link" ? (
          <a
            href={props.version.content}
            target="_blank"
            rel="noreferrer"
            className="mt-3 block break-all text-sm text-cyan-200 underline underline-offset-4"
          >
            {props.version.content}
          </a>
        ) : (
          <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words text-sm leading-6 text-slate-200">
            {props.version.content}
          </pre>
        )}
      </div>

      {(props.version.source_task_id || props.version.source_run_id) && props.onNavigateToTask ? (
        <div className="mt-4 flex flex-wrap gap-3">
          {props.version.source_task_id ? (
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
          {props.version.source_task_id && props.version.source_run_id ? (
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
        </div>
      ) : null}
    </section>
  );
}
