import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { requestJson } from "../../lib/http";
import { formatDateTime } from "../../lib/format";
import { ApprovalInboxPage } from "../approvals/ApprovalInboxPage";
import { DeliverableCenterPage } from "../deliverables/DeliverableCenterPage";
import { RoleCatalogPage } from "../roles/RoleCatalogPage";
import { RoleWorkbenchPage } from "../roles/RoleWorkbenchPage";
import { SkillRegistryPage } from "../skills/SkillRegistryPage";
import { MemorySearchPanel } from "./MemorySearchPanel";
import { ProjectMemoryPanel } from "./ProjectMemoryPanel";
import { ProjectCreateFlow } from "./ProjectCreateFlow";
import { ProjectRetrospectivePanel } from "./ProjectRetrospectivePanel";
import { ProjectTimelinePage } from "./ProjectTimelinePage";
import { ProjectSummaryCards } from "./components/ProjectSummaryCards";
import { ProjectDeliverySnapshotCard } from "./components/ProjectDeliverySnapshotCard";
import { ProjectTable } from "./components/ProjectTable";
import { ProjectDetailSection } from "./sections/ProjectDetailSection";
import { FeaturedProjectsSection } from "./sections/FeaturedProjectsSection";
import { ProjectOverviewHeroSection } from "./sections/ProjectOverviewHeroSection";
import { RepositoryOverviewSection } from "./sections/RepositoryOverviewSection";
import { buildTaskSampleFromDetail } from "./lib/bossDrilldown";
import {
  useAdvanceProjectStage,
  useBossProjectDrilldown,
  useBossProjectOverview,
  useProjectDetail,
} from "./hooks";
import type { BossProjectItem, BossProjectLatestTask } from "./types";
import type { TaskDetail } from "../task-detail/types";

