import { useEffect, useMemo } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useConsoleOverview } from "../../features/console/hooks";
import type { ConsoleTask } from "../../features/console/types";
import { useConsoleEventStream } from "../../features/events/hooks";
import { buildDeliverablesRoute } from "../../lib/deliverable-route";
import { buildRunRoute } from "../../lib/run-route";
import { buildTaskRoute } from "../../lib/task-route";
import { buildBossDrilldownHash } from "../shared/boss-drilldown-route";
import { useProjectScope } from "../shared/useProjectScope";
import { TasksPageContent } from "./components/TasksPageContent";
import { TasksPageHeader } from "./components/TasksPageHeader";
import { TasksTaskNotFoundNotice } from "./components/TasksTaskNotFoundNotice";
import { useTaskSelection } from "./hooks/useTaskSelection";

export function TasksPage() {
  const navigate = useNavigate();
  const { taskId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });
  const { selectedProjectId, setSelectedProjectId, projects, selectedProjectName } =
    useProjectScope();

  const allTasks: ConsoleTask[] = overviewQuery.data?.tasks ?? [];
  const requestedRunId = searchParams.get("runId");

  // ── Filter tasks by selected project ─────────────────────────────
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProjectId]);

  useEffect(() => {
    if (selectedProjectId === "all") return;
    if (!requestedRunId) return;
    if (!taskId) return;
    const taskInScope = filteredTasks.some((task) => task.id === taskId);
    if (!taskInScope) {
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

  const perProjectCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const task of allTasks) {
      if (task.project_id) {
        counts[task.project_id] = (counts[task.project_id] ?? 0) + 1;
      }
    }
    return counts;
  }, [allTasks]);

  return (
    <div className="space-y-6">
      <TasksPageHeader
        tasksCount={filteredTasks.length}
        selectedTaskLabel={selectedTaskLabel}
        realtimeStatus={realtime.status}
      />

      {/* Project scope selector — shared across tasks page */}
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
            const count = perProjectCounts[project.id] ?? 0;
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
