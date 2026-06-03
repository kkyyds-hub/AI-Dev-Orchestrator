import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useBackendHealth, useConsoleOverview } from "../../features/console/hooks";
import type { ConsoleOverview } from "../../features/console/types";
import { useConsoleEventStream } from "../../features/events/hooks";
import { useRunWorkerOnce } from "../../features/task-actions/hooks";
import { formatDateTime } from "../../lib/format";
import { buildTaskRoute } from "../../lib/task-route";
import { useProjectScope } from "../shared/useProjectScope";
import { DirectorChatEntry } from "./components/DirectorChatEntry";
import { WorkbenchHeader } from "./components/WorkbenchHeader";
import { WorkbenchRightRail } from "./components/WorkbenchRightRail";

const WORKBENCH_CONTEXT_MODE_STORAGE_KEY =
  "ai-dev-orchestrator:workbench-context-mode";

function readStoredWorkbenchMode(): WorkbenchContextMode | null {
  try {
    const value = localStorage.getItem(WORKBENCH_CONTEXT_MODE_STORAGE_KEY);
    return value === "new-project" || value === "project" ? value : null;
  } catch {
    return null;
  }
}

function writeStoredWorkbenchMode(mode: WorkbenchContextMode) {
  try {
    localStorage.setItem(WORKBENCH_CONTEXT_MODE_STORAGE_KEY, mode);
  } catch {
    // storage unavailable — ignore
  }
}

export function WorkbenchPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const realtime = useConsoleEventStream();
  const overviewQuery = useConsoleOverview({
    enablePollingFallback: realtime.status !== "open",
  });
  const healthQuery = useBackendHealth();
  const {
    selectedProjectId,
    selectedProjectName,
    setSelectedProjectId,
    projects,
    projectsLoading,
    projectNotFound,
  } = useProjectScope();
  const runWorkerOnceMutation = useRunWorkerOnce();
  const [stableOverviewData, setStableOverviewData] = useState(overviewQuery.data);
  const [refreshNotice, setRefreshNotice] = useState<string | null>(null);
  const [workbenchMode, setWorkbenchMode] = useState<WorkbenchContextMode>(() =>
    searchParams.get("mode") === "new-project"
      ? "new-project"
      : (readStoredWorkbenchMode() ?? "project"),
  );

  useEffect(() => {
    if (overviewQuery.data) {
      setStableOverviewData(overviewQuery.data);
    }
  }, [overviewQuery.data]);

  useEffect(() => {
    if (!refreshNotice) {
      return;
    }

    const timer = window.setTimeout(() => {
      setRefreshNotice(null);
    }, 1800);

    return () => window.clearTimeout(timer);
  }, [refreshNotice]);

  useEffect(() => {
    const urlMode =
      searchParams.get("mode") === "new-project"
        ? "new-project"
        : (readStoredWorkbenchMode() ?? "project");
    setWorkbenchMode((current) => (current === urlMode ? current : urlMode));
  }, [searchParams]);

  useEffect(() => {
    writeStoredWorkbenchMode(workbenchMode);
  }, [workbenchMode]);

  useEffect(() => {
    if (workbenchMode !== "new-project" || selectedProjectId === "all") {
      return;
    }
    setSelectedProjectId("all");
  }, [selectedProjectId, setSelectedProjectId, workbenchMode]);

  const lastUpdatedText = useMemo(() => {
    if (!overviewQuery.dataUpdatedAt && !stableOverviewData) {
      return "暂未刷新";
    }
    return formatDateTime(
      new Date(overviewQuery.dataUpdatedAt || Date.now()).toISOString(),
    );
  }, [overviewQuery.dataUpdatedAt, stableOverviewData]);

  const overviewIsInitialLoading =
    !stableOverviewData && (overviewQuery.isLoading || overviewQuery.isFetching);
  const activeProjectId = workbenchMode === "new-project" ? null : selectedProjectId;
  const activeProjectName =
    workbenchMode === "new-project" ? "新项目会话" : selectedProjectName;
  const visibleOverviewData = useMemo(
    () => filterOverviewByProject(stableOverviewData, activeProjectId, workbenchMode),
    [activeProjectId, stableOverviewData, workbenchMode],
  );

  const handleRefresh = async () => {
    setRefreshNotice("正在手动刷新...");

    try {
      await Promise.all([overviewQuery.refetch(), healthQuery.refetch()]);
      setRefreshNotice("已刷新最新状态");
    } catch {
      setRefreshNotice("刷新失败，请稍后重试");
    }
  };

  const handleNavigateToTask = (taskId: string, projectId?: string | null) => {
    const fallbackProjectId =
      workbenchMode === "project" && selectedProjectId !== "all"
        ? selectedProjectId
        : null;

    navigate(
      buildTaskRoute({
        taskId,
        from: "workbench",
        projectId: projectId ?? fallbackProjectId,
      }),
    );
  };

  const handleNavigateToTasks = () => {
    if (workbenchMode === "project" && selectedProjectId !== "all") {
      navigate(`/tasks?projectId=${selectedProjectId}`);
    } else {
      navigate("/tasks");
    }
  };

  const handleNavigateToProjects = () => {
    if (workbenchMode === "project" && selectedProjectId !== "all") {
      navigate(`/projects?projectId=${selectedProjectId}`);
    } else {
      navigate("/projects");
    }
  };

  const handleNavigateToRuns = () => {
    if (workbenchMode === "project" && selectedProjectId !== "all") {
      navigate(`/runs?projectId=${selectedProjectId}`);
    } else {
      navigate("/runs");
    }
  };

  const handleSelectWorkbenchContext = (nextValue: string) => {
    if (nextValue === NEW_PROJECT_CONTEXT_VALUE) {
      setWorkbenchMode("new-project");
      writeStoredWorkbenchMode("new-project");
      setSelectedProjectId("all");
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("mode", "new-project");
      nextParams.delete("projectId");
      navigate({ pathname: "/workbench", search: nextParams.toString() }, { replace: false });
      return;
    }

    setWorkbenchMode("project");
    writeStoredWorkbenchMode("project");
    const nextProjectId = nextValue || "all";
    setSelectedProjectId(nextProjectId);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("mode");
    if (nextProjectId === "all") {
      nextParams.delete("projectId");
    } else {
      nextParams.set("projectId", nextProjectId);
    }
    navigate({ pathname: "/workbench", search: nextParams.toString() }, { replace: false });
  };

  const handleRightRailRunWorkerOnce = () => {
    if (workbenchMode === "new-project") {
      return;
    }

    runWorkerOnceMutation.mutate(
      activeProjectId === null || activeProjectId === "all" ? null : activeProjectId,
    );
  };

  const rightRailRunWorkerOnceDisabledReason =
    workbenchMode === "new-project"
      ? "新项目会话尚未创建正式项目，右侧 run-once 已禁用。"
      : null;

  return (
    <div className="relative min-w-0 space-y-6">
      <WorkbenchHeader
        backendStatus={healthQuery.data?.status}
        realtimeStatus={realtime.status}
        lastUpdatedText={lastUpdatedText}
        selectedProjectName={activeProjectName}
        selectedProjectId={activeProjectId ?? "new-project"}
        mode={workbenchMode}
        projects={projects}
        projectsLoading={projectsLoading}
        projectNotFound={workbenchMode === "project" && projectNotFound}
        onSelectContext={handleSelectWorkbenchContext}
      />

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <div className="flex-1 lg:min-w-0">
          <DirectorChatEntry
            selectedProjectId={activeProjectId}
            selectedProjectName={activeProjectName}
            mode={workbenchMode}
          />
        </div>

        <div className="w-full shrink-0 lg:w-72 xl:w-80">
          <WorkbenchRightRail
            overviewData={visibleOverviewData}
            overviewIsInitialLoading={overviewIsInitialLoading}
            refreshNotice={refreshNotice}
            selectedProjectId={activeProjectId ?? "new-project"}
            onRefresh={() => {
              void handleRefresh();
            }}
            onNavigateToTasks={handleNavigateToTasks}
            onNavigateToTask={handleNavigateToTask}
            onNavigateToProjects={handleNavigateToProjects}
            onNavigateToRuns={handleNavigateToRuns}
            isRunWorkerOncePending={runWorkerOnceMutation.isPending}
            runWorkerOnceDisabledReason={rightRailRunWorkerOnceDisabledReason}
            onRunWorkerOnce={handleRightRailRunWorkerOnce}
            workerOnceData={
              workbenchMode === "new-project" ? null : runWorkerOnceMutation.data
            }
            workerOnceIsError={
              workbenchMode === "new-project" ? false : runWorkerOnceMutation.isError
            }
            workerOnceErrorMessage={
              workbenchMode !== "new-project" && runWorkerOnceMutation.isError
                ? runWorkerOnceMutation.error.message
                : null
            }
          />
        </div>
      </div>
    </div>
  );
}

