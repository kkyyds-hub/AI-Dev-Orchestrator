import { useCallback, useEffect, useMemo, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import type { ConsoleTask } from "../../../features/console/types";
import { useConsoleOverview } from "../../../features/console/hooks";
import { useConsoleEventStream } from "../../../features/events/hooks";
import { buildRunRoute } from "../../../lib/run-route";
import { useProjectScope } from "../../shared/useProjectScope";
import { RunsListPanel } from "../../runs/components/RunsListPanel";
import { RunsTaskDetailSection } from "../../runs/components/RunsTaskDetailSection";
import { RunsMissingTaskContextNotice } from "../../runs/components/RunsMissingTaskContextNotice";
import { RunsHistoryContextNotice } from "../../runs/components/RunsHistoryContextNotice";
import { useRunSelection } from "../../runs/hooks/useRunSelection";

export function ExecutionRunsTab() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });
  const { selectedProjectId, setSelectedProjectId, projects, selectedProjectName, projectNotFound } =
    useProjectScope();

  const allTasks: ConsoleTask[] = overviewQuery.data?.tasks ?? [];
  const routeTaskId = searchParams.get("taskId");
  const routeRunId = searchParams.get("runId") ?? undefined;

  // ── Filter tasks by selected project ─────────────────────────────
  const filteredTasks = useMemo(
    () =>
      selectedProjectId === "all"
        ? allTasks
        : allTasks.filter((task) => task.project_id === selectedProjectId),
    [allTasks, selectedProjectId],
  );

  const overviewLoaded = !overviewQuery.isLoading;

  // ── Clear runId when run not in scope ────────────────────────────
  useEffect(() => {
    if (selectedProjectId === "all") return;
    if (!routeRunId) return;
    if (!overviewLoaded) return;
    const runInScope = filteredTasks.some(
      (task) => task.latest_run?.id === routeRunId,
    );
    if (!runInScope) {
      const next = new URLSearchParams(searchParams);
      next.delete("taskId");
      next.delete("runId");
      next.set("tab", "runs");
      if (selectedProjectId !== "all") next.set("projectId", selectedProjectId);
      setSearchParams(next, { replace: true });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProjectId, routeRunId, overviewLoaded, filteredTasks]);

  // Wrap navigate so useRunSelection's internal buildRunRoute calls
  // stay within /execution search params instead of going to /runs.
  const searchParamsRef = useRef(searchParams);
  searchParamsRef.current = searchParams;
  const selectedProjectIdRef = useRef(selectedProjectId);
  selectedProjectIdRef.current = selectedProjectId;

  const wrappedNavigate = useCallback(
    ((to: string, opts?: { replace?: boolean }) => {
      if (typeof to === "string" && to.startsWith("/runs")) {
        const match = to.match(/\/runs\/([^?]+)/);
        const runIdFromRoute = match ? match[1] : null;
        const query = to.includes("?") ? to.slice(to.indexOf("?")) : "";
        const taskIdFromRoute = new URLSearchParams(query).get("taskId");
        if (runIdFromRoute && taskIdFromRoute) {
          const next = new URLSearchParams(searchParamsRef.current);
          next.set("tab", "runs");
          next.set("runId", runIdFromRoute);
          next.set("taskId", taskIdFromRoute);
          const pid = selectedProjectIdRef.current;
          if (pid !== "all") next.set("projectId", pid);
          setSearchParams(next, opts ?? {});
          return;
        }
      }
      navigate(to as any, opts as any);
    }) as typeof navigate,
    [navigate, setSearchParams],
  );

  const runSelection = useRunSelection({
    tasks: filteredTasks,
    runId: routeRunId,
    routeTaskId,
    navigate: wrappedNavigate,
  });

  const handleSelectRun = (runId: string, taskId: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("tab", "runs");
    next.set("runId", runId);
    next.set("taskId", taskId);
    if (selectedProjectId !== "all") next.set("projectId", selectedProjectId);
    setSearchParams(next, { replace: true });
  };

  const handleNavigateToTask = (taskId: string, projectId?: string | null) => {
    const next = new URLSearchParams();
    next.set("tab", "tasks");
    next.set("taskId", taskId);
    const pid = projectId ?? (selectedProjectId !== "all" ? selectedProjectId : null);
    if (pid) next.set("projectId", pid);
    navigate(`/execution?${next.toString()}`);
  };

  const perProjectCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const task of allTasks) {
      if (task.latest_run && task.project_id) {
        counts[task.project_id] = (counts[task.project_id] ?? 0) + 1;
      }
    }
    return counts;
  }, [allTasks]);

  return (
    <div className="space-y-4">
      {/* 项目选择器 */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs uppercase tracking-[0.2em] text-zinc-500">
          当前项目
        </label>
        <select
          value={selectedProjectId}
          onChange={(event) => setSelectedProjectId(event.target.value)}
          className="min-w-0 rounded border border-[#333333] bg-[#1a1a1a] px-2.5 py-1 text-xs text-zinc-300 outline-none focus:border-zinc-500"
        >
          <option value="all" className="bg-[#161616]">
            全部项目 ({allTasks.filter((t) => t.latest_run).length})
          </option>
          {projects.map((project) => {
            const count = perProjectCounts[project.id] ?? 0;
            return (
              <option key={project.id} value={project.id} className="bg-[#161616]">
                {project.name} ({count})
              </option>
            );
          })}
        </select>
        {selectedProjectId !== "all" && (
          <span className="text-xs text-zinc-500 truncate">
            {selectedProjectName}
          </span>
        )}
      </div>

      {projectNotFound ? (
        <div className="rounded border border-zinc-700 px-3 py-2 text-xs text-zinc-400">
          项目不存在或已删除。{" "}
          <button
            type="button"
            onClick={() => setSelectedProjectId("all")}
            className="underline transition hover:text-zinc-200"
          >
            切回全部项目
          </button>
        </div>
      ) : null}

      {routeRunId && !runSelection.effectiveTaskId ? (
        <RunsMissingTaskContextNotice />
      ) : null}

      {routeRunId &&
      runSelection.effectiveTaskId &&
      !runSelection.selectedRunInLatestList ? (
        <RunsHistoryContextNotice />
      ) : null}

      {/* 工作区：左侧运行列表 + 右侧诊断详情 */}
      <div
        className="hidden xl:grid xl:grid-cols-[35fr_65fr] xl:gap-0"
        style={{ height: "calc(100vh - 320px)" }}
      >
        <RunsListPanel
          isLoading={overviewQuery.isLoading}
          isError={overviewQuery.isError}
          latestRuns={runSelection.latestRuns}
          runId={routeRunId}
          onNavigateToRun={(route) => {
            // Parse the /runs/{runId}?taskId=xxx route into execution params
            const match = route.match(/\/runs\/([^?]+)/);
            const runIdFromRoute = match ? match[1] : null;
            const taskIdFromRoute = new URLSearchParams(
              route.includes("?") ? route.slice(route.indexOf("?")) : ""
            ).get("taskId");
            if (runIdFromRoute && taskIdFromRoute) {
              handleSelectRun(runIdFromRoute, taskIdFromRoute);
            } else {
              navigate(route);
            }
          }}
        />

        <RunsTaskDetailSection
          runId={routeRunId}
          selectedTask={runSelection.selectedTask}
          budget={overviewQuery.data?.budget ?? null}
          realtimeStatus={realtime.status}
          onNavigateToDeliverable={() => {}}
          onNavigateToRun={(nextRunId, taskId) => {
            handleSelectRun(nextRunId, taskId);
          }}
          onNavigateToStrategyPreview={({ taskId: previewTaskId }) => {
            handleNavigateToTask(previewTaskId);
          }}
        />
      </div>

      {/* Mobile: stack */}
      <div className="xl:hidden flex flex-col gap-4">
        <RunsListPanel
          isLoading={overviewQuery.isLoading}
          isError={overviewQuery.isError}
          latestRuns={runSelection.latestRuns}
          runId={routeRunId}
          onNavigateToRun={(route) => navigate(route)}
        />
        <RunsTaskDetailSection
          runId={routeRunId}
          selectedTask={runSelection.selectedTask}
          budget={overviewQuery.data?.budget ?? null}
          realtimeStatus={realtime.status}
          onNavigateToDeliverable={() => {}}
          onNavigateToRun={(nextRunId, taskId) => {
            navigate(
              buildRunRoute({ runId: nextRunId, taskId, from: "runs", projectId: selectedProjectId }),
            );
          }}
          onNavigateToStrategyPreview={() => {}}
        />
      </div>
    </div>
  );
}
