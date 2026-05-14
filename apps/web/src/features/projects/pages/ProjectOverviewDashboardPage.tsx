import { useCallback, useRef, useState } from "react";

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
  onNavigateToRepositoryWorkspace: () => void;
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
  const [isCreateFlowOpen, setIsCreateFlowOpen] = useState(false);
  const createFlowRef = useRef<HTMLDivElement | null>(null);

  const handleOpenCreateFlow = useCallback(() => {
    setIsCreateFlowOpen(true);
    window.setTimeout(() => {
      createFlowRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 0);
  }, []);

  return (
    <div
      id="overview"
      data-testid="project-overview-view-overview"
      className="space-y-7"
    >
      <section className="space-y-5">
        <div className="flex flex-col gap-4 border-b border-[#333333] pb-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
              控制台总览
            </p>
            <h2 className="mt-2 text-xl font-semibold text-zinc-100">
              先看态势，再处理项目
            </h2>
          </div>
          <div className="flex flex-col gap-3 lg:items-end">
            <p className="max-w-xl text-sm leading-6 text-zinc-500 lg:text-right">
              项目进展、风险和待处理事项。
            </p>
            <button
              type="button"
              onClick={handleOpenCreateFlow}
              className="inline-flex shrink-0 items-center justify-center rounded border border-zinc-300 bg-zinc-100 px-4 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-white"
            >
              {isCreateFlowOpen ? "定位到创建项目草案" : "创建项目草案"}
            </button>
          </div>
        </div>

        <ProjectSummaryCards overview={props.overview} />
      </section>

      {isCreateFlowOpen ? (
        <div id="project-create-draft-panel" ref={createFlowRef}>
          <ProjectCreateFlow onProjectCreated={props.onProjectCreated} />
        </div>
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
        onCreateProjectDraft={handleOpenCreateFlow}
        onNavigateToRepositoryWorkspace={props.onNavigateToRepositoryWorkspace}
      />

    </div>
  );
}
