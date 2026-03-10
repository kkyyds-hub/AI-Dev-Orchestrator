import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { mapLogLevelTone } from "../../lib/status";
import type { ConsoleRun } from "../console/types";
import { useDecisionTrace, useRunLogs } from "./hooks";

type RunLogPanelProps = {
  selectedRun: ConsoleRun | null;
};

export function RunLogPanel({ selectedRun }: RunLogPanelProps) {
  const logsQuery = useRunLogs(selectedRun?.id ?? null);
  const decisionTraceQuery = useDecisionTrace(selectedRun?.id ?? null);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-50">日志事件</h3>
          <p className="mt-1 text-sm text-slate-400">
            {selectedRun
              ? "读取结构化 jsonl 事件，不直接展示原始日志文件。"
              : "先选择一条运行记录，再查看结构化日志事件。"}
          </p>
        </div>
        {selectedRun ? <StatusBadge label="Day 12" tone="info" /> : null}
      </div>

      {!selectedRun ? (
        <div className="mt-4 rounded-xl border border-dashed border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-400">
          当前还没有选中的运行记录。
        </div>
      ) : logsQuery.isError ? (
        <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          无法加载该运行的日志事件：{logsQuery.error.message}
        </div>
      ) : logsQuery.isLoading && !logsQuery.data ? (
        <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-300">
          正在读取日志事件…
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {decisionTraceQuery.data ? (
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h4 className="text-sm font-semibold text-slate-50">决策回放</h4>
                  <p className="mt-1 text-xs text-slate-500">
                    基于结构化日志还原这次运行的路由、执行、验证和收口过程。
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge label={decisionTraceQuery.data.run_status} tone="info" />
                  {decisionTraceQuery.data.failure_category ? (
                    <StatusBadge
                      label={decisionTraceQuery.data.failure_category}
                      tone="warning"
                    />
                  ) : null}
                </div>
              </div>

              {decisionTraceQuery.data.failure_review ? (
                <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">
                  <div className="font-medium text-amber-50">失败复盘结论</div>
                  <p className="mt-1">{decisionTraceQuery.data.failure_review.conclusion}</p>
                  <p className="mt-2 text-xs text-amber-200">
                    处置摘要：{decisionTraceQuery.data.failure_review.action_summary}
                  </p>
                </div>
              ) : null}

              <div className="mt-4 space-y-3">
                {decisionTraceQuery.data.trace_items.map((item, index) => (
                  <div
                    key={`${item.timestamp}-${item.event}-${index}`}
                    className="rounded-xl border border-slate-800 bg-slate-950/70 p-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-slate-100">
                          {item.title}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          {formatDecisionStage(item.stage)} · {formatDateTime(item.timestamp)}
                        </div>
                      </div>
                      <StatusBadge label={item.level} tone={mapLogLevelTone(item.level)} />
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-300">{item.summary}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2">
            <InfoRow label="Run ID" value={selectedRun.id} />
            <InfoRow label="日志路径" value={logsQuery.data?.log_path ?? selectedRun.log_path ?? "—"} />
          </div>

          {logsQuery.data?.truncated ? (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-100">
              当前只展示最近 {logsQuery.data.limit} 条日志事件，避免一次读取过大。
            </div>
          ) : null}

          {logsQuery.data?.events.length ? (
            <div className="max-h-[28rem] space-y-3 overflow-y-auto pr-1">
              {logsQuery.data.events.map((event, index) => (
                <div
                  key={`${event.timestamp}-${event.event}-${index}`}
                  className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-slate-100">{event.event}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {formatDateTime(event.timestamp)}
                      </div>
                    </div>
                    <StatusBadge label={event.level} tone={mapLogLevelTone(event.level)} />
                  </div>

                  <p className="mt-3 text-sm leading-6 text-slate-300">{event.message}</p>

                  {Object.keys(event.data).length ? (
                    <pre className="mt-3 overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/80 p-3 text-xs leading-6 text-slate-300">
                      {JSON.stringify(event.data, null, 2)}
                    </pre>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-400">
              {selectedRun.log_path
                ? "日志文件已存在，但当前还没有可展示的结构化事件。"
                : "这次运行还没有日志路径。"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function formatDecisionStage(stage: string) {
  switch (stage) {
    case "routing":
      return "路由";
    case "claim":
      return "领取";
    case "context":
      return "上下文";
    case "guard":
      return "守卫";
    case "execution":
      return "执行";
    case "verification":
      return "验证";
    case "cost":
      return "成本";
    case "parallel":
      return "并行";
    case "finalize":
      return "收口";
    case "recovery":
      return "恢复";
    default:
      return "运行";
  }
}

function InfoRow(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 break-all text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}
