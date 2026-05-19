import type { ConsoleTask } from "../../../features/console/types";

type SituationPanelProps = {
  tasks: ConsoleTask[];
};

export function TaskExecutionSituationPanel({ tasks }: SituationPanelProps) {
  /* Agent load */
  const agentLoad = buildAgentLoad(tasks);

  /* Blocked tasks */
  const blockedTasks = tasks.filter((t) => t.status === "blocked").slice(0, 3);

  /* Recent runs */
  const recentRuns = tasks
    .filter((t) => t.latest_run?.id)
    .sort((a, b) => {
      const aTime = a.latest_run?.created_at ?? "";
      const bTime = b.latest_run?.created_at ?? "";
      return bTime.localeCompare(aTime);
    })
    .slice(0, 3);

  /* Rule suggestion */
  const ruleSuggestion = buildRuleSuggestion(tasks);

  return (
    <aside className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-4 space-y-4">
      {/* Agent load */}
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500 mb-2">
          Agent 负载
        </h3>
        {agentLoad.length === 0 ? (
          <p className="text-xs text-zinc-600">暂无 Agent 分配</p>
        ) : (
          <ul className="space-y-1.5">
            {agentLoad.map((a) => (
              <li
                key={a.role}
                className="flex items-center justify-between text-xs rounded border border-[#333333] px-2.5 py-1.5"
              >
                <span className="text-zinc-300">{a.role || "未分配"}</span>
                <span className="text-zinc-500">{a.count} 个任务</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Blocking reasons */}
      <section className="border-t border-[#333333] pt-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500 mb-2">
          阻塞原因
        </h3>
        {blockedTasks.length === 0 ? (
          <p className="text-xs text-zinc-600">当前无阻塞任务</p>
        ) : (
          <ul className="space-y-1.5">
            {blockedTasks.map((t) => (
              <li
                key={t.id}
                className="rounded border border-[#333333] px-2.5 py-1.5 text-xs"
              >
                <p className="text-zinc-300 truncate">{t.title}</p>
                <p className="text-zinc-600 mt-0.5">
                  {t.paused_reason ? t.paused_reason.slice(0, 60) : "阻塞原因待确认"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Recent runs */}
      <section className="border-t border-[#333333] pt-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500 mb-2">
          最近运行
        </h3>
        {recentRuns.length === 0 ? (
          <p className="text-xs text-zinc-600">暂无运行记录</p>
        ) : (
          <ul className="space-y-1.5">
            {recentRuns.map((t) => (
              <li
                key={t.id}
                className="rounded border border-[#333333] px-2.5 py-1.5 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="text-zinc-300 truncate">{t.title}</span>
                  <span className="text-zinc-500 shrink-0 ml-2">
                    {t.latest_run?.status ?? "未知"}
                  </span>
                </div>
                {t.latest_run?.result_summary && (
                  <p className="text-zinc-600 mt-0.5 truncate">
                    {t.latest_run.result_summary.slice(0, 80)}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Rule suggestion */}
      <section className="border-t border-[#333333] pt-3">
        <p className="text-xs text-zinc-500">
          规则建议 · 待接入 AI 主管建议
        </p>
        <p className="mt-1 text-xs leading-relaxed text-zinc-400">
          {ruleSuggestion}
        </p>
      </section>
    </aside>
  );
}

/* ─── helpers ─── */

function buildAgentLoad(
  tasks: ConsoleTask[],
): { role: string; count: number }[] {
  const map = new Map<string, number>();
  for (const t of tasks) {
    const role = t.owner_role_code || "未分配";
    map.set(role, (map.get(role) ?? 0) + 1);
  }
  return Array.from(map.entries())
    .map(([role, count]) => ({ role, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5);
}

function buildRuleSuggestion(tasks: ConsoleTask[]): string {
  const blocked = tasks.filter((t) => t.status === "blocked").length;
  const failed = tasks.filter((t) => t.status === "failed").length;
  const waitingHuman = tasks.filter((t) => t.status === "waiting_human").length;
  const running = tasks.filter((t) => t.status === "running").length;

  if (blocked > 0) return `${blocked} 个任务阻塞，建议优先查看阻塞原因。`;
  if (failed > 0) return `${failed} 个任务失败，建议评估是否需要重试。`;
  if (waitingHuman > 0) return `${waitingHuman} 个任务待人工确认。`;
  if (running > 0) return `${running} 个任务执行中，系统运行正常。`;
  if (tasks.length === 0) return "暂无任务。";
  return "暂无需要处理的事项。";
}
