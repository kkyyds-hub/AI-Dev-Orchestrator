import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { useConsoleOverview } from "../../../features/console/hooks";
import type { ConsoleTask } from "../../../features/console/types";
import { useConsoleEventStream } from "../../../features/events/hooks";
import { useProjectDetail } from "../../../features/projects/hooks";
import { collectProjectDirectorSource } from "../../../features/projects/lib/projectDirectorSource";
import { buildRunRoute } from "../../../lib/run-route";
import { buildTaskRoute } from "../../../lib/task-route";
import {
  usePauseTask,
  useRequestHumanReview,
  useResolveHumanReview,
  useResumeTask,
  useRetryTask,
} from "../../../features/task-actions/hooks";
import { TaskDetailDrawer } from "../../tasks/components/TaskDetailDrawer";
import { TaskExecutionSituationPanel } from "../../tasks/components/TaskExecutionSituationPanel";
import { TaskQueueList } from "../../tasks/components/TaskQueueList";
import { useProjectScope } from "../../shared/useProjectScope";

type ExecutionTasksTabProps = {
  taskId: string | null;
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

  // Task action mutations
  const pauseMutation = usePauseTask();
  const resumeMutation = useResumeTask();
  const requestHumanMutation = useRequestHumanReview();
  const resolveHumanMutation = useResolveHumanReview();
  const retryMutation = useRetryTask();

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
  const projectDetailQuery = useProjectDetail(projectIdForRoute);
  const selectedProject = useMemo(
    () =>
      selectedProjectId === "all"
        ? null
        : projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );
  const directorSource = useMemo(
    () =>
      selectedProjectId === "all"
        ? null
        : collectProjectDirectorSource({
            items: [
              selectedProject,
              projectDetailQuery.data,
              ...(projectDetailQuery.data?.tasks ?? []),
              ...filteredTasks,
            ],
          }),
    [filteredTasks, projectDetailQuery.data, selectedProject, selectedProjectId],
  );

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

  // Task action handlers
  const handlePause = (targetId: string) => pauseMutation.mutate(targetId);
  const handleResume = (targetId: string) => resumeMutation.mutate(targetId);
  const handleRequestHuman = (targetId: string) => requestHumanMutation.mutate(targetId);
  const handleResolveHuman = (targetId: string) => resolveHumanMutation.mutate(targetId);
  const handleRetry = (targetId: string) => retryMutation.mutate(targetId);

  const mkState = (m: { isPending: boolean; isError: boolean; error: Error | null }) => ({
    isPending: m.isPending,
    isError: m.isError,
    errorMessage: m.isError ? m.error?.message ?? null : null,
  });

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
      {/* 顶部工具栏：任务摘要 + 项目选择器 一行化 */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-zinc-500">
          待人工 {waitingHuman} / 阻塞 {blocked} / 执行中 {running} / 失败 {failed} / 已完成 {completed}
        </span>
        <span className="text-zinc-700">|</span>
        <select
          value={selectedProjectId}
          onChange={(event) => setSelectedProjectId(event.target.value)}
          className="min-w-0 rounded border border-[#333333] bg-[#1a1a1a] px-2.5 py-1 text-xs text-zinc-300 outline-none focus:border-zinc-500"
        >
          <option value="all" className="bg-[#161616]">
            全部项目 ({allTasks.length})
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

      {directorSource ? (
        <div
          data-testid="execution-project-director-source-readback"
          className="rounded border border-cyan-500/25 bg-cyan-500/5 px-4 py-3"
        >
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm font-medium text-cyan-100">
                执行中心读回：AI 主管草案来源
              </p>
              <p className="mt-1 text-xs leading-5 text-cyan-100/75">
                当前项目任务队列来自已审核草案；此处仅展示来源，不代表 Agent/Skill/仓库/验证机制已经真实执行。
              </p>
            </div>
            <div className="grid gap-1 text-xs text-zinc-400 lg:min-w-[320px]">
              <span className="break-all font-mono">
                source_plan_version_id: {directorSource.sourcePlanVersionId}
              </span>
              <span className="break-all font-mono">
                source_draft_id:{" "}
                {directorSource.sourceDraftIds.length > 0
                  ? directorSource.sourceDraftIds.join(", ")
                  : "后端未返回"}
              </span>
            </div>
          </div>
          <p className="mt-2 text-xs leading-5 text-cyan-100/70">
            未自动创建 Agent Session / Skill 绑定 / 仓库绑定 / Run，也未触发 provider、Worker、planning/apply、apply-local 或产品内 git-commit。
          </p>
        </div>
      ) : null}

      {taskIdExists === false && (
        <div className="rounded border border-zinc-700 px-3 py-2 text-xs text-zinc-400 flex items-center justify-between">
          <span>未命中任务</span>
          <button
            type="button"
            onClick={handleClearTaskId}
            className="rounded border border-[#444444] px-2 py-0.5 text-[10px] text-zinc-300 transition hover:border-zinc-400 hover:bg-[#222222]"
          >
            清除选择
          </button>
        </div>
      )}

      {/* 主体工作区：固定高度，左侧滚动，右侧 sticky */}
      <ExecutionTasksLayout
        selectedTaskId={taskId}
        tasks={filteredTasks}
        onSelectTask={handleSelectTask}
        onNavigateToRun={handleNavigateToRun}
        onNavigateToRepository={handleNavigateToRepository}
        onCloseDrawer={handleCloseDrawer}
        onPause={handlePause}
        onResume={handleResume}
        onRequestHuman={handleRequestHuman}
        onResolveHuman={handleResolveHuman}
        onRetry={handleRetry}
        pauseState={mkState(pauseMutation)}
        resumeState={mkState(resumeMutation)}
        requestHumanState={mkState(requestHumanMutation)}
        resolveHumanState={mkState(resolveHumanMutation)}
        retryState={mkState(retryMutation)}
      />
    </div>
  );
}

