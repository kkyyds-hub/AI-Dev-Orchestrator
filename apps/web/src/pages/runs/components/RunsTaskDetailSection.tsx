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
    <TaskDetailPanel
      panelId="runs-task-detail-panel"
      runLogPanelId="runs-run-log-panel"
      requestedRunId={props.runId ?? null}
      selectedTask={props.selectedTask}
      budget={props.budget}
      realtimeStatus={props.realtimeStatus}
      onNavigateToDeliverable={props.onNavigateToDeliverable}
      onNavigateToRun={props.onNavigateToRun}
      onNavigateToStrategyPreview={props.onNavigateToStrategyPreview}
    />
  );
}
