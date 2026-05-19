import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useConsoleOverview } from "../../features/console/hooks";
import type { ConsoleTask } from "../../features/console/types";
import { useConsoleEventStream } from "../../features/events/hooks";
import { buildRunRoute } from "../../lib/run-route";
import { buildTaskRoute } from "../../lib/task-route";
import { useProjectScope } from "../shared/useProjectScope";
import { TasksPageContent } from "./components/TasksPageContent";
import { TasksPageHeader } from "./components/TasksPageHeader";

export function TasksPage() {
  const navigate = useNavigate();
  const { taskId } = useParams();

  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });
  const { selectedProjectId, setSelectedProjectId, projects, selectedProjectName, projectNotFound } =
    useProjectScope();

  const allTasks: ConsoleTask[] = overviewQuery.data?.tasks ?? [];

  // ── Filter tasks by selected project ─────────────────────────────
  const filteredTasks = useMemo(
    () =>
      selectedProjectId === "all"
        ? allTasks
        : allTasks.filter((task) => task.project_id === selectedProjectId),
    [allTasks, selectedProjectId],
  );

  // ── Task counts ─────────────────────────────────────────────────
  const waitingHuman = useMemo(
    () => filteredTasks.filter((t) => t.status === "waiting_human").length,
    [filteredTasks],
  );
  const blocked = useMemo(
    () => filteredTasks.filter((t) => t.status === "blocked").length,
    [filteredTasks],
  );
  const running = useMemo(
    () => filteredTasks.filter((t) => t.status === "running").length,
    [filteredTasks],
  );
  const failed = useMemo(
    () => filteredTasks.filter((t) => t.status === "failed").length,
    [filteredTasks],
  );
  const completed = useMemo(
    () => filteredTasks.filter((t) => t.status === "completed").length,
    [filteredTasks],
  );

  // ── TaskId hit / miss ────────────────────────────────────────────
  const taskIdExists = useMemo(
    () =>
      !taskId || overviewQuery.isLoading
        ? null  // null = unknown / not relevant
        : filteredTasks.some((t) => t.id === taskId),
    [taskId, filteredTasks, overviewQuery.isLoading],
  );

  // ── Navigation ──────────────────────────────────────────────────
  const handleSelectTask = (nextTaskId: string) => {
    navigate(
      buildTaskRoute({
        taskId: nextTaskId,
        from: "tasks",
        projectId: selectedProjectId === "all" ? null : selectedProjectId,
      }),
    );
  };

  const handleCloseDrawer = () => {
    navigate(
      buildTaskRoute({
        projectId: selectedProjectId === "all" ? null : selectedProjectId,
      }),
    );
  };

  const handleClearTaskId = () => {
    if (selectedProjectId !== "all") {
      navigate(`/tasks?projectId=${selectedProjectId}`, { replace: true });
    } else {
      navigate("/tasks", { replace: true });
    }
  };

  const handleNavigateToRun = (
    runId: string,
    nextTaskId: string,
    projectId: string | null,
  ) => {
    navigate(
      buildRunRoute({
        runId,
        taskId: nextTaskId,
        from: "tasks",
        projectId: projectId ?? (selectedProjectId === "all" ? null : selectedProjectId),
      }),
    );
  };

  const handleNavigateToRepository = (
    nextTaskId: string,
    projectId: string | null,
  ) => {
    const targetProjectId = projectId ?? selectedProjectId;
    if (targetProjectId !== "all") {
      navigate(`/projects/${targetProjectId}/repository?taskId=${nextTaskId}`);
    }
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
    <div className="relative min-w-0 space-y-5">
      <TasksPageHeader
        waitingHuman={waitingHuman}
        blocked={blocked}
        running={running}
        failed={failed}
        completed={completed}
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

      {projectNotFound ? (
        <div className="rounded border border-zinc-700 px-4 py-3 text-sm text-zinc-400">
          当前项目不存在或已被删除。{" "}
          <button
            type="button"
            onClick={() => setSelectedProjectId("all")}
            className="underline transition hover:text-zinc-200"
          >
            切回全部项目
          </button>
        </div>
      ) : null}

      {/* taskId 未命中提示 */}
      {taskIdExists === false && (
        <div className="rounded border border-zinc-700 px-4 py-3 text-sm text-zinc-400 flex items-center justify-between">
          <span>未命中任务</span>
          <button
            type="button"
            onClick={handleClearTaskId}
            className="rounded border border-[#444444] px-3 py-1 text-xs text-zinc-300 transition hover:border-zinc-400 hover:bg-[#222222]"
          >
            清除选择
          </button>
        </div>
      )}

      <TasksPageContent
        selectedTaskId={taskId ?? null}
        tasks={filteredTasks}
        onSelectTask={handleSelectTask}
        onNavigateToRun={handleNavigateToRun}
        onNavigateToRepository={handleNavigateToRepository}
        onCloseDrawer={handleCloseDrawer}
      />
    </div>
  );
}
