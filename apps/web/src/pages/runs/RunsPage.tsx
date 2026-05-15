import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useConsoleOverview } from "../../features/console/hooks";
import { useConsoleEventStream } from "../../features/events/hooks";
import { buildDeliverablesRoute } from "../../lib/deliverable-route";
import { buildRunRoute } from "../../lib/run-route";
import { RunsHistoryContextNotice } from "./components/RunsHistoryContextNotice";
import { RunsListPanel } from "./components/RunsListPanel";
import { RunsMissingTaskContextNotice } from "./components/RunsMissingTaskContextNotice";
import { RunsPageHeader } from "./components/RunsPageHeader";
import { RunsTaskDetailSection } from "./components/RunsTaskDetailSection";
import { useRunSelection } from "./hooks/useRunSelection";
import { buildBossDrilldownHash, type BossDrilldownNavigateDetail } from "../shared/boss-drilldown-route";

export function RunsPage() {
  const navigate = useNavigate();
  const { runId } = useParams();
  const [searchParams] = useSearchParams();
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });

  const routeTaskId = searchParams.get("taskId");
  const runSelection = useRunSelection({
    tasks: overviewQuery.data?.tasks ?? [],
    runId,
    routeTaskId,
    navigate,
  });

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
    <div className="flex flex-col" style={{ height: "calc(100vh - 5rem)" }}>
      <RunsPageHeader
        latestRunCount={runSelection.latestRuns.length}
        runId={runId}
        realtimeStatus={realtime.status}
        isRefreshing={overviewQuery.isFetching}
        onRefresh={() => void overviewQuery.refetch()}
      />

      {runId && !runSelection.effectiveTaskId ? (
        <RunsMissingTaskContextNotice />
      ) : null}

      {runId &&
      runSelection.effectiveTaskId &&
      !runSelection.selectedRunInLatestList ? (
        <RunsHistoryContextNotice />
      ) : null}

      <section
        className="mt-4 grid min-h-0 flex-1 gap-0 xl:grid-cols-[480px_minmax(0,1fr)]"
        aria-label="工作流运行列表与详情"
      >
        <RunsListPanel
          isLoading={overviewQuery.isLoading}
          isError={overviewQuery.isError}
          latestRuns={runSelection.latestRuns}
          runId={runId}
          onNavigateToRun={(route) => navigate(route)}
        />

        <RunsTaskDetailSection
          runId={runId}
          selectedTask={runSelection.selectedTask}
          budget={overviewQuery.data?.budget ?? null}
          realtimeStatus={realtime.status}
          onNavigateToDeliverable={handleNavigateToDeliverable}
          onNavigateToRun={(nextRunId, taskId) =>
            navigate(
              buildRunRoute({
                runId: nextRunId,
                taskId,
                from: "runs",
              }),
            )
          }
          onNavigateToStrategyPreview={({ taskId: nextTaskId, runId: nextRunId }) =>
            handleNavigateToProjectDrilldown({
              source: "home_latest_run",
              taskId: nextTaskId,
              runId: nextRunId,
            })
          }
        />
      </section>
    </div>
  );
}
