import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { mapLogLevelTone } from "../../lib/status";
import type { ConsoleRun } from "../console/types";
import { useRunLogs } from "./hooks";

type RunLogPanelProps = {
  selectedRun: ConsoleRun | null;
};

export function RunLogPanel({ selectedRun }: RunLogPanelProps) {
  const logsQuery = useRunLogs(selectedRun?.id ?? null);

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

function InfoRow(props: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{props.label}</div>
      <div className="mt-2 break-all text-sm font-medium text-slate-100">{props.value}</div>
    </div>
  );
}
