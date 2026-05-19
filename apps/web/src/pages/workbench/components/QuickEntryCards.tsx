import { DetailModal } from "./DetailModal";

/* ─── Exported modal content components ─── */

export function BattlePlanContent({
  overviewData,
  selectedProjectId,
}: {
  overviewData: { total_tasks?: number; completed_tasks?: number } | undefined;
  selectedProjectId: string;
}) {
  const total = overviewData?.total_tasks ?? 0;
  const completed = overviewData?.completed_tasks ?? 0;
  const progress = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="space-y-4 text-sm text-zinc-300">
      <div>
        <span className="text-zinc-500">项目范围：</span>
        {selectedProjectId === "all" ? "全部项目" : selectedProjectId}
      </div>
      <div>
        <span className="text-zinc-500">任务总数：</span>
        {total}
      </div>
      <div>
        <span className="text-zinc-500">完成进度：</span>
        {completed} / {total}（{progress}%）
      </div>
      <div className="w-full rounded-full bg-[#333333] h-2">
        <div
          className="h-2 rounded-full bg-zinc-500 transition-all"
          style={{ width: `${progress}%` }}
        />
      </div>
      <p className="text-xs text-zinc-600">
        完整作战计划需接入 AI 项目主管后端能力后展示。当前仅展示基于已有控制台数据的进度摘要。
      </p>
    </div>
  );
}