const NEW_PROJECT_CONTEXT_VALUE = "new-project";

type WorkbenchContextMode = "new-project" | "project";

function filterOverviewByProject(
  overviewData: ConsoleOverview | undefined,
  selectedProjectId: string | null,
  mode: WorkbenchContextMode,
): ConsoleOverview | undefined {
  if (!overviewData) {
    return overviewData;
  }

  if (mode === "new-project") {
    return buildScopedOverview(overviewData, []);
  }

  if (selectedProjectId === null || selectedProjectId === "all") {
    return overviewData;
  }

  const tasks = overviewData.tasks.filter((task) => task.project_id === selectedProjectId);
  return buildScopedOverview(overviewData, tasks);
}

function buildScopedOverview(
  overviewData: ConsoleOverview,
  tasks: ConsoleOverview["tasks"],
): ConsoleOverview {
  const countByStatus = (status: string) =>
    tasks.filter((task) => task.status === status).length;

  return {
    ...overviewData,
    total_tasks: tasks.length,
    pending_tasks: countByStatus("pending"),
    running_tasks: countByStatus("running"),
    paused_tasks: countByStatus("paused"),
    waiting_human_tasks: countByStatus("waiting_human"),
    completed_tasks: countByStatus("completed"),
    failed_tasks: countByStatus("failed"),
    blocked_tasks: countByStatus("blocked"),
    total_estimated_cost: tasks.reduce(
      (sum, task) => sum + (task.latest_run?.estimated_cost ?? 0),
      0,
    ),
    total_prompt_tokens: tasks.reduce(
      (sum, task) => sum + (task.latest_run?.prompt_tokens ?? 0),
      0,
    ),
    total_completion_tokens: tasks.reduce(
      (sum, task) => sum + (task.latest_run?.completion_tokens ?? 0),
      0,
    ),
    tasks,
  };
}
