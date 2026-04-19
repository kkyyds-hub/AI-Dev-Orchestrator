import { ProjectCreateFlow } from "../ProjectCreateFlow";
import { ProjectSummaryCards } from "../components/ProjectSummaryCards";
import { FeaturedProjectsSection } from "../sections/FeaturedProjectsSection";
import { ProjectOverviewTableAndDetailSection } from "../sections/ProjectOverviewTableAndDetailSection";
import { RepositoryOverviewSection } from "../sections/RepositoryOverviewSection";
import type {
  BossDrilldownContext,
  BossDrilldownFeedback,
  BossProjectItem,
  BossProjectLatestTask,
  BossProjectOverview,
  ProjectDetail,
} from "../types";

type StageActionFeedback = {
  tone: "success" | "warning" | "danger";
  text: string;
} | null;

type ProjectOverviewDashboardPageProps = {
  overview: BossProjectOverview;
  featuredProjects: BossProjectItem[];
  projects: BossProjectItem[];
  selectedProjectId: string | null;
  selectedProject: BossProjectItem | null;
  selectedProjectDetail: ProjectDetail | null;
  drilldownContext: BossDrilldownContext | null;
  drilldownFeedback: BossDrilldownFeedback | null;
  activeDrilldownTaskSample: BossProjectLatestTask | null;
  onProjectCreated: (projectId: string) => void;
  onSelectProjectIntoDetail: (projectId: string) => void;
  onNavigateToStrategyPreview: (context: BossDrilldownContext) => void;
  onNavigateToProjectLatestRun: (context: BossDrilldownContext) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onAdvanceStage: (note: string | null) => Promise<void> | void;
  isAdvancingStage: boolean;
  stageActionFeedback: StageActionFeedback;
  isProjectDetailLoading: boolean;
  projectDetailErrorMessage: string | null;
};

export function ProjectOverviewDashboardPage(
  props: ProjectOverviewDashboardPageProps,
) {
  return (
    <div
      id="overview"
      data-testid="project-overview-view-overview"
      className="space-y-6"
    >
      <ProjectCreateFlow onProjectCreated={props.onProjectCreated} />

      <ProjectSummaryCards overview={props.overview} />

      {props.featuredProjects.length > 0 ? (
        <RepositoryOverviewSection
          featuredProjects={props.featuredProjects}
          selectedProjectId={props.selectedProjectId}
          onSelectProject={props.onSelectProjectIntoDetail}
        />
      ) : null}

      {props.featuredProjects.length > 0 ? (
        <FeaturedProjectsSection
          featuredProjects={props.featuredProjects}
          selectedProjectId={props.selectedProjectId}
          onSelectProject={props.onSelectProjectIntoDetail}
        />
      ) : null}

      <ProjectOverviewTableAndDetailSection
        projects={props.projects}
        selectedProjectId={props.selectedProjectId}
        selectedProject={props.selectedProject}
        selectedProjectDetail={props.selectedProjectDetail}
        drilldownContext={props.drilldownContext}
        drilldownFeedback={props.drilldownFeedback}
        activeDrilldownTaskSample={props.activeDrilldownTaskSample}
        onSelectProject={props.onSelectProjectIntoDetail}
        onNavigateToStrategyPreview={props.onNavigateToStrategyPreview}
        onNavigateToProjectLatestRun={props.onNavigateToProjectLatestRun}
        onNavigateToTask={props.onNavigateToTask}
        onAdvanceStage={props.onAdvanceStage}
        isAdvancingStage={props.isAdvancingStage}
        stageActionFeedback={props.stageActionFeedback}
        isProjectDetailLoading={props.isProjectDetailLoading}
        projectDetailErrorMessage={props.projectDetailErrorMessage}
      />
    </div>
  );
}
