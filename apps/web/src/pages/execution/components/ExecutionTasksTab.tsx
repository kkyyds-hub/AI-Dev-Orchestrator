import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { useConsoleOverview } from "../../../features/console/hooks";
import type { ConsoleTask } from "../../../features/console/types";
import { useConsoleEventStream } from "../../../features/events/hooks";
import { buildRunRoute } from "../../../lib/run-route";
import { buildTaskRoute } from "../../../lib/task-route";
import { TaskDetailDrawer } from "../../tasks/components/TaskDetailDrawer";
import { TaskExecutionSituationPanel } from "../../tasks/components/TaskExecutionSituationPanel";
import { TaskQueueList } from "../../tasks/components/TaskQueueList";
import { useProjectScope } from "../../shared/useProjectScope";

type ExecutionTasksTabProps = {
  taskId: string | null;
  /** "execution" navigates relative to /execution, "tasks" relative to /tasks */
  sourceRoute: "execution" | "tasks";
};

export function ExecutionTasksTab({ taskId, sourceRoute }: ExecutionTasksTabProps) {
  const navigate = useNavigate();
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });
  const { selectedProjectId, setSelectedProjectId, projects, selectedProjectName, projectNotFound } =
    useProjectScope();

  const allTasks: ConsoleTask[] = overviewQuery.data?.tasks ?? [];

  const filteredTasks = useMemo(
    () =>
      selectedProjectId === "all"
        ? allTasks
        : allTasks.filter((task) => task.project_id === selectedProjectId),
    [allTasks, selectedProjectId],
  );

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

  const taskIdExists = useMemo(
    () =>
      !taskId || overviewQuery.isLoading
        ? null
        : filteredTasks.some((t) => t.id === taskId),
    [taskId, filteredTasks, overviewQuery.isLoading],
  );

  const projectIdForRoute = selectedProjectId === "all" ? null : selectedProjectId;

  const handleSelectTask = (nextTaskId: string) => {
    if (sourceRoute === "execution") {
      const params = new URLSearchParams({ tab: "tasks" });
      if (projectIdForRoute) params.set("projectId", projectIdForRoute);
      params.set("taskId", nextTaskId);
      navigate(`/execution?${params.toString()}`);
    } else {
      navigate(
        buildTaskRoute({ taskId: nextTaskId, from: "tasks", projectId: projectIdForRoute }),
      );
    }
  };

  const handleCloseDrawer = () => {
    if (sourceRoute === "execution") {
      const params = new URLSearchParams({ tab: "tasks" });
      if (projectIdForRoute) params.set("projectId", projectIdForRoute);
      navigate(`/execution?${params.toString()}`);
    } else {
      navigate(buildTaskRoute({ projectId: projectIdForRoute }));
    }
  };

  const handleClearTaskId = () => {
    if (sourceRoute === "execution") {
      const params = new URLSearchParams({ tab: "tasks" });
      if (projectIdForRoute) params.set("projectId", projectIdForRoute);
      navigate(`/execution?${params.toString()}`, { replace: true });
    } else {
      const q = projectIdForRoute ? `?projectId=${projectIdForRoute}` : "";
      navigate(`/tasks${q}`, { replace: true });
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
        projectId: projectId ?? projectIdForRoute,
      }),
    );
  };

  const handleNavigateToRepository = (
    nextTaskId: string,
    projectId: string | null,
  ) => {
    const pid = projectId ?? selectedProjectId;
    if (pid !== "all") {
      navigate(`/projects/${pid}/repository?taskId=${nextTaskId}`);
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
    <div className="space-y-4">
      {/* 任务摘要 */}
      <p className="text-sm text-zinc-500">
        待人工 {waitingHuman} / 阻塞 {blocked} / 执行中 {running} / 失败 {failed} / 已完成 {completed}
      </p>

      {/* 项目选择器 */}
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

      {/* 主体：任务队列 + 态势面板 + 抽屉 */}
      <ExecutionTasksLayout
        selectedTaskId={taskId}
        tasks={filteredTasks}
        onSelectTask={handleSelectTask}
        onNavigateToRun={handleNavigateToRun}
        onNavigateToRepository={handleNavigateToRepository}
        onCloseDrawer={handleCloseDrawer}
      />
    </div>
  );
}

/* ─── Layout (shared between /execution and /tasks) ─── */

function ExecutionTasksLayout({
  selectedTaskId,
  tasks,
  onSelectTask,
  onNavigateToRun,
  onNavigateToRepository,
  onCloseDrawer,
}: {
  selectedTaskId: string | null;
  tasks: ConsoleTask[];
  onSelectTask: (taskId: string) => void;
  onNavigateToRun: (runId: string, taskId: string, projectId: string | null) => void;
  onNavigateToRepository: (taskId: string, projectId: string | null) => void;
  onCloseDrawer: () => void;
}) {
  const selectedTask = selectedTaskId
    ? tasks.find((t) => t.id === selectedTaskId) ?? null
    : null;

  return (
    <>
      <div className="flex flex-col gap-5 xl:grid xl:grid-cols-[55fr_45fr] xl:items-start min-h-0">
        <div className="min-h-0 overflow-y-auto">
          <TaskQueueList
            tasks={tasks}
            selectedTaskId={selectedTaskId}
            onSelectTask={onSelectTask}
            onNavigateToRun={onNavigateToRun}
            onNavigateToRepository={onNavigateToRepository}
          />
        </div>
        <div className="min-h-0">
          <TaskExecutionSituationPanel
            tasks={tasks}
            onNavigateToRun={onNavigateToRun}
          />
        </div>
      </div>

      {selectedTask && (
        <TaskDetailDrawer
          task={selectedTask}
          onClose={onCloseDrawer}
          onNavigateToRun={onNavigateToRun}
          onNavigateToRepository={onNavigateToRepository}
        />
      )}
    </>
  );
}
