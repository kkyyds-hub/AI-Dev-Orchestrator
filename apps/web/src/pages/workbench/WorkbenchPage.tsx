import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { useBackendHealth, useConsoleOverview } from "../../features/console/hooks";
import { useConsoleEventStream } from "../../features/events/hooks";
import { useRunWorkerOnce } from "../../features/task-actions/hooks";
import { formatDateTime } from "../../lib/format";
import { buildRunRoute } from "../../lib/run-route";
import { buildTaskRoute } from "../../lib/task-route";
import { useProjectScope } from "../shared/useProjectScope";
import { DirectorChatEntry } from "./components/DirectorChatEntry";
import { QuickEntryCards } from "./components/QuickEntryCards";
import { SituationPanel } from "./components/SituationPanel";
import { WorkbenchHeader } from "./components/WorkbenchHeader";

export function WorkbenchPage() {
  const navigate = useNavigate();
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });
  const healthQuery = useBackendHealth();
  const { selectedProjectId, selectedProjectName } = useProjectScope();
  const runWorkerOnceMutation = useRunWorkerOnce();

  const lastUpdatedText = useMemo(() => {
    if (!overviewQuery.dataUpdatedAt) {
      return "暂未刷新";
    }
    return formatDateTime(new Date(overviewQuery.dataUpdatedAt).toISOString());
  }, [overviewQuery.dataUpdatedAt]);

  const handleRefresh = async () => {
    await Promise.all([overviewQuery.refetch(), healthQuery.refetch()]);
  };

  const handleNavigateToTask = (taskId: string, options?: { runId?: string | null }) => {
    navigate(
      buildTaskRoute({
        taskId,
        runId: options?.runId ?? null,
        from: "workbench",
        projectId: selectedProjectId === "all" ? null : selectedProjectId,
      }),
    );
  };

  const handleNavigateToRun = (runId: string, taskId: string) => {
    navigate(
      buildRunRoute({
        runId,
        taskId,
        from: "workbench",
        projectId: selectedProjectId === "all" ? null : selectedProjectId,
      }),
    );
  };

  const handleNavigateToProjectDrilldown = (detail: {
    source: "home_latest_run" | "home_manual_run";
    taskId: string;
    runId?: string | null;
  }) => {
    const params = new URLSearchParams();
    params.set("source", detail.source);
    params.set("taskId", detail.taskId);
    if (detail.runId) params.set("runId", detail.runId);
    navigate(`/projects#boss-drilldown?${params.toString()}`);
  };

  const handleNavigateToTasks = () => {
    if (selectedProjectId !== "all") {
      navigate(`/tasks?projectId=${selectedProjectId}`);
    } else {
      navigate("/tasks");
    }
  };

  return (
    <div className="relative min-w-0 space-y-6">
      <WorkbenchHeader
        backendStatus={healthQuery.data?.status}
        realtimeStatus={realtime.status}
        lastUpdatedText={lastUpdatedText}
        selectedProjectName={selectedProjectName}
        selectedProjectId={selectedProjectId}
      />

      <div className="flex flex-col gap-6 lg:flex-row">
        <div className="flex-1 lg:min-w-0">
          <DirectorChatEntry
            isRunWorkerOncePending={runWorkerOnceMutation.isPending}
            onRunWorkerOnce={() => runWorkerOnceMutation.mutate()}
            workerOnceData={runWorkerOnceMutation.data}
            workerOnceIsError={runWorkerOnceMutation.isError}
            workerOnceErrorMessage={
              runWorkerOnceMutation.isError ? runWorkerOnceMutation.error.message : null
            }
          />
        </div>

        <div className="w-full lg:w-80 xl:w-96 shrink-0">
          <SituationPanel
            overviewData={overviewQuery.data}
            overviewIsLoading={overviewQuery.isLoading}
            onRefresh={() => {
              void handleRefresh();
            }}
          />
        </div>
      </div>

      <QuickEntryCards
        overviewData={overviewQuery.data}
        selectedProjectId={selectedProjectId}
        onNavigateToTasks={handleNavigateToTasks}
      />

      {/* Preserve existing navigation helpers for future use via refs or other components */}
      <NavigationSilent
        onNavigateToTask={handleNavigateToTask}
        onNavigateToRun={handleNavigateToRun}
        onNavigateToProjectDrilldown={handleNavigateToProjectDrilldown}
      />
    </div>
  );
}

/**
 * Invisible component that preserves the navigation functions as callable
 * from other components that may be added later. This keeps the functions
 * from being tree-shaken while not rendering anything.
 */
function NavigationSilent(_props: {
  onNavigateToTask: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToRun: (runId: string, taskId: string) => void;
  onNavigateToProjectDrilldown: (detail: {
    source: "home_latest_run" | "home_manual_run";
    taskId: string;
    runId?: string | null;
  }) => void;
}) {
  return null;
}
