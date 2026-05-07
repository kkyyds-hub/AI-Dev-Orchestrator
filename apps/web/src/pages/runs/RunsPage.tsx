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
import { buildBossDrilldownHash } from "./lib";
import type { BossDrilldownNavigateDetail } from "./types";

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
    <div className="space-y-6">
      <RunsPageHeader
        latestRunCount={runSelection.latestRuns.length}
        runId={runId}
        realtimeStatus={realtime.status}
      />

      {runId && !runSelection.effectiveTaskId ? (
        <RunsMissingTaskContextNotice />
      ) : null}

      {runId &&
      runSelection.effectiveTaskId &&
      !runSelection.selectedRunInLatestList ? (
        <RunsHistoryContextNotice />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[1.05fr_minmax(380px,1fr)]">
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
