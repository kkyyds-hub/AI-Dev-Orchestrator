import type { ConsoleTask } from "../../../features/console/types";

type SituationPanelProps = {
  tasks: ConsoleTask[];
  onNavigateToRun: (runId: string, taskId: string, projectId: string | null) => void;
};

export function TaskExecutionSituationPanel({
  tasks,
  onNavigateToRun,
}: SituationPanelProps) {
  const agentLoad = buildAgentLoad(tasks);
  const blockedTasks = tasks.filter((t) => t.status === "blocked").slice(0, 3);
  const recentRuns = tasks
    .filter((t) => t.latest_run?.id)
    .sort((a, b) => {
      const aTime = a.latest_run?.created_at ?? "";
      const bTime = b.latest_run?.created_at ?? "";
      return bTime.localeCompare(aTime);
    })
    .slice(0, 3);
  const ruleSuggestion = buildRuleSuggestion(tasks);

  return (
    <aside className="rounded-lg border border-[#333333] bg-[#1a1a1a] p-5 flex flex-col gap-5">
      {/* Agent 负载 */}
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500 mb-3">
          Agent 负载
        </h3>
        {agentLoad.length === 0 ? (
          <p className="text-xs text-zinc-600">暂无 Agent 分配</p>
        ) : (
          <ul className="space-y-2">
            {agentLoad.map((a) => (
              <li
                key={a.role}
                className="flex items-center justify-between rounded border border-[#333333] px-3 py-2"
              >
                <div className="min-w-0">
                  <span className="text-sm text-zinc-200 block truncate">
                    {a.role || "未分配"}
                  </span>
                  <span className="text-[11px] text-zinc-500 mt-0.5 block">
                    {a.running > 0 && `执行中 ${a.running}`}
                    {a.running > 0 && a.blocked > 0 && " · "}
                    {a.blocked > 0 && `阻塞 ${a.blocked}`}
                    {(a.running === 0 && a.blocked === 0) && `${a.count} 个任务`}
                  </span>
                </div>
                <span className="text-xs text-zinc-500 shrink-0 ml-3">{a.count}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 阻塞原因 */}
      <section className="border-t border-[#333333] pt-5">
        <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500 mb-3">
          阻塞原因
        </h3>
        {blockedTasks.length === 0 ? (
          <p className="text-xs text-zinc-600">当前无阻塞</p>
        ) : (
          <ul className="space-y-2">
            {blockedTasks.map((t) => (
              <li key={t.id} className="rounded border border-[#333333] px-3 py-2">
                <p className="text-sm text-zinc-300 truncate">{t.title}</p>
                <p className="text-[11px] text-zinc-600 mt-0.5 truncate">
                  {t.paused_reason ? t.paused_reason.slice(0, 60) : "阻塞原因待确认"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 最近运行 */}
      <section className="border-t border-[#333333] pt-5">
        <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500 mb-3">
          最近运行
        </h3>
        {recentRuns.length === 0 ? (
          <p className="text-xs text-zinc-600">暂无运行记录</p>
        ) : (
          <ul className="space-y-2">
            {recentRuns.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() =>
                    onNavigateToRun(t.latest_run!.id, t.id, t.project_id)
                  }
                  className="w-full text-left rounded border border-[#444444] px-3 py-2 transition hover:border-zinc-400 hover:bg-[#222222]"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-zinc-300 truncate min-w-0">
                      {t.title}
                    </span>
                    <span className="text-[11px] text-zinc-500 shrink-0 ml-2">
                      {t.latest_run?.status ?? "未知"}
                    </span>
                  </div>
                  {t.latest_run?.result_summary && (
                    <p className="text-[11px] text-zinc-600 mt-0.5 truncate">
                      {t.latest_run.result_summary.slice(0, 72)}
                    </p>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 规则建议 — 固定在底部 */}
      <section className="border-t border-[#333333] pt-4 mt-auto">
        <p className="text-[11px] text-zinc-500">
          规则建议 · 待接入 AI 主管建议
        </p>
        <p className="mt-1 text-xs text-zinc-400">
          {ruleSuggestion}
        </p>
      </section>
    </aside>
  );
}

/* ─── helpers ─── */

type AgentLoadEntry = {
  role: string;
  count: number;
  running: number;
  blocked: number;
};

function buildAgentLoad(tasks: ConsoleTask[]): AgentLoadEntry[] {
  const map = new Map<string, { count: number; running: number; blocked: number }>();
  for (const t of tasks) {
    const role = t.owner_role_code || "未分配";
    const entry = map.get(role) ?? { count: 0, running: 0, blocked: 0 };
    entry.count++;
    if (t.status === "running") entry.running++;
    if (t.status === "blocked") entry.blocked++;
    map.set(role, entry);
  }
  return Array.from(map.entries())
    .map(([role, e]) => ({ role, ...e }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5);
}

function buildRuleSuggestion(tasks: ConsoleTask[]): string {
  const blocked = tasks.filter((t) => t.status === "blocked").length;
  const failed = tasks.filter((t) => t.status === "failed").length;
  const waitingHuman = tasks.filter((t) => t.status === "waiting_human").length;
  const running = tasks.filter((t) => t.status === "running").length;

  if (blocked > 0) return `${blocked} 个任务阻塞，建议优先排查。`;
  if (failed > 0) return `${failed} 个任务失败，建议评估是否重试。`;
  if (waitingHuman > 0) return `${waitingHuman} 个任务待人工确认。`;
  if (running > 0) return `${running} 个任务执行中，运行正常。`;
  if (tasks.length === 0) return "暂无任务。";
  return "暂无需要处理的事项。";
}
