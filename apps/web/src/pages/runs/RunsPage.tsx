import { useEffect, useMemo } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import type { ConsoleTask } from "../../features/console/types";
import { useConsoleOverview } from "../../features/console/hooks";
import { useConsoleEventStream } from "../../features/events/hooks";
import { buildDeliverablesRoute } from "../../lib/deliverable-route";
import { buildRunRoute } from "../../lib/run-route";
import { buildBossDrilldownHash, type BossDrilldownNavigateDetail } from "../shared/boss-drilldown-route";
import { useProjectScope } from "../shared/useProjectScope";
import { RunsHistoryContextNotice } from "./components/RunsHistoryContextNotice";
import { RunsListPanel } from "./components/RunsListPanel";
import { RunsMissingTaskContextNotice } from "./components/RunsMissingTaskContextNotice";
import { RunsPageHeader } from "./components/RunsPageHeader";
import { RunsTaskDetailSection } from "./components/RunsTaskDetailSection";
import { useRunSelection } from "./hooks/useRunSelection";

export function RunsPage() {
  const navigate = useNavigate();
  const { runId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });
  const { selectedProjectId, setSelectedProjectId, projects, selectedProjectName } =
    useProjectScope();

  const allTasks: ConsoleTask[] = overviewQuery.data?.tasks ?? [];
  const routeTaskId = searchParams.get("taskId");

  // ── Filter tasks by selected project ─────────────────────────────
  const filteredTasks = useMemo(
    () =>
      selectedProjectId === "all"
        ? allTasks
        : allTasks.filter((task) => task.project_id === selectedProjectId),
    [allTasks, selectedProjectId],
  );

  // ── Clear runId / taskId when the selected run doesn't belong to
  //     the current project scope ────────────────────────────────────
  useEffect(() => {
    if (selectedProjectId === "all") return;
    if (!runId) return;
    const runInScope = filteredTasks.some(
      (task) => task.latest_run?.id === runId,
    );
    if (!runInScope) {
      const next = new URLSearchParams(searchParams);
      next.delete("taskId");
      next.delete("runId");
      if (selectedProjectId !== "all") {
        next.set("projectId", selectedProjectId);
      }
      setSearchParams(next, { replace: true });
      navigate(`/runs?${next.toString()}`, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProjectId]);

  useEffect(() => {
    if (selectedProjectId === "all") return;
    if (!routeTaskId) return;
    const taskInScope = filteredTasks.some((task) => task.id === routeTaskId);
    if (!taskInScope) {
      const next = new URLSearchParams(searchParams);
      next.delete("taskId");
      next.delete("runId");
      if (selectedProjectId !== "all") {
        next.set("projectId", selectedProjectId);
      }
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProjectId]);

  const runSelection = useRunSelection({
    tasks: filteredTasks,
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

  // ── Per-project run counts for the selector ──────────────────────
  const perProjectRunCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const task of allTasks) {
      if (task.latest_run && task.project_id) {
        counts[task.project_id] = (counts[task.project_id] ?? 0) + 1;
      }
    }
    return counts;
  }, [allTasks]);

  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 5rem)" }}>
      <RunsPageHeader
        latestRunCount={runSelection.latestRuns.length}
        runId={runId}
        realtimeStatus={realtime.status}
        isRefreshing={overviewQuery.isFetching}
        onRefresh={() => void overviewQuery.refetch()}
      />

      {/* Project scope selector — shared with tasks page */}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="text-xs uppercase tracking-[0.2em] text-zinc-500">
          当前项目
        </label>
        <select
          value={selectedProjectId}
          onChange={(event) => setSelectedProjectId(event.target.value)}
          className="min-w-0 rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2 pr-8 text-sm text-zinc-100 outline-none ring-0 transition focus:border-white/20"
        >
          <option value="all" className="bg-[#161616] text-zinc-100">
            全部项目 · {allTasks.filter((t) => t.latest_run).length} 条运行
          </option>
          {projects.map((project) => {
            const count = perProjectRunCounts[project.id] ?? 0;
            return (
              <option
                key={project.id}
                value={project.id}
                className="bg-[#161616] text-zinc-100"
              >
                {project.name} · {count} 条运行
              </option>
            );
          })}
        </select>
        {selectedProjectId !== "all" ? (
          <span className="truncate text-sm text-zinc-400">
            {selectedProjectName} · {runSelection.latestRuns.length} 条运行
          </span>
        ) : null}
      </div>

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
                projectId: selectedProjectId,
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
