import { ProjectCreateFlow } from "../ProjectCreateFlow";
import { ProjectSummaryCards } from "../components/ProjectSummaryCards";
import { ProjectOverviewTableAndDetailSection } from "../sections/ProjectOverviewTableAndDetailSection";
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
      className="space-y-7"
    >
      <section className="space-y-5">
        <div className="flex flex-col gap-2 border-b border-[#333333] pb-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
              控制台总览
            </p>
            <h2 className="mt-2 text-xl font-semibold text-zinc-100">
              先看态势，再处理项目
            </h2>
          </div>
          <p className="max-w-xl text-sm leading-6 text-zinc-500">
            聚合项目进展、风险和待处理事项，帮助你快速定位下一步工作。
          </p>
        </div>

        <ProjectSummaryCards overview={props.overview} />
      </section>

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

      <details className="group border-b border-[#333333] pb-5">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm text-zinc-400 transition hover:text-zinc-100">
          <span>
            <span className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
              创建项目
            </span>
            <span className="ml-3">需要新项目时打开创建表单</span>
          </span>
          <span className="text-xs text-zinc-600 group-open:hidden">展开</span>
          <span className="hidden text-xs text-zinc-600 group-open:inline">收起</span>
        </summary>
        <div className="mt-5">
          <ProjectCreateFlow onProjectCreated={props.onProjectCreated} />
        </div>
      </details>
    </div>
  );
}
