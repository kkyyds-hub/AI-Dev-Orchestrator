import { useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useProjectApprovalInbox } from "../../features/approvals/hooks";
import { useProjectDeliverableSnapshot } from "../../features/deliverables/hooks";
import {
  useProjectDirectorAgentTeamConfig,
  useProjectDirectorRepositoryBindingConfig,
  useProjectDirectorSetupReadiness,
  useProjectDirectorSkillBindingConfig,
  useProjectDirectorVerificationConfig,
  useProjectDirectorWorkbenchResumableSessions,
} from "../../features/project-director/hooks";
import {
  useProjectDetail,
  useProjectMemoryGovernanceState,
  useProjectMemorySnapshot,
} from "../../features/projects/hooks";
import {
  useProjectChangeSession,
  useProjectRepositoryVerificationBaseline,
  useProjectRepositorySnapshot,
} from "../../features/repositories/hooks";
import { useProjectRoleCatalog, useProjectRoleSkillConsumption, useSystemRoleCatalog } from "../../features/roles/hooks";
import { useProjectSkillBindings, useSkillRegistry } from "../../features/skills/hooks";
import { ProjectDirectorWorkbenchSurface } from "../../features/workbench/ProjectDirectorWorkbenchSurface";
import { WorkbenchExperience } from "../../features/workbench/WorkbenchExperience";
import type {
  WorkbenchDirectorSurfaceContext,
  WorkbenchInitialModal,
  WorkbenchMainPageKey,
} from "../../features/workbench/WorkbenchExperience";
import { buildRealWorkbenchProjectGroups } from "../../features/workbench/adapters/realWorkbenchAdapter";
import {
  fetchWorkbenchTask,
  fetchWorkbenchRunLogs,
  fetchWorkbenchTaskRuns,
  fetchWorkbenchTasks,
} from "../../features/workbench/adapters/realWorkbenchSurfaceApi";
import { buildWorkbenchSurfaceData } from "../../features/workbench/adapters/realWorkbenchSurfaceAdapter";
import { useProjectScope } from "../shared/useProjectScope";
import { WorkbenchActionInbox } from "./components/WorkbenchActionInbox";
import {
  WorkbenchActionToast,
  type WorkbenchActionToastState,
  type WorkbenchActionToastStatus,
} from "./components/WorkbenchActionToast";
import { WorkbenchRepositoryBindingPanel } from "./components/WorkbenchRepositoryBindingPanel";
import { useWorkbenchSettingsAdapters } from "./useWorkbenchSettingsAdapters";

type WorkbenchPageProps = {
  initialMainPage?: WorkbenchMainPageKey | null;
  initialModal?: WorkbenchInitialModal | null;
};

const WORKBENCH_SURFACES: readonly WorkbenchMainPageKey[] = [
  "projects",
  "execution",
  "deliverables",
  "repository",
  "governance",
];

function parseWorkbenchSurface(value: string | null): WorkbenchMainPageKey | null {
  return WORKBENCH_SURFACES.includes(value as WorkbenchMainPageKey)
    ? (value as WorkbenchMainPageKey)
    : null;
}

