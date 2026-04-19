import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useReviewClusters } from "../../features/console-metrics/decision-hooks";
import { useBackendHealth, useConsoleOverview } from "../../features/console/hooks";
import type { ConsoleTask } from "../../features/console/types";
import { useConsoleEventStream } from "../../features/events/hooks";
import { useRunWorkerOnce, useRunWorkerPoolOnce } from "../../features/task-actions/hooks";
import { formatDateTime } from "../../lib/format";
import { HomeHeaderSection } from "../../app/sections/HomeHeaderSection";
import { HomeMetricsSection } from "../../app/sections/HomeMetricsSection";
import { ManualRunResultSection } from "../../app/sections/ManualRunResultSection";
import { RightSidebarOverviewSection } from "../../app/sections/RightSidebarOverviewSection";
import { TaskTableSection } from "../../app/sections/TaskTableSection";
import { WorkerPoolResultSection } from "../../app/sections/WorkerPoolResultSection";
import { buildDeliverablesRoute } from "../../lib/deliverable-route";
import { buildRunRoute } from "../../lib/run-route";
import { buildTaskRoute } from "../../lib/task-route";

type BossDrilldownNavigateDetail = {
  source: "home_latest_run" | "home_manual_run";
  taskId: string;
  runId?: string | null;
};

function buildBossDrilldownHash(detail: BossDrilldownNavigateDetail) {
  const params = new URLSearchParams();
  params.set("source", detail.source);
  params.set("taskId", detail.taskId);

  if (detail.runId) {
    params.set("runId", detail.runId);
  }

  return `#boss-drilldown?${params.toString()}`;
}

