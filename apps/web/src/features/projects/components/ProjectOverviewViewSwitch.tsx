import { ApprovalInboxPage } from "../../approvals/ApprovalInboxPage";
import { DeliverableCenterPage } from "../../deliverables/DeliverableCenterPage";
import { ProjectCollaborationControlPage } from "../pages/ProjectCollaborationControlPage";
import { ProjectMemoryRoleGovernancePage } from "../pages/ProjectMemoryRoleGovernancePage";
import { ProjectOverviewDashboardPage } from "../pages/ProjectOverviewDashboardPage";
import { ProjectTimelineRetrospectivePage } from "../pages/ProjectTimelineRetrospectivePage";
import { type ProjectOverviewPageView } from "../lib/overviewNavigation";
import type { ProjectOverviewPageController } from "../hooks/useProjectOverviewPageController";

type ProjectOverviewViewSwitchProps = {
  activeView: ProjectOverviewPageView;
  controller: ProjectOverviewPageController;
  overview: NonNullable<ProjectOverviewPageController["overviewQuery"]["data"]>;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function ProjectOverviewViewSwitch(props: ProjectOverviewViewSwitchProps) {
  const { controller } = props;

  if (props.activeView === "overview") {
    return (
      <ProjectOverviewDashboardPage
        overview={props.overview}
        featuredProjects={controller.featuredProjects}
        projects={controller.projects}
        selectedProjectId={controller.selectedProjectId}
        selectedProject={controller.selectedProject}
        selectedProjectDetail={controller.selectedProjectDetail}
        drilldownContext={controller.drilldownContext}
        drilldownFeedback={controller.drilldownFeedback}
        activeDrilldownTaskSample={controller.activeDrilldownTaskSample}
        onProjectCreated={controller.handleProjectCreated}
        onSelectProjectIntoDetail={(projectId) =>
          controller.handleSelectProject(projectId, { scrollIntoDetail: true })
        }
        onNavigateToRepositoryWorkspace={() =>
          controller.navigateToOverviewSection("repository-workspace")
        }
        onNavigateToStrategyPreview={controller.navigateToStrategyPreview}
        onNavigateToProjectLatestRun={controller.navigateToProjectLatestRun}
        onNavigateToTask={props.onNavigateToTask}
        onAdvanceStage={controller.handleAdvanceStage}
        isAdvancingStage={controller.isAdvancingStage}
        stageActionFeedback={controller.stageActionFeedback}
        isProjectDetailLoading={
          controller.projectDetailQuery.isLoading && !controller.selectedProjectDetail
        }
        projectDetailErrorMessage={
          controller.projectDetailQuery.isError
            ? controller.projectDetailQuery.error.message
            : null
        }
      />
    );
  }

  if (props.activeView === "timeline-retrospective") {
    return (
      <ProjectTimelineRetrospectivePage
        selectedProjectId={controller.selectedProjectId}
        selectedProjectName={controller.selectedProjectName}
        onNavigateToTask={props.onNavigateToTask}
        onNavigateToDeliverable={controller.handleNavigateToDeliverable}
        onNavigateToApproval={controller.handleNavigateToApproval}
      />
    );
  }

  if (props.activeView === "collaboration-control") {
    return (
      <ProjectCollaborationControlPage
        selectedProjectId={controller.selectedProjectId}
        selectedProjectName={controller.selectedProjectName}
      />
    );
  }

  if (props.activeView === "memory-role-governance") {
    return (
      <ProjectMemoryRoleGovernancePage
        selectedProjectId={controller.selectedProjectId}
        selectedProjectName={controller.selectedProjectName}
        projects={controller.projects}
        onSelectProject={(projectId) => controller.handleSelectProject(projectId)}
        onNavigateToTask={props.onNavigateToTask}
        onNavigateToDeliverable={controller.handleNavigateToDeliverable}
        onNavigateToApproval={controller.handleNavigateToApproval}
      />
    );
  }

  if (props.activeView === "deliverable-center") {
    return (
      <div
        id="project-overview-view-deliverable-center"
        data-testid="project-overview-view-deliverable-center"
      >
        <DeliverableCenterPage
          projectId={controller.selectedProjectId}
          projectName={controller.selectedProjectName}
          requestedDeliverableId={controller.requestedDeliverableId}
          onRequestedDeliverableHandled={() =>
            controller.setRequestedDeliverableId(null)
          }
          onNavigateToTask={props.onNavigateToTask}
        />
      </div>
    );
  }

  if (props.activeView === "approval-inbox") {
    return (
      <div
        id="project-overview-view-approval-inbox"
        data-testid="project-overview-view-approval-inbox"
      >
        <ApprovalInboxPage
          projectId={controller.selectedProjectId}
          projectName={controller.selectedProjectName}
          requestedApprovalId={controller.requestedApprovalId}
          onRequestedApprovalHandled={() => controller.setRequestedApprovalId(null)}
        />
      </div>
    );
  }

  return null;
}