export function AgentMovementContent({
  agentSummary,
  totalTasks,
}: {
  agentSummary: { role: string; count: number }[];
  totalTasks: number;
}) {
  if (agentSummary.length === 0) {
    return <p className="text-sm text-zinc-500">当前无 Agent 分配记录。任务尚未绑定角色。</p>;
  }

  return (
    <div className="space-y-3 text-sm text-zinc-300">
      <p className="text-xs text-zinc-500">
        基于当前 {totalTasks} 个任务的角色分配情况：
      </p>
      <ul className="space-y-2">
        {agentSummary.map((a) => (
          <li key={a.role} className="flex items-center justify-between rounded border border-[#333333] px-3 py-2">
            <span className="text-zinc-200">{a.role || "未分配角色"}</span>
            <span className="text-xs text-zinc-500">{a.count} 个任务</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-zinc-600">
        完整 Agent 动向与实时状态需接入 AI 项目主管调度后端后展示。
      </p>
    </div>
  );
}

export function ProjectFlowContent({
  onNavigateToProjects,
  onNavigateToTasks,
  onNavigateToRuns,
}: {
  onNavigateToProjects: () => void;
  onNavigateToTasks: () => void;
  onNavigateToRuns: () => void;
}) {
  return (
    <div className="space-y-3 text-sm text-zinc-300">
      <p className="text-xs text-zinc-500">
        AI-Dev-Orchestrator 端到端闭环流程：
      </p>
      <ol className="space-y-2 list-decimal list-inside text-zinc-400">
        <li>用户提出目标</li>
        <li>AI 项目主管澄清范围</li>
        <li>生成作战计划与角色方案</li>
        <li>用户确认计划</li>
        <li>创建任务队列</li>
        <li>AI 项目主管调度 Agent 执行任务</li>
        <li>Agent 执行任务并产生运行记录</li>
        <li>运行观测：状态 / 摘要 / 日志 / 证据</li>
        <li>失败处理：重试 / 返工 / 人工介入 / 重规划</li>
        <li>成功任务生成交付物草案</li>
        <li>成果中心审批 Gate</li>
        <li>审批通过沉淀角色 / Skill / 成本台账</li>
        <li>项目目标完成</li>
      </ol>
      <p className="text-xs text-zinc-600">
        详细流程图请参阅 docs/product/ai-project-director/closure-flow-20260518.md
      </p>
      <div className="flex flex-wrap gap-2 border-t border-[#333333] pt-3">
        <button
          type="button"
          onClick={onNavigateToProjects}
          className="rounded border border-[#444444] px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-400 hover:bg-[#2f2f2f]"
        >
          查看项目页
        </button>
        <button
          type="button"
          onClick={onNavigateToTasks}
          className="rounded border border-[#444444] px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-400 hover:bg-[#2f2f2f]"
        >
          查看任务队列
        </button>
        <button
          type="button"
          onClick={onNavigateToRuns}
          className="rounded border border-[#444444] px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-400 hover:bg-[#2f2f2f]"
        >
          查看运行观测
        </button>
      </div>
    </div>
  );
}

export function PendingConfirmationsContent({
  tasks,
  onNavigateToTask,
  onNavigateToTasks,
}: {
  tasks: { id: string; title: string; status: string; project_id?: string | null }[];
  onNavigateToTask: (taskId: string, projectId?: string | null) => void;
  onNavigateToTasks: () => void;
}) {
  if (tasks.length === 0) {
    return (
      <div className="space-y-3 text-sm text-zinc-300">
        <p className="text-sm text-zinc-500">当前无待确认事项。</p>
        <button
          type="button"
          onClick={onNavigateToTasks}
          className="rounded border border-[#444444] px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-400 hover:bg-[#2f2f2f]"
        >
          前往任务页
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3 text-sm text-zinc-300">
      <p className="text-xs text-zinc-500">
        以下 {tasks.length} 个任务需要人工确认：
      </p>
      <ul className="space-y-2">
        {tasks.map((t) => (
          <li
            key={t.id}
            className="flex items-center justify-between rounded border border-[#333333] px-3 py-2"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-zinc-200">{t.title}</p>
              <p className="text-xs text-zinc-500">ID: {t.id.slice(0, 8)}...</p>
            </div>
            <button
              type="button"
              disabled
              className="ml-3 shrink-0 rounded border border-[#333333] px-2.5 py-1 text-xs text-zinc-600 cursor-not-allowed"
            >
              确认
            </button>
          </li>
        ))}
      </ul>
      <p className="text-xs text-zinc-600">
        确认 / 驳回操作待接入确认流转接口。当前请前往任务页手动处理。
      </p>
      <div className="flex flex-wrap gap-2 border-t border-[#333333] pt-3">
        <button
          type="button"
          onClick={() => onNavigateToTask(tasks[0].id, tasks[0].project_id)}
          className="rounded border border-[#444444] px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-400 hover:bg-[#2f2f2f]"
        >
          查看第一个待确认任务
        </button>
        <button
          type="button"
          onClick={onNavigateToTasks}
          className="rounded border border-[#444444] px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-400 hover:bg-[#2f2f2f]"
        >
          前往任务页
        </button>
      </div>
    </div>
  );
}

/* ─── Exported helpers ─── */

export function buildAgentSummary(
  tasks: { owner_role_code?: string | null }[],
): { role: string; count: number }[] {
  const map = new Map<string, number>();
  for (const t of tasks) {
    const role = t.owner_role_code || "未分配角色";
    map.set(role, (map.get(role) ?? 0) + 1);
  }
  return Array.from(map.entries())
    .map(([role, count]) => ({ role, count }))
    .sort((a, b) => b.count - a.count);
}

/* ─── Entry modals container (used by WorkbenchRightRail) ─── */

export type EntryModalKind = "battleplan" | "agents" | "flow" | "confirmations";

type EntryModalsProps = {
  modalKind: EntryModalKind | null;
  onClose: () => void;
  overviewData: { total_tasks?: number; completed_tasks?: number; tasks?: { id: string; title: string; status: string; project_id?: string | null; owner_role_code?: string | null }[]; blocked_tasks?: number; waiting_human_tasks?: number } | undefined;
  selectedProjectId: string;
  onNavigateToTask: (taskId: string, projectId?: string | null) => void;
  onNavigateToTasks: () => void;
  onNavigateToProjects: () => void;
  onNavigateToRuns: () => void;
};

export function EntryModals({
  modalKind,
  onClose,
  overviewData,
  selectedProjectId,
  onNavigateToTask,
  onNavigateToTasks,
  onNavigateToProjects,
  onNavigateToRuns,
}: EntryModalsProps) {
  const tasks = overviewData?.tasks ?? [];
  const agentSummary = buildAgentSummary(tasks);
  const waitingHumanTasks = tasks.filter((t) => t.status === "waiting_human");

  return (
    <>
      <DetailModal open={modalKind === "battleplan"} onClose={onClose} title="作战计划">
        <BattlePlanContent overviewData={overviewData} selectedProjectId={selectedProjectId} />
      </DetailModal>

      <DetailModal open={modalKind === "agents"} onClose={onClose} title="Agent 动向">
        <AgentMovementContent agentSummary={agentSummary} totalTasks={tasks.length} />
      </DetailModal>

      <DetailModal open={modalKind === "flow"} onClose={onClose} title="项目流程">
        <ProjectFlowContent
          onNavigateToProjects={onNavigateToProjects}
          onNavigateToTasks={onNavigateToTasks}
          onNavigateToRuns={onNavigateToRuns}
        />
      </DetailModal>

      <DetailModal open={modalKind === "confirmations"} onClose={onClose} title="待确认事项">
        <PendingConfirmationsContent
          tasks={waitingHumanTasks}
          onNavigateToTask={onNavigateToTask}
          onNavigateToTasks={onNavigateToTasks}
        />
      </DetailModal>
    </>
  );
}
