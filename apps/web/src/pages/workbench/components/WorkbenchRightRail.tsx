import { useState } from "react";
import type { ConsoleOverview } from "../../../features/console/types";
import { EntryModals, type EntryModalKind } from "./QuickEntryCards";

type WorkbenchRightRailProps = {
  overviewData: ConsoleOverview | undefined;
  overviewIsInitialLoading: boolean;
  refreshNotice: string | null;
  selectedProjectId: string;
  onRefresh: () => void;
  onNavigateToTasks: () => void;
  onNavigateToTask: (taskId: string, projectId?: string | null) => void;
  onNavigateToProjects: () => void;
  onNavigateToRuns: () => void;
  isRunWorkerOncePending: boolean;
  onRunWorkerOnce: () => void;
  workerOnceData: unknown;
  workerOnceIsError: boolean;
  workerOnceErrorMessage: string | null;
};

export function WorkbenchRightRail({
  overviewData,
  overviewIsInitialLoading,
  refreshNotice,
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

  const blockedTasks = tasks.filter((task) => task.status === "blocked").slice(0, 3);
  const waitingHumanTasks = tasks
    .filter((task) => task.status === "waiting_human")
    .slice(0, 3);

  let suggestion = "";
  if (blocked > 0) {
    suggestion = `${blocked} 个阻塞，建议查看阻塞处理。`;
  } else if (failed > 0) {
    suggestion = `${failed} 个失败，建议评估是否需要重试。`;
  } else if (waitingHuman > 0) {
    suggestion = `${waitingHuman} 个待确认，请在待确认中处理。`;
  } else if (total === 0) {
    suggestion = "尚无任务，可通过 AI 项目主管对话提出目标。";
  } else if (running > 0) {
    suggestion = `${running} 个任务执行中，系统运行正常。`;
  } else {
    suggestion = "暂无需要处理的事项。";
  }

  const handleBlockingClick = () => {
    if (blockedTasks.length > 0) {
      const task = blockedTasks[0];
      onNavigateToTask(task.id, task.project_id);
      return;
    }
    onNavigateToTasks();
  };

  return (
    <>
      <aside
        data-testid="workbench-right-rail"
        className="space-y-4 rounded-lg border border-[#333333] bg-[#1a1a1a] p-4"
      >
        <section>
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500">
              项目态势
            </h3>
            <button
              type="button"
              onClick={onRefresh}
              className="rounded border border-[#333333] px-2 py-0.5 text-xs text-zinc-500 transition hover:border-zinc-500 hover:text-zinc-300"
            >
              刷新
            </button>
          </div>

          <div
            className="mb-2 min-h-[1.25rem] text-[11px] leading-5 text-zinc-500"
            aria-live="polite"
          >
            {refreshNotice ?? <span className="invisible">已刷新最新状态</span>}
          </div>

          {overviewIsInitialLoading ? (
            <div className="grid grid-cols-3 gap-1.5" data-testid="right-rail-initial-loading">
              {Array.from({ length: 6 }).map((_, index) => (
                <div
                  key={index}
                  className="h-[56px] animate-pulse rounded border border-[#333333] bg-[#171717]"
                />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-1.5" data-testid="right-rail-stable-stats">
              <CompactStat label="总计" value={total} />
              <CompactStat label="运行中" value={running} />
              <CompactStat label="阻塞" value={blocked} />
              <CompactStat label="失败" value={failed} />
              <CompactStat label="待确认" value={waitingHuman} />
              <CompactStat label="已完成" value={completed} />
            </div>
          )}
        </section>

        {(blockedTasks.length > 0 || waitingHumanTasks.length > 0) && (
          <section className="border-t border-[#333333] pt-4">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500">
              待处理
            </h3>
            <ul className="space-y-1.5">
              {blockedTasks.map((task) => (
                <li key={task.id}>
                  <button
                    type="button"
                    onClick={() => onNavigateToTask(task.id, task.project_id)}
                    className="w-full rounded border border-[#333333] px-2.5 py-1.5 text-left text-xs transition hover:border-zinc-500 hover:bg-[#222222]"
                  >
                    <span className="block truncate text-zinc-300">{task.title}</span>
                    <span className="text-zinc-600">阻塞 · 点击查看详情</span>
                  </button>
                </li>
              ))}
              {waitingHumanTasks.map((task) => (
                <li key={task.id}>
                  <button
                    type="button"
                    onClick={() => onNavigateToTask(task.id, task.project_id)}
                    className="w-full rounded border border-[#333333] px-2.5 py-1.5 text-left text-xs transition hover:border-zinc-500 hover:bg-[#222222]"
                  >
                    <span className="block truncate text-zinc-300">{task.title}</span>
                    <span className="text-zinc-600">待确认 · 点击查看详情</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="border-t border-[#333333] pt-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500">
            执行控制
          </h3>
          <div className="space-y-2">
            <button
              type="button"
              data-testid="right-rail-run-worker-once"
              onClick={onRunWorkerOnce}
              disabled={isRunWorkerOncePending}
              className="w-full rounded border border-[#333333] px-3 py-1.5 text-xs text-zinc-300 transition hover:border-zinc-500 hover:bg-[#222222] disabled:cursor-not-allowed disabled:text-zinc-600 disabled:hover:bg-transparent"
            >
              {isRunWorkerOncePending ? "启动中..." : "启动一次执行"}
            </button>

            {workerOnceData != null && !workerOnceIsError && (
              <p className="text-xs text-zinc-500">
                已启动一次执行，请查看任务页或运行页了解进展。
              </p>
            )}
            {workerOnceIsError && workerOnceErrorMessage != null && (
              <p className="text-xs text-zinc-500">启动失败：{workerOnceErrorMessage}</p>
            )}
          </div>
        </section>

        <section className="border-t border-[#333333] pt-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.15em] text-zinc-500">
            工具入口
          </h3>
          <div className="space-y-1.5">
            <CompactEntryButton title="作战计划" onClick={() => setModalKind("battleplan")} />
            <CompactEntryButton title="Agent 动向" onClick={() => setModalKind("agents")} />
            <CompactEntryButton title="项目流程" onClick={() => setModalKind("flow")} />
            <CompactEntryButton
              title="待确认"
              badge={waitingHuman > 0 ? waitingHuman : undefined}
              onClick={() => setModalKind("confirmations")}
            />
            <CompactEntryButton
              title="阻塞处理"
              badge={blocked > 0 ? blocked : undefined}
              onClick={handleBlockingClick}
            />
          </div>
        </section>

        <section className="border-t border-[#333333] pt-3">
          <p className="text-xs text-zinc-600">
            <span className="text-zinc-500">规则建议</span>
            {" · "}待接入真实 AI 主管建议
          </p>
          <p className="mt-1 text-xs leading-relaxed text-zinc-400">{suggestion}</p>
        </section>
      </aside>

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

function CompactStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-[#333333] px-1.5 py-1 text-center">
      <div className="text-[10px] text-zinc-500">{label}</div>
      <div className="text-sm font-medium text-zinc-300">{value}</div>
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
      className="w-full rounded border border-[#333333] px-3 py-1.5 text-left text-xs text-zinc-300 transition hover:border-zinc-500 hover:bg-[#222222]"
    >
      <span>{title}</span>
      {badge != null && badge > 0 ? <span className="ml-2 text-zinc-500">({badge})</span> : null}
    </button>
  );
}
