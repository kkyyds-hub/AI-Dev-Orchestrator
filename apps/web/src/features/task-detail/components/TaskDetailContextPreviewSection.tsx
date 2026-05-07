import { StatusBadge } from "../../../components/StatusBadge";
import { formatDateTime } from "../../../lib/format";
import { mapRunStatusTone, mapTaskStatusTone } from "../../../lib/status";
import type { TaskContextPreview } from "../types";
import { DetailField } from "./TaskDetailField";

export function TaskDetailContextPreviewSection(props: {
  contextPreview: TaskContextPreview;
}) {
  const { contextPreview } = props;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-50">最小上下文包</h3>
          <p className="mt-1 text-sm text-slate-400">
            Worker 在执行前会聚合任务目标、依赖状态、最近运行片段和阻塞信号。
          </p>
        </div>
        <StatusBadge
          label={contextPreview.ready_for_execution ? "上下文就绪" : "存在阻塞信号"}
          tone={contextPreview.ready_for_execution ? "success" : "warning"}
        />
      </div>

      <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">上下文摘要</div>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">
          {contextPreview.context_summary}
        </p>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <DetailField
          label="上下文状态"
          value={contextPreview.ready_for_execution ? "可执行" : "需人工关注"}
        />
        <DetailField
          label="最近运行片段"
          value={String(contextPreview.recent_runs.length)}
        />
        <DetailField label="依赖摘要" value={String(contextPreview.dependency_items.length)} />
        <DetailField label="阻塞项" value={String(contextPreview.blocking_signals.length)} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">依赖状态</div>
          {contextPreview.dependency_items.length > 0 ? (
            <div className="mt-2 space-y-3">
              {contextPreview.dependency_items.map((dependency) => (
                <div
                  key={dependency.task_id}
                  className="rounded-xl border border-slate-800 bg-slate-900/70 p-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-slate-100">{dependency.title}</div>
                      <code className="mt-1 block break-all text-xs text-cyan-200">
                        {dependency.task_id}
                      </code>
                    </div>
                    <StatusBadge
                      label={dependency.status}
                      tone={mapTaskStatusTone(dependency.status)}
                    />
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-300">
                    {dependency.missing
                      ? "依赖任务不存在，需先补齐或重建。"
                      : dependency.latest_run_summary ?? "暂无依赖运行摘要"}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-500">无前置依赖，上下文更轻量。</p>
          )}
        </div>

        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">最近运行摘要</div>
          {contextPreview.recent_runs.length > 0 ? (
            <div className="mt-2 space-y-3">
              {contextPreview.recent_runs.map((run) => (
                <div key={run.run_id} className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-slate-100">
                        {formatDateTime(run.created_at)}
                      </div>
                      <code className="mt-1 block break-all text-xs text-cyan-200">
                        {run.run_id}
                      </code>
                    </div>
                    <StatusBadge label={run.status} tone={mapRunStatusTone(run.status)} />
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-300">
                    {run.result_summary ?? "暂无运行摘要"}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-500">这是首次执行，没有历史运行片段。</p>
          )}
        </div>
      </div>

      <div className="mt-4">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">阻塞信号</div>
        {contextPreview.blocking_signals.length > 0 ? (
          <div className="mt-2 space-y-2">
            {contextPreview.blocking_signals.map((signal, index) => (
              <div
                key={`${contextPreview.task_id}-context-block-${signal.code}-${index}`}
                className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-amber-50">{mapBlockingCategoryLabel(signal)}</div>
                  <code className="text-[11px] uppercase tracking-[0.12em] text-amber-200">
                    {signal.code}
                  </code>
                </div>
                <div className="mt-2 leading-6 text-amber-100">{signal.message}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
            当前没有显式阻塞信号；Worker 会按此上下文继续执行。
          </div>
        )}
      </div>
    </div>
  );
}

function mapBlockingCategoryLabel(signal: TaskContextPreview["blocking_signals"][number]): string {
  if (signal.category === "dependency") {
    return "依赖阻塞";
  }
  if (signal.category === "human") {
    return "人工阻塞";
  }
  if (signal.category === "pause") {
    return "暂停阻塞";
  }
  if (signal.category === "budget") {
    return "预算阻塞";
  }
  return "状态阻塞";
}
