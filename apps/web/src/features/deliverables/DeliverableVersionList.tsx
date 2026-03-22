import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { PROJECT_STAGE_LABELS } from "../projects/types";
import { ROLE_CODE_LABELS } from "../roles/types";
import { DeliverableDiffPanel } from "./DeliverableDiffPanel";
import {
  DELIVERABLE_CONTENT_FORMAT_LABELS,
  DELIVERABLE_TYPE_LABELS,
  type DeliverableDetail,
  type DeliverableSummary,
  type DeliverableVersion,
} from "./types";

type DeliverableVersionListProps = {
  deliverable: DeliverableSummary | null;
  detail: DeliverableDetail | null;
  isLoading: boolean;
  errorMessage: string | null;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function DeliverableVersionList(props: DeliverableVersionListProps) {
  if (!props.deliverable) {
    return (
      <section className="rounded-2xl border border-dashed border-slate-800 bg-slate-950/40 p-5 text-sm leading-6 text-slate-400">
        请先从左侧选择一个交付件，再查看版本快照与版本对比。
      </section>
    );
  }

  const deliverable = props.deliverable;

  return (
    <section className="space-y-5 rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
      <header className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-slate-50">
              {deliverable.title}
            </h3>
            <StatusBadge
              label={DELIVERABLE_TYPE_LABELS[deliverable.type]}
              tone="info"
            />
            <StatusBadge
              label={PROJECT_STAGE_LABELS[deliverable.stage] ?? deliverable.stage}
              tone="neutral"
            />
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            创建角色：
            {ROLE_CODE_LABELS[deliverable.created_by_role_code] ??
              deliverable.created_by_role_code}
            ，当前版本 v{deliverable.current_version_number}，累计
            {deliverable.total_versions} 个快照。
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <MiniInfo label="创建时间" value={formatDateTime(deliverable.created_at)} />
          <MiniInfo label="最近更新" value={formatDateTime(deliverable.updated_at)} />
        </div>
      </header>

      {props.isLoading ? (
        <p className="text-sm leading-6 text-slate-400">正在加载交付件版本快照…</p>
      ) : props.errorMessage ? (
        <p className="text-sm leading-6 text-rose-200">
          交付件详情加载失败：{props.errorMessage}
        </p>
      ) : props.detail && props.detail.versions.length > 0 ? (
        <>
          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h4 className="text-base font-semibold text-slate-50">版本快照列表</h4>
                <p className="mt-1 text-sm leading-6 text-slate-400">
                  先看每次提交的摘要，再进入下方对比视图查看版本变化。
                </p>
              </div>
              <StatusBadge
                label={`${props.detail.versions.length} 个版本`}
                tone="neutral"
              />
            </div>

            <div className="mt-4 space-y-3">
              {props.detail.versions.map((version) => (
                <DeliverableVersionCard
                  key={version.id}
                  deliverableType={deliverable.type}
                  version={version}
                  onNavigateToTask={props.onNavigateToTask}
                />
              ))}
            </div>
          </section>

          <DeliverableDiffPanel
            deliverable={deliverable}
            detail={props.detail}
            onNavigateToTask={props.onNavigateToTask}
          />
        </>
      ) : (
        <p className="text-sm leading-6 text-slate-400">
          当前交付件尚未产生可展示的版本快照。
        </p>
      )}
    </section>
  );
}

function DeliverableVersionCard(props: {
  deliverableType: DeliverableSummary["type"];
  version: DeliverableVersion;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
}) {
  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
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
          <p className="mt-2 text-sm leading-6 text-slate-300">{props.version.summary}</p>
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
        {props.version.source_task_id && props.version.source_run_id && props.onNavigateToTask ? (
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

function MiniInfo(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}
