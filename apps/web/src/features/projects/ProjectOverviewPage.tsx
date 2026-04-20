import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { requestJson } from "../../lib/http";
import { formatDateTime } from "../../lib/format";
import { ApprovalInboxPage } from "../approvals/ApprovalInboxPage";
import { DeliverableCenterPage } from "../deliverables/DeliverableCenterPage";
import { ProjectDeliverySnapshotCard } from "./components/ProjectDeliverySnapshotCard";
import {
  PROJECT_OVERVIEW_NAVIGATION_ITEMS,
  type ProjectOverviewPageView,
} from "./lib/overviewNavigation";
import { buildTaskSampleFromDetail } from "./lib/bossDrilldown";
import { useProjectOverviewNavigationState } from "./hooks/useProjectOverviewNavigationState";
import { ProjectCollaborationControlPage } from "./pages/ProjectCollaborationControlPage";
import { ProjectMemoryRoleGovernancePage } from "./pages/ProjectMemoryRoleGovernancePage";
import { ProjectOverviewDashboardPage } from "./pages/ProjectOverviewDashboardPage";
import { ProjectTimelineRetrospectivePage } from "./pages/ProjectTimelineRetrospectivePage";
import {
  useAdvanceProjectStage,
  useBossProjectDrilldown,
  useBossProjectOverview,
  useProjectDetail,
} from "./hooks";
import { ProjectOverviewHeroSection } from "./sections/ProjectOverviewHeroSection";
import { ProjectOverviewModuleNavSection } from "./sections/ProjectOverviewModuleNavSection";
import type { BossProjectItem, BossProjectLatestTask } from "./types";
import type { TaskDetail } from "../task-detail/types";

type ProjectOverviewPageProps = {
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToApproval?: (projectId: string, approvalId: string) => void;
  resolveProjectViewHref?: (
    view: Exclude<ProjectOverviewPageView, "overview">,
    projectId: string,
  ) => string | null | undefined;
  routeProjectId?: string | null;
  routeProjectView?: Exclude<ProjectOverviewPageView, "overview"> | null;
  routeRequestedDeliverableId?: string | null;
  routeRequestedApprovalId?: string | null;
  onNavigateToProjectView?: (
    view: ProjectOverviewPageView,
    options?: { projectId?: string | null },
  ) => boolean | void;
};

type ProjectDay15FlowOverview = {
  project_id: string;
  project_name: string;
  generated_at: string;
  overall_status: "in_progress" | "blocked" | "ready_for_review";
  summary: string;
  completed_step_count: number;
  total_step_count: number;
  blocked_step_count: number;
  selected_change_batch_id: string | null;
  selected_change_batch_title: string | null;
  release_status: string | null;
  release_qualification_established: boolean;
  git_write_actions_triggered: boolean;
};

function getProjectRecencyTimestamp(project: BossProjectItem): number {
  const timestampCandidates = [
    project.latest_progress_at,
    project.updated_at,
    project.created_at,
  ];

  for (const candidate of timestampCandidates) {
    if (!candidate) {
      continue;
    }

    const parsed = Date.parse(candidate);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }

  return 0;
}

function useProjectDay15FlowOverview(projectId: string | null) {
  return useQuery({
    queryKey: ["project-day15-repository-flow", projectId],
    queryFn: () =>
      requestJson<ProjectDay15FlowOverview>(
        `/projects/${projectId}/day15-repository-flow`,
      ),
    enabled: Boolean(projectId),
  });
}