export function WorkbenchPage({
  initialMainPage = null,
  initialModal = null,
}: WorkbenchPageProps = {}) {
  const navigate = useNavigate();
  const params = useParams();
  const [searchParams] = useSearchParams();
  const [toast, setToast] = useState<WorkbenchActionToastState | null>(null);
  const resumableSessionsQuery = useProjectDirectorWorkbenchResumableSessions();
  const {
    selectedProjectId,
    selectedProjectName,
    setSelectedProjectId,
    projects,
  } = useProjectScope();

  const urlProjectId = searchParams.get("projectId");
  const routeProjectId = params.projectId ?? null;
  const routeSurface = parseWorkbenchSurface(searchParams.get("surface"));
  const urlMode = searchParams.get("mode") === "new-project" ? "new-project" : null;
  const formalProjectId =
    urlProjectId ??
    routeProjectId ??
    (selectedProjectId && selectedProjectId !== "all" ? selectedProjectId : null);
  const formalProjectName =
    projects.find((project) => project.id === formalProjectId)?.name ??
    selectedProjectName ??
    "新项目会话";
  const surfaceProjectId =
    formalProjectId ?? (initialMainPage ? projects[0]?.id ?? null : null);
  const surfaceProjectName =
    projects.find((project) => project.id === surfaceProjectId)?.name ??
    formalProjectName;
  const projectDetailQuery = useProjectDetail(surfaceProjectId);
  const tasksQuery = useQuery({
    queryKey: ["workbench-surface", "tasks"],
    queryFn: fetchWorkbenchTasks,
    retry: false,
  });
  const scopedTasks = useMemo(
    () =>
      surfaceProjectId
        ? (tasksQuery.data ?? []).filter((task) => task.project_id === surfaceProjectId)
        : tasksQuery.data ?? [],
    [surfaceProjectId, tasksQuery.data],
  );
  const executionTaskId =
    scopedTasks.find((task) => task.status === "running")?.id ??
    scopedTasks.find((task) => task.human_status && task.human_status !== "none")?.id ??
    scopedTasks[0]?.id ??
    null;
  const selectedTaskQuery = useQuery({
    queryKey: ["workbench-surface", "task-detail", executionTaskId],
    queryFn: () => fetchWorkbenchTask(executionTaskId as string),
    enabled: Boolean(executionTaskId),
    retry: false,
  });
  const taskRunsQuery = useQuery({
    queryKey: ["workbench-surface", "task-runs", executionTaskId],
    queryFn: () => fetchWorkbenchTaskRuns(executionTaskId as string),
    enabled: Boolean(executionTaskId),
    retry: false,
  });
  const executionRunId = taskRunsQuery.data?.[0]?.id ?? null;
  const runLogsQuery = useQuery({
    queryKey: ["workbench-surface", "run-logs", executionRunId],
    queryFn: () => fetchWorkbenchRunLogs(executionRunId as string),
    enabled: Boolean(executionRunId),
    retry: false,
  });
  const deliverableSnapshotQuery = useProjectDeliverableSnapshot(surfaceProjectId);
  const approvalInboxQuery = useProjectApprovalInbox(surfaceProjectId);
  const repositorySnapshotQuery = useProjectRepositorySnapshot(surfaceProjectId);
  const repositoryVerificationBaselineQuery =
    useProjectRepositoryVerificationBaseline(surfaceProjectId);
  const changeSessionQuery = useProjectChangeSession(surfaceProjectId);
  const roleCatalogQuery = useProjectRoleCatalog(surfaceProjectId);
  const systemRoleCatalogQuery = useSystemRoleCatalog();
  const skillRegistryQuery = useSkillRegistry();
  const skillBindingsQuery = useProjectSkillBindings(surfaceProjectId);
  const roleConsumptionQuery = useProjectRoleSkillConsumption(surfaceProjectId);
  const projectMemoryQuery = useProjectMemorySnapshot(surfaceProjectId);
  const memoryGovernanceQuery = useProjectMemoryGovernanceState(surfaceProjectId);
  const directorSetupReadinessQuery = useProjectDirectorSetupReadiness(surfaceProjectId);
  const directorAgentTeamConfigQuery = useProjectDirectorAgentTeamConfig(surfaceProjectId);
  const directorSkillBindingConfigQuery = useProjectDirectorSkillBindingConfig(surfaceProjectId);
  const directorRepositoryBindingConfigQuery =
    useProjectDirectorRepositoryBindingConfig(surfaceProjectId);
  const directorVerificationConfigQuery = useProjectDirectorVerificationConfig(surfaceProjectId);

  const projectGroups = useMemo(
    () =>
      buildRealWorkbenchProjectGroups({
        projects,
        resumableSessions: resumableSessionsQuery.data?.sessions ?? [],
      }),
    [projects, resumableSessionsQuery.data?.sessions],
  );

  const showActionFeedback = useCallback(
    (message: string, status: WorkbenchActionToastStatus = "done") => {
      setToast({ message, status });
      window.setTimeout(() => setToast(null), 3000);
    },
    [],
  );

  const { accountAdapter, settingsAdapter, workspaceSettingsQuery } =
    useWorkbenchSettingsAdapters(showActionFeedback);

  const surfaceData = useMemo(
    () =>
      buildWorkbenchSurfaceData({
        selectedProjectId: surfaceProjectId,
        selectedProjectName: surfaceProjectName,
        projects,
        projectDetail: projectDetailQuery.data ?? null,
        tasks: tasksQuery.data ?? [],
        selectedTask: selectedTaskQuery.data ?? null,
        taskRuns: taskRunsQuery.data ?? [],
        taskRunLogs: runLogsQuery.data ?? null,
        deliverables: deliverableSnapshotQuery.data ?? null,
        approvals: approvalInboxQuery.data ?? null,
        repositorySnapshot: repositorySnapshotQuery.data ?? null,
        repositoryVerificationBaseline: repositoryVerificationBaselineQuery.data ?? null,
        changeSession: changeSessionQuery.data ?? null,
        workspaceSettings: workspaceSettingsQuery.data ?? null,
        roleCatalog: roleCatalogQuery.data ?? null,
        systemRoles: systemRoleCatalogQuery.data ?? [],
        skillRegistry: skillRegistryQuery.data ?? null,
        skillBindings: skillBindingsQuery.data ?? null,
        roleSkillConsumption: roleConsumptionQuery.data ?? null,
        projectMemory: projectMemoryQuery.data ?? null,
        memoryGovernance: memoryGovernanceQuery.data ?? null,
        directorSetupReadiness: directorSetupReadinessQuery.data ?? null,
        directorAgentTeamConfig: directorAgentTeamConfigQuery.data ?? null,
        directorSkillBindingConfig: directorSkillBindingConfigQuery.data ?? null,
        directorRepositoryBindingConfig: directorRepositoryBindingConfigQuery.data ?? null,
        directorVerificationConfig: directorVerificationConfigQuery.data ?? null,
        loading: {
          project: projectDetailQuery.isLoading,
          execution: tasksQuery.isLoading || selectedTaskQuery.isLoading || taskRunsQuery.isLoading,
          deliverables: deliverableSnapshotQuery.isLoading || approvalInboxQuery.isLoading,
          repository:
            repositorySnapshotQuery.isLoading ||
            repositoryVerificationBaselineQuery.isLoading ||
            changeSessionQuery.isLoading ||
            workspaceSettingsQuery.isLoading,
          governance:
            roleCatalogQuery.isLoading ||
            systemRoleCatalogQuery.isLoading ||
            skillRegistryQuery.isLoading ||
            skillBindingsQuery.isLoading ||
            roleConsumptionQuery.isLoading ||
            projectMemoryQuery.isLoading ||
            memoryGovernanceQuery.isLoading ||
            directorSetupReadinessQuery.isLoading ||
            directorAgentTeamConfigQuery.isLoading ||
            directorSkillBindingConfigQuery.isLoading ||
            directorRepositoryBindingConfigQuery.isLoading ||
            directorVerificationConfigQuery.isLoading,
        },
        error: {
          project: projectDetailQuery.isError,
          execution: tasksQuery.isError || selectedTaskQuery.isError || taskRunsQuery.isError,
          deliverables: deliverableSnapshotQuery.isError || approvalInboxQuery.isError,
          repository:
            repositorySnapshotQuery.isError ||
            repositoryVerificationBaselineQuery.isError ||
            changeSessionQuery.isError ||
            workspaceSettingsQuery.isError,
          governance:
            roleCatalogQuery.isError ||
            systemRoleCatalogQuery.isError ||
            skillRegistryQuery.isError ||
            skillBindingsQuery.isError ||
            roleConsumptionQuery.isError ||
            projectMemoryQuery.isError ||
            memoryGovernanceQuery.isError ||
            directorSetupReadinessQuery.isError ||
            directorAgentTeamConfigQuery.isError ||
            directorSkillBindingConfigQuery.isError ||
            directorRepositoryBindingConfigQuery.isError ||
            directorVerificationConfigQuery.isError,
        },
      }),
    [
      approvalInboxQuery.data,
      approvalInboxQuery.isError,
      approvalInboxQuery.isLoading,
      changeSessionQuery.data,
      changeSessionQuery.isError,
      changeSessionQuery.isLoading,
      deliverableSnapshotQuery.data,
      deliverableSnapshotQuery.isError,
      deliverableSnapshotQuery.isLoading,
      directorAgentTeamConfigQuery.data,
      directorAgentTeamConfigQuery.isError,
      directorAgentTeamConfigQuery.isLoading,
      directorRepositoryBindingConfigQuery.data,
      directorRepositoryBindingConfigQuery.isError,
      directorRepositoryBindingConfigQuery.isLoading,
      directorSetupReadinessQuery.data,
      directorSetupReadinessQuery.isError,
      directorSetupReadinessQuery.isLoading,
      directorSkillBindingConfigQuery.data,
      directorSkillBindingConfigQuery.isError,
      directorSkillBindingConfigQuery.isLoading,
      directorVerificationConfigQuery.data,
      directorVerificationConfigQuery.isError,
      directorVerificationConfigQuery.isLoading,
      projectDetailQuery.data,
      projectDetailQuery.isError,
      projectDetailQuery.isLoading,
      projectMemoryQuery.data,
      projectMemoryQuery.isError,
      projectMemoryQuery.isLoading,
      projects,
      repositorySnapshotQuery.data,
      repositorySnapshotQuery.isError,
      repositorySnapshotQuery.isLoading,
      repositoryVerificationBaselineQuery.data,
      repositoryVerificationBaselineQuery.isError,
      repositoryVerificationBaselineQuery.isLoading,
      roleCatalogQuery.data,
      roleCatalogQuery.isError,
      roleCatalogQuery.isLoading,
      runLogsQuery.data,
      roleConsumptionQuery.data,
      roleConsumptionQuery.isError,
      roleConsumptionQuery.isLoading,
      memoryGovernanceQuery.data,
      memoryGovernanceQuery.isError,
      memoryGovernanceQuery.isLoading,
      skillBindingsQuery.data,
      skillBindingsQuery.isError,
      skillBindingsQuery.isLoading,
      skillRegistryQuery.data,
      skillRegistryQuery.isError,
      skillRegistryQuery.isLoading,
      surfaceProjectId,
      surfaceProjectName,
      systemRoleCatalogQuery.data,
      systemRoleCatalogQuery.isError,
      systemRoleCatalogQuery.isLoading,
      selectedTaskQuery.data,
      selectedTaskQuery.isError,
      selectedTaskQuery.isLoading,
      taskRunsQuery.data,
      taskRunsQuery.isError,
      taskRunsQuery.isLoading,
      tasksQuery.data,
      tasksQuery.isError,
      tasksQuery.isLoading,
      workspaceSettingsQuery.data,
      workspaceSettingsQuery.isError,
      workspaceSettingsQuery.isLoading,
    ],
  );

  const resolveProjectId = useCallback(
    (context: WorkbenchDirectorSurfaceContext) => {
      const contextProjectId =
        context.activeProjectId && context.activeProjectId !== "new-project"
          ? context.activeProjectId
          : null;
      return contextProjectId ?? formalProjectId ?? (initialMainPage ? surfaceProjectId : null);
    },
    [formalProjectId, initialMainPage, surfaceProjectId],
  );

  const resolveProjectName = useCallback(
    (context: WorkbenchDirectorSurfaceContext) =>
      context.activeProjectName ?? formalProjectName,
    [formalProjectName],
  );

  return (
    <>
      <WorkbenchExperience
        mode="real"
        projectGroups={projectGroups}
        initialMainPage={routeSurface ?? initialMainPage}
        initialProjectId={urlMode === "new-project" ? null : formalProjectId}
        initialSelectionMode={
          urlMode === "new-project" || !formalProjectId ? "new-project" : "project"
        }
        initialModal={initialModal}
        pageAdapterMode="real"
        surfaceData={surfaceData}
        settingsAdapter={settingsAdapter}
        accountAdapter={accountAdapter}
        suppressPromptBox
        onNewProjectSession={() => {
          setSelectedProjectId("all");
          navigate("/workbench?mode=new-project");
        }}
        renderTopActionSlot={(context) => (
          <WorkbenchActionInbox projectId={resolveProjectId(context)} />
        )}
        renderRepositoryBindingPanel={(context) => (
          <WorkbenchRepositoryBindingPanel
            projectId={resolveProjectId(context)}
            projectName={resolveProjectName(context)}
            onActionFeedback={showActionFeedback}
          />
        )}
        renderDirectorSurface={(context) => (
          <ProjectDirectorWorkbenchSurface
            context={context}
            fallbackProjectId={
              context.workbenchMode === "new-project" ? null : resolveProjectId(context)
            }
            fallbackProjectName={resolveProjectName(context)}
            mode={context.workbenchMode}
          />
        )}
      />
      <WorkbenchActionToast toast={toast} onClose={() => setToast(null)} />
    </>
  );
}
