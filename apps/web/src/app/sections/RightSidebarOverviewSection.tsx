import { useEffect } from "react";

import type { ConsoleBudget, ConsoleTask } from "../../features/console/types";
import type { StreamConnectionStatus } from "../../features/events/types";
import { TaskDetailPanel } from "../../features/task-detail/TaskDetailPanel";

type RightSidebarOverviewSectionProps = {
  isOpen: boolean;
  onClose: () => void;
  requestedRunId: string | null;
  selectedTask: ConsoleTask | null;
  budget: ConsoleBudget | null;
  realtimeStatus: StreamConnectionStatus;
  onNavigateToRun?: (runId: string, taskId: string) => void;
  onNavigateToProjectDrilldown: (detail: {
    source: "home_latest_run" | "home_manual_run";
    taskId: string;
    runId?: string | null;
  }) => void;
  onNavigateToDeliverable: (input: { projectId: string; deliverableId: string }) => void;
};

export function RightSidebarOverviewSection(props: RightSidebarOverviewSectionProps) {
  const { isOpen, onClose } = props;

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      data-testid="home-right-sidebar-overview-section"
      className="fixed inset-0 z-50 flex justify-end bg-slate-950/70 p-3 backdrop-blur-sm sm:p-5"
      role="dialog"
      aria-modal="true"
      aria-labelledby="workbench-task-detail-drawer-title"
      onClick={props.onClose}
    >
      <div
        className="flex h-full w-full max-w-5xl min-w-0 flex-col overflow-hidden rounded-[28px] border border-slate-800/90 bg-slate-950 shadow-2xl shadow-black/50 ring-1 ring-white/[0.04]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-800/90 bg-slate-950/95 px-5 py-4">
          <div className="min-w-0">
            <div className="text-xs font-medium uppercase tracking-[0.22em] text-cyan-300">
              任务详情
            </div>
            <h2
              id="workbench-task-detail-drawer-title"
              className="mt-1 truncate text-lg font-semibold text-slate-50"
            >
              {props.selectedTask?.title ?? "未选择任务"}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              详情信息已从首页右侧栏移入抽屉，避免挤压主列表与形成长窄栏。
            </p>
          </div>

          <button
            type="button"
            onClick={props.onClose}
            className="shrink-0 rounded-xl border border-slate-700/80 bg-slate-900/80 px-3 py-2 text-sm font-medium text-slate-200 transition hover:border-cyan-400/30 hover:text-cyan-100"
          >
            关闭
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto bg-[#07080a] p-3 sm:p-5">
          <TaskDetailPanel
            panelId="task-detail-panel"
            runLogPanelId="task-run-log-panel"
            requestedRunId={props.requestedRunId}
            selectedTask={props.selectedTask}
            budget={props.budget}
            realtimeStatus={props.realtimeStatus}
            onNavigateToDeliverable={props.onNavigateToDeliverable}
            onNavigateToRun={props.onNavigateToRun}
            onNavigateToStrategyPreview={({ taskId, runId }) =>
              props.onNavigateToProjectDrilldown({
                source: "home_latest_run",
                taskId,
                runId,
              })
            }
          />
        </div>
      </div>
    </div>
  );
}
