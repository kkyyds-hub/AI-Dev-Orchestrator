import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import type { ProjectRetrospectiveFailureRun } from "../../approvals/types";
import { ProjectRetrospectiveTagList } from "./ProjectRetrospectiveShared";

export function ProjectRetrospectiveRecentFailures(props: {
  recentFailures: ProjectRetrospectiveFailureRun[];
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="text-sm font-medium text-slate-100">最近失败运行</div>
      <div className="mt-1 text-xs leading-5 text-slate-400">
        这里保留项目内最近的失败 / 取消运行，用于把审批闭环与执行失败复盘串联起来。
      </div>

      {props.recentFailures.length > 0 ? (
        <div className="mt-4 space-y-3">
          {props.recentFailures.map((item) => (
            <article
              key={item.run_id}
              className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge label={item.run_status} tone="danger" />
                  {item.failure_category ? (
                    <StatusBadge label={item.failure_category} tone="warning" />
                  ) : null}
                </div>
                <div className="text-xs text-slate-500">
                  {formatDateTime(item.created_at)}
                </div>
              </div>

              <div className="mt-3 text-base font-semibold text-slate-50">
                {item.task_title ?? item.task_id}
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-300">{item.headline}</p>
              {item.review ? (
                <div className="mt-3 rounded-2xl border border-slate-800 bg-slate-900/60 px-3 py-3 text-sm leading-6 text-slate-300">
                  <div className="font-medium text-slate-100">{item.review.conclusion}</div>
                  <div className="mt-1 text-slate-400">处置摘要：{item.review.action_summary}</div>
                </div>
              ) : null}
              {item.stages.length > 0 ? (
                <ProjectRetrospectiveTagList
                  title="涉及阶段"
                  items={item.stages}
                  tone="neutral"
                />
              ) : null}

              <div className="mt-4 flex flex-wrap gap-3">
                {props.onNavigateToTask ? (
                  <button
                    type="button"
                    onClick={() =>
                      props.onNavigateToTask?.(item.task_id, { runId: item.run_id })
                    }
                    className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 transition hover:bg-cyan-500/20"
                  >
                    查看运行
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 px-4 py-6 text-sm leading-6 text-slate-400">
          当前项目还没有失败 / 取消运行记录。
        </div>
      )}
    </section>
  );
}
