import { TaskDetailPanel } from "../../../features/task-detail/TaskDetailPanel";
import type { ConsoleBudget, ConsoleTask } from "../../../features/console/types";
import type { StreamConnectionStatus } from "../../../features/events/types";

type RunsTaskDetailSectionProps = {
  runId: string | undefined;
  selectedTask: ConsoleTask | null;
  budget: ConsoleBudget | null;
  realtimeStatus: StreamConnectionStatus;
  onNavigateToDeliverable: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
  onNavigateToRun: (nextRunId: string, taskId: string) => void;
  onNavigateToStrategyPreview: (input: {
    taskId: string;
    runId?: string | null;
  }) => void;
};

export function RunsTaskDetailSection(props: RunsTaskDetailSectionProps) {
  return (
    <section className="min-w-0" data-testid="runs-task-detail-section">
      <div className="mb-4 border-b border-[#333333] pb-4">
        <h2 className="text-base font-semibold text-zinc-100">任务与运行详情</h2>
        <p className="mt-1 text-sm leading-6 text-zinc-500">
          保留任务处理、运行切换、交付物跳转、日志查看与策略预览入口。
        </p>
      </div>
      <TaskDetailPanel
        panelId="runs-task-detail-panel"
        runLogPanelId="runs-run-log-panel"
        requestedRunId={props.runId ?? null}
        selectedTask={props.selectedTask}
        budget={props.budget}
        realtimeStatus={props.realtimeStatus}
        surfaceVariant="line"
        onNavigateToDeliverable={props.onNavigateToDeliverable}
        onNavigateToRun={props.onNavigateToRun}
        onNavigateToStrategyPreview={props.onNavigateToStrategyPreview}
      />
    </section>
  );
}