/* ─── Layout ─── */

type ActionState = { isPending: boolean; isError: boolean; errorMessage: string | null };

function ExecutionTasksLayout({
  selectedTaskId,
  tasks,
  onSelectTask,
  onNavigateToRun,
  onNavigateToRepository,
  onCloseDrawer,
  onPause, onResume, onRequestHuman, onResolveHuman, onRetry,
  pauseState, resumeState, requestHumanState, resolveHumanState, retryState,
}: {
  selectedTaskId: string | null;
  tasks: ConsoleTask[];
  onSelectTask: (taskId: string) => void;
  onNavigateToRun: (runId: string, taskId: string, projectId: string | null) => void;
  onNavigateToRepository: (taskId: string, projectId: string | null) => void;
  onCloseDrawer: () => void;
  onPause: (taskId: string) => void;
  onResume: (taskId: string) => void;
  onRequestHuman: (taskId: string) => void;
  onResolveHuman: (taskId: string) => void;
  onRetry: (taskId: string) => void;
  pauseState: ActionState;
  resumeState: ActionState;
  requestHumanState: ActionState;
  resolveHumanState: ActionState;
  retryState: ActionState;
}) {
  const selectedTask = selectedTaskId
    ? tasks.find((t) => t.id === selectedTaskId) ?? null
    : null;

  return (
    <>
      {/*
        Fixed-height work area: left scrolls, right is sticky.
        h-[calc(100vh-260px)] keeps the workspace stable regardless of task count.
      */}
      <div className="hidden xl:grid xl:grid-cols-[55fr_45fr] xl:gap-5"
           style={{ height: "calc(100vh - 260px)" }}>
        {/* 左侧：任务队列 — 内部滚动 */}
        <div className="min-h-0 overflow-y-auto pr-1">
          <TaskQueueList
            tasks={tasks}
            selectedTaskId={selectedTaskId}
            onSelectTask={onSelectTask}
            onNavigateToRun={onNavigateToRun}
            onNavigateToRepository={onNavigateToRepository}
          />
        </div>

        {/* 右侧：态势面板 — sticky 顶部 */}
        <div className="min-h-0">
          <div className="sticky top-0">
            <TaskExecutionSituationPanel
              tasks={tasks}
              onNavigateToRun={onNavigateToRun}
            />
          </div>
        </div>
      </div>

      {/* Mobile: stack vertically */}
      <div className="xl:hidden flex flex-col gap-5">
        <TaskQueueList
          tasks={tasks}
          selectedTaskId={selectedTaskId}
          onSelectTask={onSelectTask}
          onNavigateToRun={onNavigateToRun}
          onNavigateToRepository={onNavigateToRepository}
        />
        <TaskExecutionSituationPanel
          tasks={tasks}
          onNavigateToRun={onNavigateToRun}
        />
      </div>

      {selectedTask && (
        <TaskDetailDrawer
          task={selectedTask}
          onClose={onCloseDrawer}
          onNavigateToRun={onNavigateToRun}
          onNavigateToRepository={onNavigateToRepository}
          onPause={onPause}
          onResume={onResume}
          onRequestHuman={onRequestHuman}
          onResolveHuman={onResolveHuman}
          onRetry={onRetry}
          pauseState={pauseState}
          resumeState={resumeState}
          requestHumanState={requestHumanState}
          resolveHumanState={resolveHumanState}
          retryState={retryState}
        />
      )}
    </>
  );
}
