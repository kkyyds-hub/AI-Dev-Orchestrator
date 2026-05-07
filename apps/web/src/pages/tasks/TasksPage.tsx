import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useConsoleOverview } from "../../features/console/hooks";
import { useConsoleEventStream } from "../../features/events/hooks";
import { buildDeliverablesRoute } from "../../lib/deliverable-route";
import { buildRunRoute } from "../../lib/run-route";
import { buildTaskRoute } from "../../lib/task-route";
import { buildBossDrilldownHash } from "../shared/boss-drilldown-route";
import { TasksPageContent } from "./components/TasksPageContent";
import { TasksPageHeader } from "./components/TasksPageHeader";
import { TasksTaskNotFoundNotice } from "./components/TasksTaskNotFoundNotice";
import { useTaskSelection } from "./hooks/useTaskSelection";

export function TasksPage() {
  const navigate = useNavigate();
  const { taskId } = useParams();
  const [searchParams] = useSearchParams();
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });

  const tasks = overviewQuery.data?.tasks ?? [];
  const requestedRunId = searchParams.get("runId");
  const taskSelection = useTaskSelection({
    tasks,
    taskId,
    overviewIsLoading: overviewQuery.isLoading,
  });
  const selectedTaskLabel = taskSelection.selectedTask
    ? taskSelection.selectedTask.title
    : taskId
      ? "未命中任务"
      : "未选择";

  const handleNavigateToDeliverable = (input: {
    projectId: string;
    deliverableId: string;
  }) => {
    navigate(
      buildDeliverablesRoute({
        projectId: input.projectId,
        deliverableId: input.deliverableId,
      }),
    );
  };

  const handleNavigateToProjectDrilldown = (detail: {
    source: "home_latest_run" | "home_manual_run";
    taskId: string;
    runId?: string | null;
  }) => {
    navigate(`/projects${buildBossDrilldownHash(detail)}`);
  };

  return (
    <div className="space-y-6">
      <TasksPageHeader
        tasksCount={tasks.length}
        selectedTaskLabel={selectedTaskLabel}
        realtimeStatus={realtime.status}
      />

      {taskSelection.taskNotFound ? (
        <TasksTaskNotFoundNotice taskId={taskId ?? ""} />
      ) : null}

      <TasksPageContent
        selectedTaskId={taskSelection.selectedTask?.id ?? taskId ?? null}
        selectedTask={taskSelection.selectedTask}
        overviewIsLoading={overviewQuery.isLoading}
        overviewIsError={overviewQuery.isError}
        requestedRunId={requestedRunId}
        tasks={tasks}
        budget={overviewQuery.data?.budget ?? null}
        realtimeStatus={realtime.status}
        onSelectTask={(nextTaskId) => {
          navigate(buildTaskRoute({ taskId: nextTaskId, from: "tasks" }));
        }}
        onNavigateToRun={(nextRunId, nextTaskId) => {
          navigate(
            buildRunRoute({
              runId: nextRunId,
              taskId: nextTaskId,
              from: "tasks",
            }),
          );
        }}
        onNavigateToProjectDrilldown={handleNavigateToProjectDrilldown}
        onNavigateToDeliverable={handleNavigateToDeliverable}
        onNavigateToStrategyPreview={({ taskId: nextTaskId, runId }) =>
          handleNavigateToProjectDrilldown({
            source: "home_latest_run",
            taskId: nextTaskId,
            runId,
          })
        }
      />
    </div>
  );
}
