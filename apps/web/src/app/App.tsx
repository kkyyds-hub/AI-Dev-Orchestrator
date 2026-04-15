import { useEffect, useMemo, useState } from "react";

import { useReviewClusters } from "../features/console-metrics/decision-hooks";
import { useBackendHealth, useConsoleOverview } from "../features/console/hooks";
import type { ConsoleTask } from "../features/console/types";
import { useConsoleEventStream } from "../features/events/hooks";
import { ProjectOverviewPage } from "../features/projects/ProjectOverviewPage";
import { useRunWorkerOnce, useRunWorkerPoolOnce } from "../features/task-actions/hooks";
import { formatDateTime } from "../lib/format";
import { HomeHeaderSection } from "./sections/HomeHeaderSection";
import { HomeMetricsSection } from "./sections/HomeMetricsSection";
import { ManualRunResultSection } from "./sections/ManualRunResultSection";
import { RightSidebarOverviewSection } from "./sections/RightSidebarOverviewSection";
import { TaskTableSection } from "./sections/TaskTableSection";
import { WorkerPoolResultSection } from "./sections/WorkerPoolResultSection";

type BossDrilldownNavigateDetail = {
  source: "home_latest_run" | "home_manual_run";
  taskId: string;
  runId?: string | null;
};

function dispatchBossDrilldownNavigation(detail: BossDrilldownNavigateDetail) {
  const params = new URLSearchParams();
  params.set("source", detail.source);
  params.set("taskId", detail.taskId);
  if (detail.runId) {
    params.set("runId", detail.runId);
  }
  window.location.hash = `boss-drilldown?${params.toString()}`;
  window.dispatchEvent(
    new CustomEvent("boss:drilldown-navigate", {
      detail: {
        source: detail.source,
        taskId: detail.taskId,
        runId: detail.runId ?? null,
      },
    }),
  );
}

export function App() {
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
      return "灏氭湭鍒锋柊";
    }

    return formatDateTime(new Date(overviewQuery.dataUpdatedAt).toISOString());
  }, [overviewQuery.dataUpdatedAt]);

  const handleRefresh = async () => {
    await Promise.all([overviewQuery.refetch(), healthQuery.refetch()]);
  };

  const handleNavigateToTaskDetail = (
    taskId: string,
    options?: { runId?: string | null },
  ) => {
    setSelectedTaskId(taskId);
    setRequestedRunId(options?.runId ?? null);

    const targetId = options?.runId ? "task-run-log-panel" : "task-detail-panel";
    requestAnimationFrame(() => {
      document.getElementById(targetId)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  const handleNavigateToDeliverable = (input: {
    projectId: string;
    deliverableId: string;
  }) => {
    window.dispatchEvent(
      new CustomEvent("deliverable:navigate", {
        detail: input,
      }),
    );

    requestAnimationFrame(() => {
      document.getElementById("deliverable-center")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  const handleNavigateToProjectDrilldown = (detail: BossDrilldownNavigateDetail) => {
    dispatchBossDrilldownNavigation(detail);
    requestAnimationFrame(() => {
      document.getElementById("project-detail")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
        <ProjectOverviewPage onNavigateToTask={handleNavigateToTaskDetail} />

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

        <section className="grid gap-4 lg:grid-cols-[1.45fr_1fr]">
          <TaskTableSection
            tasks={tasks}
            selectedTaskId={selectedTaskId}
            overviewIsLoading={overviewQuery.isLoading}
            overviewIsError={overviewQuery.isError}
            onSelectTask={(taskId) => {
              setSelectedTaskId(taskId);
              setRequestedRunId(null);
            }}
            onNavigateToProjectDrilldown={handleNavigateToProjectDrilldown}
          />

          <RightSidebarOverviewSection
            requestedRunId={requestedRunId}
            selectedTask={selectedTask}
            budget={overviewQuery.data?.budget ?? null}
            blockedTasks={overviewQuery.data?.blocked_tasks ?? 0}
            realtimeStatus={realtime.status}
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
    </main>
  );
}
