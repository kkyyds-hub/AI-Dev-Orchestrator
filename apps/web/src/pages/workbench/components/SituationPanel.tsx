import type { ConsoleOverview } from "../../../features/console/types";

type SituationPanelProps = {
  overviewData: ConsoleOverview | undefined;
  overviewIsLoading: boolean;
  onRefresh: () => void;
};

export function SituationPanel({
  overviewData,
  overviewIsLoading,
  onRefresh,
}: SituationPanelProps) {
  const total = overviewData?.total_tasks ?? 0;
  const running = overviewData?.running_tasks ?? 0;
  const blocked = overviewData?.blocked_tasks ?? 0;
  const failed = overviewData?.failed_tasks ?? 0;
  const completed = overviewData?.completed_tasks ?? 0;
  const waitingHuman = overviewData?.waiting_human_tasks ?? 0;
  const cost = overviewData?.total_estimated_cost ?? 0;

  const suggestions: string[] = [];

  if (blocked > 0) {
    suggestions.push(`${blocked} 个任务处于阻塞状态，建议进入"阻塞处理"查看详情并决定下一步动作。`);
  }
  if (failed > 0) {
    suggestions.push(`${failed} 个任务执行失败，可前往任务页评估是否需要重试或人工介入。`);
  }
  if (waitingHuman > 0) {
    suggestions.push(`${waitingHuman} 个任务等待人工确认，请在"待确认"中处理。`);
  }
  if (blocked === 0 && failed === 0 && waitingHuman === 0 && running > 0) {
    suggestions.push(`当前 ${running} 个任务正在执行中，系统运行正常。`);
  }
  if (total === 0) {
    suggestions.push("当前尚无任务。请通过 AI 项目主管对话入口提出目标，生成首批作战计划。");
  }

  return (
    <aside
      data-testid="situation-panel"
      className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-5"
    >
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-zinc-400">
          项目态势
        </h3>
        <button
          type="button"
          onClick={onRefresh}
          className="rounded-md border border-[#333333] px-2.5 py-1 text-xs text-zinc-400 transition hover:border-zinc-500 hover:text-zinc-200"
        >
          刷新
        </button>
      </div>

      {overviewIsLoading ? (
        <p className="text-sm text-zinc-600">加载中…</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2 mb-4">
            <StatBadge label="总计" value={total} />
            <StatBadge label="运行中" value={running} tone="info" />
            <StatBadge label="阻塞" value={blocked} tone="warning" />
            <StatBadge label="失败" value={failed} tone="danger" />
            <StatBadge label="待确认" value={waitingHuman} tone="warning" />
            <StatBadge label="已完成" value={completed} tone="success" />
          </div>

          {cost > 0 && (
            <p className="mb-4 text-xs text-zinc-500">
              预估费用：${cost.toFixed(4)}
            </p>
          )}
        </>
      )}

      <div className="border-t border-[#333333] pt-4">
        <h4 className="mb-3 text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500">
          AI 主管当前建议
        </h4>
        {suggestions.length > 0 ? (
          <ul className="space-y-2">
            {suggestions.map((s, i) => (
              <li key={i} className="text-sm leading-relaxed text-zinc-300">
                {s}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-zinc-600">暂无建议</p>
        )}
      </div>
    </aside>
  );
}

function StatBadge({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "info" | "success" | "warning" | "danger";
}) {
  const toneMap: Record<string, string> = {
    info: "border-blue-800 text-blue-300",
    success: "border-green-800 text-green-300",
    warning: "border-yellow-800 text-yellow-300",
    danger: "border-red-800 text-red-300",
    default: "border-[#333333] text-zinc-300",
  };

  const borderColor = tone ? (toneMap[tone] ?? toneMap.default) : toneMap.default;

  return (
    <div className={`rounded-md border px-2.5 py-1.5 text-center ${borderColor}`}>
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
