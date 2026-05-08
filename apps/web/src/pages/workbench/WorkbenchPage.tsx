import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

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
  const healthQuery = useBackendHealth();
  const runWorkerOnceMutation = useRunWorkerOnce();
  const runWorkerPoolOnceMutation = useRunWorkerPoolOnce();
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [requestedRunId, setRequestedRunId] = useState<string | null>(null);
  const [isTaskDetailOpen, setIsTaskDetailOpen] = useState(false);

  const tasks = overviewQuery.data?.tasks ?? [];

  useEffect(() => {
    if (!tasks.length) {
      if (selectedTaskId !== null) {
        setSelectedTaskId(null);
      }
      if (isTaskDetailOpen) {
        setIsTaskDetailOpen(false);
      }
      return;
    }

    const hasSelection = tasks.some((task) => task.id === selectedTaskId);
    if (!selectedTaskId || !hasSelection) {
      setSelectedTaskId(tasks[0].id);
      setRequestedRunId(null);
    }
  }, [isTaskDetailOpen, tasks, selectedTaskId]);

  const selectedTask = useMemo<ConsoleTask | null>(
    () => tasks.find((task) => task.id === selectedTaskId) ?? null,
    [tasks, selectedTaskId],
  );

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
      }),
    );
  };

  const handleNavigateToRun = (runId: string, taskId: string) => {
    navigate(
      buildRunRoute({
        runId,
        taskId,
        from: "workbench",
      }),
    );
  };

  const handleNavigateToProjectDrilldown = (detail: BossDrilldownNavigateDetail) => {
    navigate(`/projects${buildBossDrilldownHash(detail)}`);
  };

  return (
    <div className="relative overflow-hidden rounded-[30px] border border-zinc-900 bg-[#0f0f10] p-3 shadow-2xl shadow-black/25 ring-1 ring-white/[0.025] sm:p-4">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-[radial-gradient(circle_at_50%_0%,rgba(255,255,255,0.055),transparent_36%)]" />
      <div className="relative space-y-3">
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

        <div className="min-w-0 space-y-3">
          <TaskTableSection
            tasks={tasks}
            selectedTaskId={selectedTaskId}
            overviewIsLoading={overviewQuery.isLoading}
            overviewIsError={overviewQuery.isError}
            onSelectTask={(taskId) => {
              setSelectedTaskId(taskId);
              setRequestedRunId(null);
              setIsTaskDetailOpen(true);
            }}
            onNavigateToTask={handleNavigateToTask}
            onNavigateToRun={handleNavigateToRun}
            onNavigateToProjectDrilldown={handleNavigateToProjectDrilldown}
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
        </div>
      </div>

      <RightSidebarOverviewSection
        isOpen={isTaskDetailOpen}
        onClose={() => setIsTaskDetailOpen(false)}
        requestedRunId={requestedRunId}
        selectedTask={selectedTask}
        budget={overviewQuery.data?.budget ?? null}
        realtimeStatus={realtime.status}
        onNavigateToTask={handleNavigateToTask}
        onNavigateToRun={handleNavigateToRun}
        onNavigateToProjectDrilldown={handleNavigateToProjectDrilldown}
      />
    </div>
  );
}
