import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useConsoleOverview } from "../../features/console/hooks";
import type { ConsoleTask } from "../../features/console/types";
import { useConsoleEventStream } from "../../features/events/hooks";
import { useBossProjectOverview } from "../../features/projects/hooks";
import { buildDeliverablesRoute } from "../../lib/deliverable-route";
import { buildRunRoute } from "../../lib/run-route";
import { buildTaskRoute } from "../../lib/task-route";
import { buildBossDrilldownHash } from "../shared/boss-drilldown-route";
import { TasksPageContent } from "./components/TasksPageContent";
import { TasksPageHeader } from "./components/TasksPageHeader";
import { TasksTaskNotFoundNotice } from "./components/TasksTaskNotFoundNotice";
import { useTaskSelection } from "./hooks/useTaskSelection";

const LOCALSTORAGE_KEY = "ai-dev-orchestrator:tasks-selected-project-id";

function readStoredProjectId(): string | null {
  try {
    const value = localStorage.getItem(LOCALSTORAGE_KEY);
    return value ?? null;
  } catch {
    return null;
  }
}

function writeStoredProjectId(projectId: string | null) {
  try {
    if (projectId) {
      localStorage.setItem(LOCALSTORAGE_KEY, projectId);
    } else {
      localStorage.removeItem(LOCALSTORAGE_KEY);
    }
  } catch {
    // storage unavailable — ignore
  }
}

/** Resolve the effective projectId for the tasks page.
 *  Priority: URL query ?projectId= → localStorage → "all" */
function resolveInitialProjectId(searchParams: URLSearchParams): string {
  const urlId = searchParams.get("projectId");
  if (urlId) return urlId;
  const stored = readStoredProjectId();
  if (stored) return stored;
  return "all";
}

export function TasksPage() {
  const navigate = useNavigate();
  const { taskId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });
  const projectOverviewQuery = useBossProjectOverview({ enablePolling: false });
  const projects = projectOverviewQuery.data?.projects ?? [];

  const allTasks: ConsoleTask[] = overviewQuery.data?.tasks ?? [];
  const requestedRunId = searchParams.get("runId");

  // ── Project selection state ──────────────────────────────────────
  const [selectedProjectId, setSelectedProjectIdState] = useState<string>(
    () => resolveInitialProjectId(searchParams),
  );

  const setSelectedProjectId = useCallback(
    (nextId: string) => {
      setSelectedProjectIdState(nextId);
      writeStoredProjectId(nextId === "all" ? null : nextId);
      const nextParams = new URLSearchParams(searchParams);
      if (nextId === "all") {
        nextParams.delete("projectId");
      } else {
        nextParams.set("projectId", nextId);
      }
      setSearchParams(nextParams, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  // Sync URL → state (for browser back/forward)
  useEffect(() => {
    const urlId = searchParams.get("projectId") ?? "all";
    setSelectedProjectIdState((current) => (current !== urlId ? urlId : current));
  }, [searchParams]);

  // ── Filter tasks ─────────────────────────────────────────────────
  const filteredTasks = useMemo(
    () =>
      selectedProjectId === "all"
        ? allTasks
        : allTasks.filter((task) => task.project_id === selectedProjectId),
    [allTasks, selectedProjectId],
  );

  // ── Clear taskId / runId when task doesn't belong to current scope
  useEffect(() => {
    if (selectedProjectId === "all") return;
    if (!taskId) return;
    const taskInScope = filteredTasks.some((task) => task.id === taskId);
    if (!taskInScope) {
      const next = new URLSearchParams(searchParams);
      next.delete("runId");
      setSearchParams(next, { replace: true });
      navigate("/tasks", { replace: true });
    }
    // Only re-check on scope change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProjectId]);

  useEffect(() => {
    if (selectedProjectId === "all") return;
    if (!requestedRunId) return;
    if (!taskId) return;
    const taskInScope = filteredTasks.some((task) => task.id === taskId);
    if (!taskInScope) {
      // runId bound to an out-of-scope task — clear it
      const next = new URLSearchParams(searchParams);
      next.delete("runId");
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProjectId]);

  // ── Task selection ───────────────────────────────────────────────
  const taskSelection = useTaskSelection({
    tasks: filteredTasks,
    taskId,
    overviewIsLoading: overviewQuery.isLoading,
  });
  const selectedTaskLabel = taskSelection.selectedTask
    ? taskSelection.selectedTask.title
    : taskId
      ? "未命中任务"
      : "未选择";

  const selectedProjectName = useMemo(() => {
    if (selectedProjectId === "all") return "全部项目";
    return projects.find((p) => p.id === selectedProjectId)?.name ?? "未知项目";
  }, [projects, selectedProjectId]);

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
        tasksCount={filteredTasks.length}
        selectedTaskLabel={selectedTaskLabel}
        realtimeStatus={realtime.status}
      />

      {/* Project scope selector */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs uppercase tracking-[0.2em] text-zinc-500">
          当前项目
        </label>
        <select
          value={selectedProjectId}
          onChange={(event) => setSelectedProjectId(event.target.value)}
          className="min-w-0 rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2 pr-8 text-sm text-zinc-100 outline-none ring-0 transition focus:border-white/20"
        >
          <option value="all" className="bg-[#161616] text-zinc-100">
            全部项目 · {allTasks.length} 条任务
          </option>
          {projects.map((project) => {
            const count = allTasks.filter(
              (task) => task.project_id === project.id,
            ).length;
            return (
              <option
                key={project.id}
                value={project.id}
                className="bg-[#161616] text-zinc-100"
              >
              {project.name} · {count} 条任务
              </option>
            );
          })}
        </select>
        {selectedProjectId !== "all" ? (
          <span className="truncate text-sm text-zinc-400">
            {selectedProjectName} · {filteredTasks.length} 条任务
          </span>
        ) : null}
      </div>

      {taskSelection.taskNotFound ? (
        <TasksTaskNotFoundNotice taskId={taskId ?? ""} />
      ) : null}

      <TasksPageContent
        selectedTaskId={taskSelection.selectedTask?.id ?? taskId ?? null}
        selectedTask={taskSelection.selectedTask}
        overviewIsLoading={overviewQuery.isLoading}
        overviewIsError={overviewQuery.isError}
        requestedRunId={requestedRunId}
        tasks={filteredTasks}
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
