import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { mapRunStatusTone } from "../../lib/status";
import type { DecisionHistoryItem } from "./types";

type DecisionHistoryPanelProps = {
  taskId: string | null;
  history: DecisionHistoryItem[];
  isLoading: boolean;
  errorMessage?: string | null;
  selectedRunId?: string | null;
  onSelectRun?: (runId: string) => void;
};

export function DecisionHistoryPanel({
  taskId,
  history,
  isLoading,
  errorMessage,
  selectedRunId,
  onSelectRun,
}: DecisionHistoryPanelProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-50">决策历史</h3>
          <p className="mt-1 text-sm text-slate-400">
            {taskId
              ? "查看该任务所有运行的决策路径摘要。"
              : "先选择一个任务，再查看其决策历史。"}
          </p>
        </div>
        {history.length > 0 ? (
          <StatusBadge label={`${history.length} 次运行`} tone="info" />
        ) : null}
      </div>

      {!taskId ? (
        <div className="mt-4 rounded-xl border border-dashed border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-400">
          当前还没有选中的任务。
        </div>
      ) : isLoading ? (
        <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-300">
          正在加载决策历史…
        </div>
      ) : errorMessage ? (
        <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          无法加载决策历史：{errorMessage}
        </div>
      ) : history.length === 0 ? (
        <div className="mt-4 rounded-xl border border-dashed border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-400">
          该任务还没有运行历史。
        </div>
      ) : (
        <div className="mt-4 max-h-[32rem] space-y-3 overflow-y-auto pr-1">
          {history.map((item) => (
            <button
              key={item.run_id}
              type="button"
              className={`w-full rounded-xl border p-4 text-left transition-colors ${
                item.run_id === selectedRunId
                  ? "border-cyan-500/40 bg-cyan-500/5"
                  : "border-slate-800 bg-slate-900/70 hover:border-slate-700 hover:bg-slate-900"
              }`}
              onClick={() => onSelectRun?.(item.run_id)}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="text-sm font-medium text-slate-100">{item.headline}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {formatDateTime(item.created_at)}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge label={item.status} tone={mapRunStatusTone(item.status)} />
                  {item.failure_category ? (
                    <StatusBadge label={item.failure_category} tone="warning" />
                  ) : null}
                </div>
              </div>

              {item.stages.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {item.stages.map((stage, index) => (
                    <span
                      key={`${stage}-${index}`}
                      className="rounded-lg bg-slate-800/70 px-2 py-1 text-xs text-slate-300"
                    >
                      {formatStageLabel(stage)}
                    </span>
                  ))}
                </div>
              ) : null}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function formatStageLabel(stage: string): string {
  const labels: Record<string, string> = {
    routing: "路由",
    claim: "领取",
    context: "上下文",
    guard: "守卫",
    execution: "执行",
    verification: "验证",
    cost: "成本",
    parallel: "并行",
    finalize: "收口",
    recovery: "恢复",
  };
  return labels[stage] || stage;
}