export function ProjectOverviewPage(props: ProjectOverviewPageProps) {
  const overviewQuery = useBossProjectOverview();
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    props.routeProjectId ?? null,
  );
  const [stageActionFeedback, setStageActionFeedback] = useState<{
    tone: "success" | "warning" | "danger";
    text: string;
  } | null>(null);
  const [requestedDeliverableId, setRequestedDeliverableId] = useState<string | null>(
    props.routeRequestedDeliverableId ?? null,
  );
  const [requestedApprovalId, setRequestedApprovalId] = useState<string | null>(
    props.routeRequestedApprovalId ?? null,
  );
  const { activeView, navigateToOverviewSection, navigateToOverviewPage } =
    useProjectOverviewNavigationState({
      requestedApprovalId,
      requestedDeliverableId,
      selectedProjectId,
      routeProjectView: props.routeProjectView ?? null,
      onNavigateToRouteView: props.onNavigateToProjectView,
    });

  const projects = overviewQuery.data?.projects ?? [];
  const defaultSelectedProjectId = useMemo(() => {
    if (!projects.length) {
      return null;
    }

    return [...projects].sort(
      (left, right) =>
        getProjectRecencyTimestamp(right) - getProjectRecencyTimestamp(left),
    )[0]?.id ?? null;
  }, [projects]);

  useEffect(() => {
    setRequestedDeliverableId(props.routeRequestedDeliverableId ?? null);
  }, [props.routeRequestedDeliverableId]);

  useEffect(() => {
    setRequestedApprovalId(props.routeRequestedApprovalId ?? null);
  }, [props.routeRequestedApprovalId]);

  useEffect(() => {
    if (!props.routeProjectId || !projects.length) {
      return;
    }

    const hasRouteProject = projects.some((project) => project.id === props.routeProjectId);
    if (hasRouteProject && selectedProjectId !== props.routeProjectId) {
      setSelectedProjectId(props.routeProjectId);
      setStageActionFeedback(null);
    }
  }, [projects, props.routeProjectId, selectedProjectId]);

  useEffect(() => {
    if (!projects.length) {
      if (selectedProjectId !== null) {
        setSelectedProjectId(null);
      }
      return;
    }

    const hasSelection = projects.some(
      (project) => project.id === selectedProjectId,
    );
    if ((!selectedProjectId || !hasSelection) && defaultSelectedProjectId) {
      setSelectedProjectId(defaultSelectedProjectId);
    }
  }, [defaultSelectedProjectId, projects, props.routeProjectId, selectedProjectId]);

  const selectedProject = useMemo<BossProjectItem | null>(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );
  const projectDetailQuery = useProjectDetail(selectedProjectId);
  const advanceStageMutation = useAdvanceProjectStage(selectedProjectId);
  const day15FlowOverviewQuery = useProjectDay15FlowOverview(selectedProjectId);
  const selectedProjectDetail = projectDetailQuery.data ?? null;
  const selectedProjectName =
    selectedProject?.name ?? selectedProjectDetail?.name ?? null;

  const featuredProjects = useMemo(() => projects.slice(0, 3), [projects]);
  const lastUpdatedText = overviewQuery.dataUpdatedAt
    ? formatDateTime(new Date(overviewQuery.dataUpdatedAt).toISOString())
    : "尚未刷新";

  const handleSelectProject = (
    projectId: string,
    options?: {
      scrollIntoDetail?: boolean;
      requestedDeliverableId?: string | null;
      requestedApprovalId?: string | null;
      preserveDrilldownContext?: boolean;
      syncRoute?: boolean;
    },
  ) => {
    setSelectedProjectId(projectId);
    setStageActionFeedback(null);
    setRequestedDeliverableId(options?.requestedDeliverableId ?? null);
    setRequestedApprovalId(options?.requestedApprovalId ?? null);
    if (!options?.preserveDrilldownContext) {
      setDrilldownContext(null);
      setDrilldownFeedback(null);
    }

    if (options?.syncRoute !== false && props.routeProjectId) {
      props.onNavigateToProjectView?.(activeView, { projectId });
    }

    if (options?.scrollIntoDetail) {
      navigateToOverviewSection("project-detail", { projectId });
    }
  };

  const handleProjectCreated = (projectId: string) => {
    handleSelectProject(projectId, { scrollIntoDetail: true });
  };

  const {
    drilldownContext,
    drilldownFeedback,
    navigateToStrategyPreview,
    navigateToProjectLatestRun,
    setDrilldownContext,
    setDrilldownFeedback,
  } = useBossProjectDrilldown({
    projects,
    refetchOverview: overviewQuery.refetch,
    onSelectProject: handleSelectProject,
  });

  const drilldownTaskDetailQuery = useQuery({
    queryKey: ["project-drilldown-task-detail", drilldownContext?.task_id],
    queryFn: () =>
      requestJson<TaskDetail>(`/tasks/${drilldownContext?.task_id ?? ""}/detail`),
    enabled: Boolean(drilldownContext?.task_id),
  });

  const activeDrilldownTaskSample = useMemo<BossProjectLatestTask | null>(() => {
    if (!drilldownContext || !drilldownTaskDetailQuery.data) {
      return null;
    }
    return buildTaskSampleFromDetail(
      drilldownTaskDetailQuery.data,
      drilldownContext.run_id,
    );
  }, [drilldownContext, drilldownTaskDetailQuery.data]);

  const handleNavigateToDeliverable = (input: {
    projectId: string;
    deliverableId: string;
  }) => {
    handleSelectProject(input.projectId, {
      requestedDeliverableId: input.deliverableId,
      syncRoute: false,
    });

    navigateToOverviewPage("deliverable-center", "deliverable-center", {
      projectId: input.projectId,
    });
  };

  const handleNavigateToApproval = (input: {
    projectId: string;
    approvalId: string;
  }) => {
    if (props.onNavigateToApproval) {
      props.onNavigateToApproval(input.projectId, input.approvalId);
      return;
    }

    handleSelectProject(input.projectId, {
      requestedApprovalId: input.approvalId,
      syncRoute: false,
    });

    navigateToOverviewPage("approval-inbox", "approval-inbox", {
      projectId: input.projectId,
    });
  };

  useEffect(() => {
    const handleDeliverableNavigation = (event: Event) => {
      const detail = (event as CustomEvent<{
        projectId?: string;
        deliverableId?: string | null;
      }>).detail;
      if (!detail?.projectId || !detail.deliverableId) {
        return;
      }

      handleNavigateToDeliverable({
        projectId: detail.projectId,
        deliverableId: detail.deliverableId,
      });
    };

    window.addEventListener(
      "deliverable:navigate",
      handleDeliverableNavigation as EventListener,
    );

    return () => {
      window.removeEventListener(
        "deliverable:navigate",
        handleDeliverableNavigation as EventListener,
      );
    };
  }, []);

  const handleAdvanceStage = async (note: string | null) => {
    try {
      const result = await advanceStageMutation.mutateAsync({ note });
      setStageActionFeedback({
        tone: result.advanced ? "success" : "warning",
        text: result.message,
      });
    } catch (error) {
      setStageActionFeedback({
        tone: "danger",
        text: error instanceof Error ? error.message : "项目阶段推进失败。",
      });
      throw error;
    }
  };

  return (
    <section
      data-testid="project-overview-page"
      className="space-y-6 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/40"
    >
      <ProjectOverviewHeroSection
        budgetStrategyLabel={overviewQuery.data?.budget.strategy_label}
        budgetPressureLevel={overviewQuery.data?.budget.pressure_level}
        lastUpdatedText={lastUpdatedText}
      />

      <ProjectOverviewModuleNavSection
        activeView={activeView}
        projectId={selectedProjectId}
        navigationItems={PROJECT_OVERVIEW_NAVIGATION_ITEMS}
        onNavigateToOverviewSection={navigateToOverviewSection}
        resolvePageHref={(item, projectId) =>
          props.resolveProjectViewHref?.(item.view, projectId) ?? null
        }
        onNavigateToOverviewPage={navigateToOverviewPage}
      />

      {selectedProjectId ? (
        <ProjectDeliverySnapshotCard
          overview={day15FlowOverviewQuery.data ?? null}
          isLoading={day15FlowOverviewQuery.isLoading}
          errorMessage={
            day15FlowOverviewQuery.isError ? day15FlowOverviewQuery.error.message : null
          }
        />
      ) : null}

      {overviewQuery.isLoading && !overviewQuery.data ? (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
          正在加载老板首页数据...
        </section>
      ) : null}

      {overviewQuery.isError ? (
        <section className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-6 text-sm text-rose-100">
          项目总览加载失败：{overviewQuery.error.message}
        </section>
      ) : null}

      {overviewQuery.data ? (
        <>
          {activeView === "overview" ? (
            <ProjectOverviewDashboardPage
              overview={overviewQuery.data}
              featuredProjects={featuredProjects}
              projects={projects}
              selectedProjectId={selectedProjectId}
              selectedProject={selectedProject}
              selectedProjectDetail={selectedProjectDetail}
              drilldownContext={drilldownContext}
              drilldownFeedback={drilldownFeedback}
              activeDrilldownTaskSample={activeDrilldownTaskSample}
              onProjectCreated={handleProjectCreated}
              onSelectProjectIntoDetail={(projectId) =>
                handleSelectProject(projectId, { scrollIntoDetail: true })
              }
              onNavigateToStrategyPreview={navigateToStrategyPreview}
              onNavigateToProjectLatestRun={navigateToProjectLatestRun}
              onNavigateToTask={props.onNavigateToTask}
              onAdvanceStage={handleAdvanceStage}
              isAdvancingStage={advanceStageMutation.isPending}
              stageActionFeedback={stageActionFeedback}
              isProjectDetailLoading={projectDetailQuery.isLoading && !selectedProjectDetail}
              projectDetailErrorMessage={
                projectDetailQuery.isError ? projectDetailQuery.error.message : null
              }
            />
          ) : null}

          {activeView === "timeline-retrospective" ? (
            <ProjectTimelineRetrospectivePage
              selectedProjectId={selectedProjectId}
              selectedProjectName={selectedProjectName}
              onNavigateToTask={props.onNavigateToTask}
              onNavigateToDeliverable={handleNavigateToDeliverable}
              onNavigateToApproval={handleNavigateToApproval}
            />
          ) : null}

          {activeView === "collaboration-control" ? (
            <ProjectCollaborationControlPage
              selectedProjectId={selectedProjectId}
              selectedProjectName={selectedProjectName}
            />
          ) : null}

          {activeView === "memory-role-governance" ? (
            <ProjectMemoryRoleGovernancePage
              selectedProjectId={selectedProjectId}
              selectedProjectName={selectedProjectName}
              projects={projects}
              onSelectProject={(projectId) => handleSelectProject(projectId)}
              onNavigateToTask={props.onNavigateToTask}
              onNavigateToDeliverable={handleNavigateToDeliverable}
              onNavigateToApproval={handleNavigateToApproval}
            />
          ) : null}

          {activeView === "deliverable-center" ? (
            <div
              id="project-overview-view-deliverable-center"
              data-testid="project-overview-view-deliverable-center"
            >
              <DeliverableCenterPage
                projectId={selectedProjectId}
                projectName={selectedProjectName}
                requestedDeliverableId={requestedDeliverableId}
                onRequestedDeliverableHandled={() => setRequestedDeliverableId(null)}
                onNavigateToTask={props.onNavigateToTask}
              />
            </div>
          ) : null}

          {activeView === "approval-inbox" ? (
            <div
              id="project-overview-view-approval-inbox"
              data-testid="project-overview-view-approval-inbox"
            >
              <ApprovalInboxPage
                projectId={selectedProjectId}
                projectName={selectedProjectName}
                requestedApprovalId={requestedApprovalId}
                onRequestedApprovalHandled={() => setRequestedApprovalId(null)}
              />
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
