import { TaskTableSection } from "../../../app/sections/TaskTableSection";
import { TaskDetailPanel } from "../../../features/task-detail/TaskDetailPanel";
import type { ConsoleBudget, ConsoleTask } from "../../../features/console/types";
import type { StreamConnectionStatus } from "../../../features/events/types";
import type { BossDrilldownNavigateDetail } from "../../shared/boss-drilldown-route";

type TasksPageContentProps = {
  selectedTaskId: string | null;
  selectedTask: ConsoleTask | null;
  overviewIsLoading: boolean;
  overviewIsError: boolean;
  requestedRunId: string | null;
  tasks: ConsoleTask[];
  budget: ConsoleBudget | null;
  realtimeStatus: StreamConnectionStatus;
  onSelectTask: (taskId: string) => void;
  onNavigateToRun: (nextRunId: string, nextTaskId: string) => void;
  onNavigateToProjectDrilldown: (detail: BossDrilldownNavigateDetail) => void;
  onNavigateToDeliverable: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
  onNavigateToStrategyPreview: (input: {
    taskId: string;
    runId?: string | null;
  }) => void;
};

export function TasksPageContent(props: TasksPageContentProps) {
  return (
    <section
      className="grid min-h-0 gap-0 xl:grid-cols-[minmax(0,1fr)_minmax(420px,1fr)]"
      style={{ height: "calc(100vh - 10rem)" }}
    >
      <TaskTableSection
        tasks={props.tasks}
        selectedTaskId={props.selectedTaskId}
        overviewIsLoading={props.overviewIsLoading}
        overviewIsError={props.overviewIsError}
        onSelectTask={props.onSelectTask}
        onNavigateToRun={props.onNavigateToRun}
        onNavigateToProjectDrilldown={props.onNavigateToProjectDrilldown}
      />

      <div className="min-h-0 overflow-y-auto border-l border-[#333333]">
        <TaskDetailPanel
          panelId="tasks-detail-panel"
          runLogPanelId="tasks-run-log-panel"
          requestedRunId={props.requestedRunId}
          selectedTask={props.selectedTask}
          budget={props.budget}
          realtimeStatus={props.realtimeStatus}
          surfaceVariant="line"
          onNavigateToDeliverable={props.onNavigateToDeliverable}
          onNavigateToRun={props.onNavigateToRun}
          onNavigateToStrategyPreview={props.onNavigateToStrategyPreview}
        />
      </div>
    </section>
  );
}
