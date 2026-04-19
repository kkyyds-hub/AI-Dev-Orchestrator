import { ProjectTable } from "../components/ProjectTable";
import type {
  BossDrilldownContext,
  BossDrilldownFeedback,
  BossProjectItem,
  BossProjectLatestTask,
  ProjectDetail,
} from "../types";
import { ProjectDetailSection } from "./ProjectDetailSection";

type StageActionFeedback = {
  tone: "success" | "warning" | "danger";
  text: string;
} | null;

type ProjectOverviewTableAndDetailSectionProps = {
  projects: BossProjectItem[];
  selectedProjectId: string | null;
  selectedProject: BossProjectItem | null;
  selectedProjectDetail: ProjectDetail | null;
  drilldownContext: BossDrilldownContext | null;
  drilldownFeedback: BossDrilldownFeedback | null;
  activeDrilldownTaskSample: BossProjectLatestTask | null;
  onSelectProject: (projectId: string) => void;
  onNavigateToStrategyPreview: (context: BossDrilldownContext) => void;
  onNavigateToProjectLatestRun: (context: BossDrilldownContext) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onAdvanceStage: (note: string | null) => Promise<void> | void;
  isAdvancingStage: boolean;
  stageActionFeedback: StageActionFeedback;
  isProjectDetailLoading: boolean;
  projectDetailErrorMessage: string | null;
};

export function ProjectOverviewTableAndDetailSection(
  props: ProjectOverviewTableAndDetailSectionProps,
) {
  return (
    <section
      data-testid="project-overview-detail-workspace"
      className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]"
    >
      <ProjectTable
        projects={props.projects}
        selectedProjectId={props.selectedProjectId}
        onSelectProject={props.onSelectProject}
      />

      <aside
        id="project-detail"
        data-testid="project-detail-panel"
        className="scroll-mt-24 rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-slate-950/30"
      >
        <h2 className="text-lg font-semibold text-slate-50">项目详情</h2>
        <p className="mt-1 text-sm text-slate-400">
          聚焦阶段推进、运行钻取与策略上下文，保持同一入口内的最小协同闭环。
        </p>

        {props.drilldownFeedback ? (
          <div
            data-testid="project-detail-drilldown-feedback"
            className={`mt-3 rounded-xl border p-3 text-xs ${
              props.drilldownFeedback.tone === "success"
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
                : "border-amber-500/30 bg-amber-500/10 text-amber-100"
            }`}
          >
            {props.drilldownFeedback.text}
          </div>
        ) : null}

        {props.selectedProject || props.selectedProjectDetail ? (
          <ProjectDetailSection
            project={props.selectedProject}
            detail={props.selectedProjectDetail}
            drilldownContext={
              props.drilldownContext &&
              props.drilldownContext.project_id ===
                (props.selectedProjectDetail?.id ?? props.selectedProject?.id ?? null)
                ? props.drilldownContext
                : null
            }
            activeDrilldownTaskSample={
              props.drilldownContext &&
              props.drilldownContext.project_id ===
                (props.selectedProjectDetail?.id ?? props.selectedProject?.id ?? null)
                ? props.activeDrilldownTaskSample
                : null
            }
            onNavigateToStrategyPreview={props.onNavigateToStrategyPreview}
            onNavigateToProjectLatestRun={props.onNavigateToProjectLatestRun}
            onNavigateToTask={props.onNavigateToTask}
            onAdvanceStage={props.onAdvanceStage}
            isAdvancing={props.isAdvancingStage}
            stageActionFeedback={props.stageActionFeedback}
            isLoading={props.isProjectDetailLoading}
            errorMessage={props.projectDetailErrorMessage}
          />
        ) : (
          <div className="mt-4 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-8 text-center text-sm text-slate-400">
            请选择项目后查看阶段守卫、任务树和运行策略上下文。
          </div>
        )}
      </aside>
    </section>
  );
}
