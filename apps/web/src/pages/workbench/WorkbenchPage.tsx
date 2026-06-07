import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useBackendHealth, useConsoleOverview } from "../../features/console/hooks";
import type { ConsoleOverview } from "../../features/console/types";
import { useConsoleEventStream } from "../../features/events/hooks";
import { useRunWorkerOnce } from "../../features/task-actions/hooks";
import { useProjectDirectorWorkbenchResumableSessions } from "../../features/project-director/hooks";
import { formatDateTime } from "../../lib/format";
import { buildTaskRoute } from "../../lib/task-route";
import { useProjectScope } from "../shared/useProjectScope";
import { DirectorChatEntry } from "./components/DirectorChatEntry";
import { ProjectDirectorConversationList } from "./components/ProjectDirectorConversationList";
import {
  parseDirectorSessionOptionValue,
  WorkbenchHeader,
} from "./components/WorkbenchHeader";
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
  const resumableSessionsQuery = useProjectDirectorWorkbenchResumableSessions();
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
  const [selectedDirectorSessionId, setSelectedDirectorSessionId] = useState<
    string | null
  >(() => searchParams.get("directorSessionId"));
  const resumableSessions = resumableSessionsQuery.data?.sessions ?? [];
  const selectedDirectorSession = selectedDirectorSessionId
    ? resumableSessions.find(
        (session) => session.session_id === selectedDirectorSessionId,
      ) ?? null
    : null;
  const directorSessionUrlProjectId = selectedDirectorSessionId
    ? searchParams.get("projectId")
    : null;
  const activeWorkbenchMode: WorkbenchContextMode = selectedDirectorSessionId
    ? selectedDirectorSession?.project_id || directorSessionUrlProjectId
      ? "project"
      : "new-project"
    : workbenchMode;

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
    setSelectedDirectorSessionId(searchParams.get("directorSessionId"));
  }, [searchParams]);

  useEffect(() => {
    writeStoredWorkbenchMode(workbenchMode);
  }, [workbenchMode]);

  useEffect(() => {
    if (
      activeWorkbenchMode !== "new-project" ||
      selectedDirectorSessionId ||
      selectedProjectId === "all"
    ) {
      return;
    }
    setSelectedProjectId("all");
  }, [
    activeWorkbenchMode,
    selectedDirectorSessionId,
    selectedProjectId,
    setSelectedProjectId,
  ]);

  useEffect(() => {
    if (
      selectedDirectorSessionId ||
      workbenchMode !== "project" ||
      selectedProjectId !== "all" ||
      projects.length === 0
    ) {
      return;
    }
    setSelectedProjectId(projects[0].id);
  }, [
    projects,
    selectedDirectorSessionId,
    selectedProjectId,
    setSelectedProjectId,
    workbenchMode,
  ]);

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
  const activeProjectId = selectedDirectorSessionId
    ? selectedDirectorSession?.project_id ?? directorSessionUrlProjectId
    : activeWorkbenchMode === "new-project"
      ? null
      : selectedProjectId;
  const activeProjectName =
    selectedDirectorSessionId
      ? selectedDirectorSession?.project_name ?? "未完成 AI 主管会话"
      : activeWorkbenchMode === "new-project"
        ? "新项目会话"
        : selectedProjectName;
  const visibleOverviewData = useMemo(
    () =>
      filterOverviewByProject(
        stableOverviewData,
        activeProjectId,
        activeWorkbenchMode,
      ),
    [activeProjectId, activeWorkbenchMode, stableOverviewData],
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
      activeWorkbenchMode === "project" && activeProjectId && activeProjectId !== "all"
        ? activeProjectId
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
    if (activeWorkbenchMode === "project" && activeProjectId && activeProjectId !== "all") {
      navigate(`/tasks?projectId=${activeProjectId}`);
    } else {
      navigate("/tasks");
    }
  };

  const handleNavigateToProjects = () => {
    if (activeWorkbenchMode === "project" && activeProjectId && activeProjectId !== "all") {
      navigate(`/projects?projectId=${activeProjectId}`);
    } else {
      navigate("/projects");
    }
  };

  const handleNavigateToRuns = () => {
    if (activeWorkbenchMode === "project" && activeProjectId && activeProjectId !== "all") {
      navigate(`/runs?projectId=${activeProjectId}`);
    } else {
      navigate("/runs");
    }
  };

  const handleSelectWorkbenchContext = (nextValue: string) => {
    const directorSessionId = parseDirectorSessionOptionValue(nextValue);
    if (directorSessionId) {
      const session = resumableSessions.find(
        (item) => item.session_id === directorSessionId,
      );
      const nextMode: WorkbenchContextMode = session?.project_id
        ? "project"
        : "new-project";
      setSelectedDirectorSessionId(directorSessionId);
      setWorkbenchMode(nextMode);
      writeStoredWorkbenchMode(nextMode);
      setSelectedProjectId(session?.project_id ?? "all");
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("directorSessionId", directorSessionId);
      if (nextMode === "new-project") {
        nextParams.set("mode", "new-project");
        nextParams.delete("projectId");
      } else {
        nextParams.delete("mode");
        if (session?.project_id) {
          nextParams.set("projectId", session.project_id);
        }
      }
      navigate({ pathname: "/workbench", search: nextParams.toString() }, { replace: false });
      return;
    }

    if (nextValue === NEW_PROJECT_CONTEXT_VALUE) {
      setSelectedDirectorSessionId(null);
      setWorkbenchMode("new-project");
      writeStoredWorkbenchMode("new-project");
      setSelectedProjectId("all");
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("mode", "new-project");
      nextParams.delete("projectId");
      nextParams.delete("directorSessionId");
      navigate({ pathname: "/workbench", search: nextParams.toString() }, { replace: false });
      return;
    }

    if (!nextValue) {
      return;
    }

    setSelectedDirectorSessionId(null);
    setWorkbenchMode("project");
    writeStoredWorkbenchMode("project");
    const nextProjectId = nextValue;
    setSelectedProjectId(nextProjectId);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("mode");
    nextParams.delete("directorSessionId");
    nextParams.set("projectId", nextProjectId);
    navigate({ pathname: "/workbench", search: nextParams.toString() }, { replace: false });
  };

  const handleSelectDirectorConversation = (conversation: {
    conversation_id: string;
    project_id: string | null;
  }) => {
    const nextMode: WorkbenchContextMode = conversation.project_id
      ? "project"
      : "new-project";
    setSelectedDirectorSessionId(conversation.conversation_id);
    setWorkbenchMode(nextMode);
    writeStoredWorkbenchMode(nextMode);
    setSelectedProjectId(conversation.project_id ?? "all");

    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("directorSessionId", conversation.conversation_id);
    if (nextMode === "new-project") {
      nextParams.set("mode", "new-project");
      nextParams.delete("projectId");
    } else {
      nextParams.delete("mode");
      if (conversation.project_id) {
        nextParams.set("projectId", conversation.project_id);
      }
    }
    navigate({ pathname: "/workbench", search: nextParams.toString() }, { replace: false });
  };

  const handleRightRailRunWorkerOnce = () => {
    if (activeWorkbenchMode === "new-project") {
      return;
    }

    runWorkerOnceMutation.mutate(
      activeProjectId === null || activeProjectId === "all" ? null : activeProjectId,
    );
  };

  const rightRailRunWorkerOnceDisabledReason =
    activeWorkbenchMode === "new-project"
      ? "新项目会话尚未创建正式项目，右侧 run-once 已禁用。"
      : null;

  return (
    <div className="relative flex h-[calc(100vh-7rem)] min-w-0 flex-col gap-6 overflow-hidden">
      <WorkbenchHeader
        backendStatus={healthQuery.data?.status}
        realtimeStatus={realtime.status}
        lastUpdatedText={lastUpdatedText}
        selectedProjectName={activeProjectName}
        selectedProjectId={activeProjectId ?? "new-project"}
        mode={activeWorkbenchMode}
        selectedDirectorSessionId={selectedDirectorSessionId}
        resumableSessions={resumableSessions}
        resumableSessionsLoading={resumableSessionsQuery.isLoading}
        projects={projects}
        projectsLoading={projectsLoading}
        projectNotFound={
          !selectedDirectorSessionId && activeWorkbenchMode === "project" && projectNotFound
        }
        onSelectContext={handleSelectWorkbenchContext}
      />

      <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-hidden lg:flex-row lg:items-stretch">
        <div className="flex min-h-0 flex-1 flex-col gap-4 lg:min-w-0">
          <ProjectDirectorConversationList
            projectId={
              activeWorkbenchMode === "project" &&
              activeProjectId &&
              activeProjectId !== "all"
                ? activeProjectId
                : null
            }
            selectedConversationId={selectedDirectorSessionId}
            onSelectConversation={handleSelectDirectorConversation}
          />
          <div className="min-h-0 flex-1">
            <DirectorChatEntry
              selectedProjectId={activeProjectId}
              selectedProjectName={activeProjectName}
              mode={activeWorkbenchMode}
              resumeSessionId={selectedDirectorSessionId}
            />
          </div>
        </div>

        <div className="min-h-0 w-full shrink-0 lg:w-72 xl:w-80">
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
              activeWorkbenchMode === "new-project" ? null : runWorkerOnceMutation.data
            }
            workerOnceIsError={
              activeWorkbenchMode === "new-project" ? false : runWorkerOnceMutation.isError
            }
            workerOnceErrorMessage={
              activeWorkbenchMode !== "new-project" && runWorkerOnceMutation.isError
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