export function WorkbenchPage() {
  const navigate = useNavigate();
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });
  const reviewClustersQuery = useReviewClusters();
  const healthQuery = useBackendHealth();
  const runWorkerOnceMutation = useRunWorkerOnce();
  const runWorkerPoolOnceMutation = useRunWorkerPoolOnce();
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [requestedRunId, setRequestedRunId] = useState<string | null>(null);

  const tasks = overviewQuery.data?.tasks ?? [];

  useEffect(() => {
    if (!tasks.length) {
      if (selectedTaskId !== null) {
        setSelectedTaskId(null);
      }
      return;
    }

    const hasSelection = tasks.some((task) => task.id === selectedTaskId);
    if (!selectedTaskId || !hasSelection) {
      setSelectedTaskId(tasks[0].id);
      setRequestedRunId(null);
    }
  }, [tasks, selectedTaskId]);

  const selectedTask = useMemo<ConsoleTask | null>(
    () => tasks.find((task) => task.id === selectedTaskId) ?? null,
    [tasks, selectedTaskId],
  );

  const lastUpdatedText = useMemo(() => {
    if (!overviewQuery.dataUpdatedAt) {
      return "尚未刷新";
    }

    return formatDateTime(new Date(overviewQuery.dataUpdatedAt).toISOString());
  }, [overviewQuery.dataUpdatedAt]);

  const handleRefresh = async () => {
    await Promise.all([overviewQuery.refetch(), healthQuery.refetch()]);
  };

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

  const handleNavigateToProjectDrilldown = (detail: BossDrilldownNavigateDetail) => {
    navigate(`/projects${buildBossDrilldownHash(detail)}`);
  };

  return (
    <div className="space-y-6">
      <HomeHeaderSection
        backendStatus={healthQuery.data?.status}
        backendService={healthQuery.data?.service}
        realtimeStatus={realtime.status}
        realtimeLastEventType={realtime.lastEventType}
        realtimeLastEventAt={realtime.lastEventAt}
        lastUpdatedText={lastUpdatedText}
        isRunWorkerOncePending={runWorkerOnceMutation.isPending}
        isRunWorkerPoolOncePending={runWorkerPoolOnceMutation.isPending}
        onRunWorkerOnce={() => runWorkerOnceMutation.mutate()}
        onRunWorkerPoolOnce={() => runWorkerPoolOnceMutation.mutate()}
        onRefresh={() => {
          void handleRefresh();
        }}
      />

      <ManualRunResultSection
        data={runWorkerOnceMutation.data}
        isError={runWorkerOnceMutation.isError}
        errorMessage={runWorkerOnceMutation.isError ? runWorkerOnceMutation.error.message : null}
        onNavigateToProjectDrilldown={handleNavigateToProjectDrilldown}
      />

      <WorkerPoolResultSection
        data={runWorkerPoolOnceMutation.data}
        isError={runWorkerPoolOnceMutation.isError}
        errorMessage={runWorkerPoolOnceMutation.isError ? runWorkerPoolOnceMutation.error.message : null}
      />

      <HomeMetricsSection
        totalTasks={overviewQuery.data?.total_tasks ?? 0}
        runningTasks={overviewQuery.data?.running_tasks ?? 0}
        pendingTasks={overviewQuery.data?.pending_tasks ?? 0}
        pausedTasks={overviewQuery.data?.paused_tasks ?? 0}
        waitingHumanTasks={overviewQuery.data?.waiting_human_tasks ?? 0}
        completedTasks={overviewQuery.data?.completed_tasks ?? 0}
        failedTasks={overviewQuery.data?.failed_tasks ?? 0}
        totalPromptTokens={overviewQuery.data?.total_prompt_tokens ?? 0}
        totalCompletionTokens={overviewQuery.data?.total_completion_tokens ?? 0}
        totalEstimatedCost={overviewQuery.data?.total_estimated_cost ?? 0}
      />

      <section className="grid gap-4 xl:grid-cols-[1.45fr_minmax(320px,1fr)]">
        <TaskTableSection
          tasks={tasks}
          selectedTaskId={selectedTaskId}
          overviewIsLoading={overviewQuery.isLoading}
          overviewIsError={overviewQuery.isError}
          onSelectTask={(taskId) => {
            setSelectedTaskId(taskId);
            setRequestedRunId(null);
          }}
          onNavigateToTask={(taskId, options) => {
            navigate(
              buildTaskRoute({
                taskId,
                runId: options?.runId ?? null,
                from: "workbench",
              }),
            );
          }}
          onNavigateToRun={(runId, taskId) => {
            navigate(
              buildRunRoute({
                runId,
                taskId,
                from: "workbench",
              }),
            );
          }}
          onNavigateToProjectDrilldown={handleNavigateToProjectDrilldown}
        />

        <RightSidebarOverviewSection
          requestedRunId={requestedRunId}
          selectedTask={selectedTask}
          budget={overviewQuery.data?.budget ?? null}
          blockedTasks={overviewQuery.data?.blocked_tasks ?? 0}
          realtimeStatus={realtime.status}
          onNavigateToRun={(runId, taskId) =>
            navigate(
              buildRunRoute({
                runId,
                taskId,
                from: "workbench",
              }),
            )
          }
          onNavigateToProjectDrilldown={handleNavigateToProjectDrilldown}
          onNavigateToDeliverable={handleNavigateToDeliverable}
          reviewClusters={reviewClustersQuery.data ?? []}
          reviewClustersIsLoading={reviewClustersQuery.isLoading && !reviewClustersQuery.data}
          reviewClustersErrorMessage={
            reviewClustersQuery.isError ? reviewClustersQuery.error.message : null
          }
          pendingTasks={overviewQuery.data?.pending_tasks ?? 0}
          runningTasks={overviewQuery.data?.running_tasks ?? 0}
          completedTasks={overviewQuery.data?.completed_tasks ?? 0}
          failedTasks={overviewQuery.data?.failed_tasks ?? 0}
          totalPromptTokens={overviewQuery.data?.total_prompt_tokens ?? 0}
          totalCompletionTokens={overviewQuery.data?.total_completion_tokens ?? 0}
          totalEstimatedCost={overviewQuery.data?.total_estimated_cost ?? 0}
        />
      </section>
    </div>
  );
}
