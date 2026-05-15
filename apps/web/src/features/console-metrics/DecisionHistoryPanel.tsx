import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime } from "../../lib/format";
import { mapRunStatusTone } from "../../lib/status";
import type { TaskDetailSurfaceVariant } from "../task-detail/components/TaskDetailField";
import type { DecisionHistoryItem } from "./types";

type DecisionHistoryPanelProps = {
  taskId: string | null;
  history: DecisionHistoryItem[];
  isLoading: boolean;
  errorMessage?: string | null;
  selectedRunId?: string | null;
  surfaceVariant?: TaskDetailSurfaceVariant;
  onSelectRun?: (runId: string) => void;
};

export function DecisionHistoryPanel({
  taskId,
  history,
  isLoading,
  errorMessage,
  selectedRunId,
  surfaceVariant,
  onSelectRun,
}: DecisionHistoryPanelProps) {
  const isLine = surfaceVariant === "line";

  return (
    <section className={isLine ? "border-b border-[#333333] pb-5" : "rounded-xl border border-[#333333] bg-transparent p-4"}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className={`text-base font-semibold ${isLine ? "text-zinc-100" : "text-zinc-100"}`}>决策历史</h3>
          <p className={`mt-1 text-sm leading-6 ${isLine ? "text-zinc-500" : "text-zinc-400"}`}>
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
        <div className={isLine ? "mt-4 border-y border-dashed border-[#333333] py-6 text-sm text-zinc-500" : "mt-4 rounded-xl border border-dashed border-[#333333] bg-transparent p-4 text-sm text-zinc-400"}>
          当前还没有选中的任务。
        </div>
      ) : isLoading ? (
        <div className={isLine ? "mt-4 border-y border-[#333333] py-4 text-sm text-zinc-500" : "mt-4 rounded-xl border border-[#333333] bg-transparent p-4 text-sm text-zinc-400"}>
          正在加载决策历史…
        </div>
      ) : errorMessage ? (
        <div className={isLine ? "mt-4 border-l border-rose-700/70 pl-4 text-sm leading-6 text-rose-200" : "mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100"}>
          无法加载决策历史：{errorMessage}
        </div>
      ) : history.length === 0 ? (
        <div className={isLine ? "mt-4 border-y border-dashed border-[#333333] py-6 text-sm text-zinc-500" : "mt-4 rounded-xl border border-dashed border-[#333333] bg-transparent p-4 text-sm text-zinc-400"}>
          该任务还没有运行历史。
        </div>
      ) : (
        <div className={isLine ? "mt-4 max-h-[32rem] divide-y divide-[#333333] overflow-y-auto border-y border-[#333333]" : "mt-4 max-h-[32rem] space-y-3 overflow-y-auto pr-1"}>
          {history.map((item) => (
            <button
              key={item.run_id}
              type="button"
              className={
                isLine
                  ? `w-full px-3 py-4 text-left transition-colors ${
                      item.run_id === selectedRunId
                        ? "bg-[#2b2b2b]"
                        : "bg-transparent hover:bg-[#252525]"
                    }`
                  : `w-full rounded-xl border p-4 text-left transition-colors ${
                      item.run_id === selectedRunId
                        ? "border-[#3a3a3a] bg-transparent"
                        : "border-[#333333] bg-transparent hover:border-[#333333] hover:bg-transparent"
                    }`
              }
              onClick={() => onSelectRun?.(item.run_id)}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className={`text-sm font-medium ${isLine ? "text-zinc-100" : "text-zinc-100"}`}>{item.headline}</div>
                  <div className={`mt-1 text-xs ${isLine ? "text-zinc-600" : "text-zinc-500"}`}>
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
                      className={isLine ? "border-l border-[#333333] px-2 py-1 text-xs text-zinc-400" : "rounded-lg bg-transparent/70 px-2 py-1 text-xs text-zinc-400"}
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
    </section>
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
