import { useState } from "react";
import type { ConsoleOverview } from "../../../features/console/types";
import { EntryModals, type EntryModalKind } from "./QuickEntryCards";

type WorkbenchRightRailProps = {
  overviewData: ConsoleOverview | undefined;
  overviewIsLoading: boolean;
  selectedProjectId: string;
  onRefresh: () => void;
  onNavigateToTasks: () => void;
  onNavigateToTask: (taskId: string, projectId?: string | null) => void;
  onNavigateToProjects: () => void;
  onNavigateToRuns: () => void;
  /* Worker scheduling */
  isRunWorkerOncePending: boolean;
  onRunWorkerOnce: () => void;
  workerOnceData: unknown;
  workerOnceIsError: boolean;
  workerOnceErrorMessage: string | null;
};

export function WorkbenchRightRail({
  overviewData,
  overviewIsLoading,
  selectedProjectId,
  onRefresh,
  onNavigateToTasks,
  onNavigateToTask,
  onNavigateToProjects,
  onNavigateToRuns,
  isRunWorkerOncePending,
  onRunWorkerOnce,
  workerOnceData,
  workerOnceIsError,
  workerOnceErrorMessage,
}: WorkbenchRightRailProps) {
  const [modalKind, setModalKind] = useState<EntryModalKind | null>(null);
  const closeModal = () => setModalKind(null);

  const total = overviewData?.total_tasks ?? 0;
  const running = overviewData?.running_tasks ?? 0;
  const blocked = overviewData?.blocked_tasks ?? 0;
  const failed = overviewData?.failed_tasks ?? 0;
  const completed = overviewData?.completed_tasks ?? 0;
  const waitingHuman = overviewData?.waiting_human_tasks ?? 0;
  const tasks = overviewData?.tasks ?? [];

  const blockedTasks = tasks.filter((t) => t.status === "blocked").slice(0, 3);
  const waitingHumanTasks = tasks.filter((t) => t.status === "waiting_human").slice(0, 3);

  /* Suggestion */
  let suggestion = "";
  if (blocked > 0) {
    suggestion = `${blocked} 个阻塞任务，建议调阅异常详情并尽快处理。`;
  } else if (failed > 0) {
    suggestion = `${failed} 个任务失败，可对失败节点触发重试。`;
  } else if (waitingHuman > 0) {
    suggestion = `${waitingHuman} 个任务待确认，请查阅确认。`;
  } else if (total === 0) {
    suggestion = "无活动任务。可通过左侧对话框输入目标。";
  } else if (running > 0) {
    suggestion = `${running} 个 Agent 调度执行中，系统无异常红线。`;
  } else {
    suggestion = "当前项目就绪，无阻塞挂起项。";
  }

  const handleBlockingClick = () => {
    if (blockedTasks.length > 0) {
      const task = blockedTasks[0];
      onNavigateToTask(task.id, task.project_id);
    } else {
      onNavigateToTasks();
    }
  };

  const handleConfirmationsClick = () => {
    setModalKind("confirmations");
  };

  return (
    <>
      <aside
        data-testid="workbench-right-rail"
        className="border-l border-zinc-900/50 pl-6 space-y-8 relative overflow-hidden h-full min-h-[calc(100vh-220px)]"
      >
        {/* A. 项目态势 - Architectural Wireframe */}
        <section className="space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-zinc-900/60">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
              项目态势指标
            </h3>
            <button
              type="button"
              onClick={onRefresh}
              className="text-[10px] uppercase font-bold tracking-widest text-zinc-600 hover:text-zinc-200 transition"
            >
              刷新
            </button>
          </div>

          {overviewIsLoading ? (
            <div className="flex items-center justify-center py-6">
              <svg className="animate-spin h-3 w-3 text-zinc-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-y-6 gap-x-2">
              <CompactStat label="总计任务" value={total} />
              <CompactStat label="调度执行" value={running} />
              <CompactStat label="异常阻塞" value={blocked} highlight={blocked > 0} />
              <CompactStat label="执行失败" value={failed} highlight={failed > 0} />
              <CompactStat label="人工确认" value={waitingHuman} highlight={waitingHuman > 0} />
              <CompactStat label="完成交付" value={completed} />
            </div>
          )}
        </section>

        {/* B. 待处理 */}
        {(blockedTasks.length > 0 || waitingHumanTasks.length > 0) && (
          <section className="space-y-3">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-900/60">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-300 animate-pulse" />
                <h3 className="text-[10px] font-bold uppercase tracking-widest text-zinc-300">
                  紧急待办项
                </h3>
              </div>
            </div>
            <ul className="space-y-0.5">
              {blockedTasks.map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => onNavigateToTask(t.id, t.project_id)}
                    className="w-full text-left wireframe-btn py-2.5 pl-3 pr-2 text-xs transition"
                  >
                    <span className="text-zinc-200 font-medium truncate block">{t.title}</span>
                    <span className="text-zinc-500 text-[9px] uppercase tracking-wider mt-1 block">阻塞排查详情</span>
                  </button>
                </li>
              ))}
              {waitingHumanTasks.map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => onNavigateToTask(t.id, t.project_id)}
                    className="w-full text-left wireframe-btn py-2.5 pl-3 pr-2 text-xs transition"
                  >
                    <span className="text-zinc-200 font-medium truncate block">{t.title}</span>
                    <span className="text-zinc-500 text-[9px] uppercase tracking-wider mt-1 block">待确认批复</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* C. 执行控制 */}
        <section className="space-y-4">
          <div className="pb-3 border-b border-zinc-900/60">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
              调度控制台
            </h3>
          </div>
          <div className="space-y-3">
            <button
              type="button"
              data-testid="right-rail-run-worker-once"
              onClick={onRunWorkerOnce}
              disabled={isRunWorkerOncePending}
              className="w-full border border-zinc-800 bg-transparent hover:bg-zinc-900 text-zinc-300 font-medium py-2.5 px-3 text-xs tracking-wider uppercase transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isRunWorkerOncePending ? "调度中..." : "触发单次调度"}
            </button>

            {workerOnceData != null && !workerOnceIsError && (
              <p className="text-[9px] text-zinc-400 uppercase tracking-wider leading-relaxed">
                ✓ 调度执行已就绪
              </p>
            )}
            {workerOnceIsError && workerOnceErrorMessage != null && (
              <p className="text-[9px] text-zinc-500 uppercase tracking-wider leading-relaxed border-l border-zinc-500 pl-2">
                ✗ 异常: {workerOnceErrorMessage}
              </p>
            )}
          </div>
        </section>

        {/* D. 工具入口 */}
        <section className="space-y-3">
          <div className="pb-3 border-b border-zinc-900/60">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">
              分析工具箱
            </h3>
          </div>
          <div className="space-y-0.5">
            <CompactEntryButton
              title="作战计划制图"
              onClick={() => setModalKind("battleplan")}
            />
            <CompactEntryButton
              title="Agent 协作图景"
              onClick={() => setModalKind("agents")}
            />
            <CompactEntryButton
              title="项目交付全景图"
              onClick={() => setModalKind("flow")}
            />
            <CompactEntryButton
              title="待审核批复项"
              badge={waitingHuman > 0 ? waitingHuman : undefined}
              onClick={handleConfirmationsClick}
            />
            <CompactEntryButton
              title="阻塞异常调阅"
              badge={blocked > 0 ? blocked : undefined}
              onClick={handleBlockingClick}
            />
          </div>
        </section>

        {/* E. 诊断建议 */}
        <section className="pt-4 border-t border-zinc-900/60 mt-auto">
          <div className="text-[9px] text-zinc-600 font-bold uppercase tracking-widest mb-2">
            诊断运行建议
          </div>
          <p className="text-[11px] leading-relaxed text-zinc-400 tracking-wide">
            {suggestion}
          </p>
        </section>
      </aside>

      {/* Modals */}
      <EntryModals
        modalKind={modalKind}
        onClose={closeModal}
        overviewData={overviewData}
        selectedProjectId={selectedProjectId}
        onNavigateToTask={onNavigateToTask}
        onNavigateToTasks={onNavigateToTasks}
        onNavigateToProjects={onNavigateToProjects}
        onNavigateToRuns={onNavigateToRuns}
      />
    </>
  );
}

/* ─── Compact sub-components ─── */

function CompactStat({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div className="flex flex-col items-start px-1">
      <div className="text-[9px] uppercase tracking-widest text-zinc-600 font-medium mb-1">{label}</div>
      <div className={`text-xl font-light tracking-tight ${highlight ? "text-zinc-200 font-medium" : "text-zinc-400"}`}>
        {value}
      </div>
    </div>
  );
}

function CompactEntryButton({
  title,
  badge,
  onClick,
}: {
  title: string;
  badge?: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="wireframe-btn w-full text-left py-2.5 pl-3 pr-2 text-[11px] text-zinc-400 flex items-center justify-between group cursor-pointer"
    >
      <span className="font-medium tracking-wide uppercase group-hover:text-zinc-200 transition-colors">{title}</span>
      
      <div className="flex items-center gap-2">
        {badge != null && badge > 0 && (
          <span className="text-[10px] font-bold text-zinc-300">
            [{badge}]
          </span>
        )}
        <span className="text-zinc-700 group-hover:text-zinc-400 transition-transform group-hover:translate-x-0.5">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
          </svg>
        </span>
      </div>
    </button>
  );
}