type ProjectOverviewPageProps = {
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
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
  const detailRef = useRef<HTMLElement | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    null,
  );
  const [stageActionFeedback, setStageActionFeedback] = useState<{
    tone: "success" | "warning" | "danger";
    text: string;
  } | null>(null);
  const [requestedDeliverableId, setRequestedDeliverableId] = useState<string | null>(
    null,
  );
  const [requestedApprovalId, setRequestedApprovalId] = useState<string | null>(null);

  const projects = overviewQuery.data?.projects ?? [];

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
    if (!selectedProjectId || !hasSelection) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const selectedProject = useMemo<BossProjectItem | null>(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );
  const projectDetailQuery = useProjectDetail(selectedProjectId);
  const advanceStageMutation = useAdvanceProjectStage(selectedProjectId);
  const day15FlowOverviewQuery = useProjectDay15FlowOverview(selectedProjectId);
  const selectedProjectDetail = projectDetailQuery.data ?? null;

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

    if (options?.scrollIntoDetail) {
      requestAnimationFrame(() => {
        detailRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      });
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
      scrollIntoDetail: true,
      requestedDeliverableId: input.deliverableId,
    });

    requestAnimationFrame(() => {
      document.getElementById("deliverable-center")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  const handleNavigateToApproval = (input: {
    projectId: string;
    approvalId: string;
  }) => {
    handleSelectProject(input.projectId, {
      scrollIntoDetail: true,
      requestedApprovalId: input.approvalId,
    });

    requestAnimationFrame(() => {
      document.getElementById("approval-inbox")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
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
    <section className="space-y-6 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/40">
      <ProjectOverviewHeroSection
        budgetStrategyLabel={overviewQuery.data?.budget.strategy_label}
        budgetPressureLevel={overviewQuery.data?.budget.pressure_level}
        lastUpdatedText={lastUpdatedText}
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
          <ProjectCreateFlow onProjectCreated={handleProjectCreated} />

          <ProjectSummaryCards overview={overviewQuery.data} />

          {featuredProjects.length > 0 ? (
            <RepositoryOverviewSection
              featuredProjects={featuredProjects}
              selectedProjectId={selectedProjectId}
              onSelectProject={(projectId) =>
                handleSelectProject(projectId, { scrollIntoDetail: true })
              }
            />
          ) : null}

          {featuredProjects.length > 0 ? (
            <FeaturedProjectsSection
              featuredProjects={featuredProjects}
              selectedProjectId={selectedProjectId}
              onSelectProject={(projectId) =>
                handleSelectProject(projectId, { scrollIntoDetail: true })
              }
            />
          ) : null}

          <section className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
            <ProjectTable
              projects={projects}
              selectedProjectId={selectedProjectId}
              onSelectProject={(projectId) =>
                handleSelectProject(projectId, { scrollIntoDetail: true })
              }
            />

            <aside
              ref={detailRef}
              id="project-detail"
              data-testid="project-detail-panel"
              className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-slate-950/30"
            >
              <h2 className="text-lg font-semibold text-slate-50">项目详情</h2>
              <p className="mt-1 text-sm text-slate-400">
                从项目卡片或列表进入，查看老板视角的项目详情；Day04 已把仓库绑定、目录快照和当前变更会话合并到同一详情视图中，仓库首页仍只保留最小入口，不扩展到文件级编辑、代码上下文包或验证证据视图。
              </p>

              {drilldownFeedback ? (
                <div
                  data-testid="project-detail-drilldown-feedback"
                  className={`mt-3 rounded-xl border p-3 text-xs ${
                    drilldownFeedback.tone === "success"
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
                      : "border-amber-500/30 bg-amber-500/10 text-amber-100"
                  }`}
                >
                  {drilldownFeedback.text}
                </div>
              ) : null}

              {selectedProject || selectedProjectDetail ? (
                <ProjectDetailSection
                  project={selectedProject}
                  detail={selectedProjectDetail}
                  drilldownContext={
                    drilldownContext &&
                    drilldownContext.project_id === (selectedProjectDetail?.id ?? selectedProject?.id ?? null)
                      ? drilldownContext
                      : null
                  }
                  activeDrilldownTaskSample={
                    drilldownContext &&
                    drilldownContext.project_id ===
                      (selectedProjectDetail?.id ?? selectedProject?.id ?? null)
                      ? activeDrilldownTaskSample
                      : null
                  }
                  onNavigateToStrategyPreview={navigateToStrategyPreview}
                  onNavigateToProjectLatestRun={navigateToProjectLatestRun}
                  onNavigateToTask={props.onNavigateToTask}
                  onAdvanceStage={handleAdvanceStage}
                  isAdvancing={advanceStageMutation.isPending}
                  stageActionFeedback={stageActionFeedback}
                  isLoading={projectDetailQuery.isLoading && !selectedProjectDetail}
                  errorMessage={
                    projectDetailQuery.isError
                      ? projectDetailQuery.error.message
                      : null
                  }
                />
              ) : (
                <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-8 text-center text-sm text-slate-400">
                  还没有可查看的项目详情。
                </div>
              )}
            </aside>
          </section>

          <ProjectTimelinePage
            projectId={selectedProjectId}
            projectName={selectedProject?.name ?? selectedProjectDetail?.name ?? null}
            onNavigateToTask={props.onNavigateToTask}
            onNavigateToDeliverable={handleNavigateToDeliverable}
            onNavigateToApproval={handleNavigateToApproval}
          />

          <DeliverableCenterPage
            projectId={selectedProjectId}
            projectName={selectedProject?.name ?? selectedProjectDetail?.name ?? null}
            requestedDeliverableId={requestedDeliverableId}
            onRequestedDeliverableHandled={() => setRequestedDeliverableId(null)}
            onNavigateToTask={props.onNavigateToTask}
          />

          <ApprovalInboxPage
            projectId={selectedProjectId}
            projectName={selectedProject?.name ?? selectedProjectDetail?.name ?? null}
            requestedApprovalId={requestedApprovalId}
            onRequestedApprovalHandled={() => setRequestedApprovalId(null)}
          />

          <ProjectRetrospectivePanel
            projectId={selectedProjectId}
            projectName={selectedProject?.name ?? selectedProjectDetail?.name ?? null}
            onNavigateToApproval={handleNavigateToApproval}
            onNavigateToTask={props.onNavigateToTask}
          />

          <ProjectMemoryPanel
            projectId={selectedProjectId}
            projectName={selectedProject?.name ?? selectedProjectDetail?.name ?? null}
            onNavigateToApproval={handleNavigateToApproval}
            onNavigateToDeliverable={handleNavigateToDeliverable}
            onNavigateToTask={props.onNavigateToTask}
          />

          <MemorySearchPanel
            projectId={selectedProjectId}
            projectName={selectedProject?.name ?? selectedProjectDetail?.name ?? null}
            onNavigateToApproval={handleNavigateToApproval}
            onNavigateToDeliverable={handleNavigateToDeliverable}
            onNavigateToTask={props.onNavigateToTask}
          />

          <RoleCatalogPage
            selectedProjectId={selectedProjectId}
            selectedProjectName={
              selectedProject?.name ?? selectedProjectDetail?.name ?? null
            }
          />

          <SkillRegistryPage
            selectedProjectId={selectedProjectId}
            selectedProjectName={
              selectedProject?.name ?? selectedProjectDetail?.name ?? null
            }
          />

          <RoleWorkbenchPage
            selectedProjectId={selectedProjectId}
            selectedProjectName={
              selectedProject?.name ?? selectedProjectDetail?.name ?? null
            }
            projectOptions={projects.map((project) => ({
              id: project.id,
              name: project.name,
              stage: project.stage,
              status: project.status,
            }))}
            onNavigateToProject={(projectId) =>
              handleSelectProject(projectId, { scrollIntoDetail: true })
            }
            onNavigateToTask={props.onNavigateToTask}
          />
        </>
      ) : null}
    </section>
  );
}
