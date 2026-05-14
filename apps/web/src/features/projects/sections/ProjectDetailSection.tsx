import { RepositoryOverviewPage as ProjectRepositoryOverviewPage } from "../../repositories/RepositoryOverviewPage";
import { RoleFlowPanel } from "../../roles/RoleFlowPanel";
import { StrategyDecisionPanel } from "../../strategy/StrategyDecisionPanel";
import { StrategyRuleEditor } from "../../strategy/StrategyRuleEditor";
import { ProjectSopPanel } from "../ProjectSopPanel";
import { ProjectDetailHeader } from "../components/ProjectDetailHeader";
import { ProjectDetailStatsGrid } from "../components/ProjectDetailStatsGrid";
import { ProjectLatestTaskPreview } from "../components/ProjectLatestTaskPreview";
import { ProjectMilestonePanel } from "../components/ProjectMilestonePanel";
import { ProjectProgressRiskSummary } from "../components/ProjectProgressRiskSummary";
import { ProjectSettingsEntryPanel } from "../components/ProjectSettingsEntryPanel";
import { ProjectStageTimeline } from "../components/ProjectStageTimeline";
import { ProjectTaskTree } from "../components/ProjectTaskTree";
import type {
  BossDrilldownContext,
  BossProjectItem,
  BossProjectLatestTask,
  ProjectDetail,
} from "../types";

export function ProjectDetailSection(props: {
  project: BossProjectItem | null;
  detail: ProjectDetail | null;
  drilldownContext: BossDrilldownContext | null;
  activeDrilldownTaskSample: BossProjectLatestTask | null;
  onNavigateToStrategyPreview: (context: BossDrilldownContext) => void;
  onNavigateToProjectLatestRun: (context: BossDrilldownContext) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onAdvanceStage: (note: string | null) => Promise<void> | void;
  isAdvancing: boolean;
  stageActionFeedback: {
    tone: "success" | "warning" | "danger";
    text: string;
  } | null;
  isLoading: boolean;
  errorMessage: string | null;
}) {
  const taskStats = props.project?.task_stats ?? props.detail?.task_stats ?? null;
  const projectName = props.project?.name ?? props.detail?.name ?? "未命名项目";
  const projectSummary = props.project?.summary ?? props.detail?.summary ?? "暂无项目摘要。";
  const projectStage = props.project?.stage ?? props.detail?.stage ?? "planning";
  const projectStatus = props.project?.status ?? props.detail?.status ?? "active";
  const projectCreatedAt =
    props.project?.created_at ?? props.detail?.created_at ?? null;
  const projectUpdatedAt =
    props.project?.updated_at ?? props.detail?.updated_at ?? null;
  const projectTasks = props.detail?.tasks ?? [];
  const projectId = props.detail?.id ?? props.project?.id ?? null;
  const runtimeTaskSample = props.drilldownContext
    ? props.activeDrilldownTaskSample
    : props.project?.latest_task ?? null;

  const handleNavigateToTaskDetailFromLatestRun = () => {
    if (!runtimeTaskSample) {
      return;
    }
    props.onNavigateToTask?.(runtimeTaskSample.task_id, {
      runId: runtimeTaskSample.latest_run_id,
    });
    requestAnimationFrame(() => {
      document.getElementById("task-detail-panel")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  const handleNavigateToProjectLatestRunFromStrategyPreview = () => {
    if (!projectId || !runtimeTaskSample) {
      return;
    }
    props.onNavigateToProjectLatestRun({
      source: "strategy_preview",
      project_id: projectId,
      task_id: runtimeTaskSample.task_id,
      run_id: runtimeTaskSample.latest_run_id ?? null,
    });
  };

  return (
    <div data-testid="project-detail-section" className="mt-4 space-y-5">
      <ProjectDetailHeader
        project={props.project}
        projectName={projectName}
        projectSummary={projectSummary}
        projectStage={projectStage}
        projectStatus={projectStatus}
        projectCreatedAt={projectCreatedAt}
        projectUpdatedAt={projectUpdatedAt}
      />

      <ProjectDetailStatsGrid project={props.project} taskStats={taskStats} />

      <ProjectProgressRiskSummary project={props.project} />

      <ProjectSettingsEntryPanel project={props.project} detail={props.detail} />

      <ProjectRepositoryOverviewPage
        project={props.project}
        detail={props.detail}
        isLoading={props.isLoading}
        errorMessage={props.errorMessage}
      />

      <ProjectStageTimeline
        detail={props.detail}
        isAdvancing={props.isAdvancing}
        actionFeedback={props.stageActionFeedback}
        onAdvanceStage={props.onAdvanceStage}
      />

      <ProjectSopPanel projectId={projectId} detail={props.detail} />

      <ProjectMilestonePanel detail={props.detail} />

      <RoleFlowPanel
        projectName={projectName}
        tasks={projectTasks}
        isLoading={props.isLoading}
        errorMessage={props.errorMessage}
      />

      <StrategyDecisionPanel
        projectId={projectId}
        drilldownContext={props.drilldownContext}
        latestRunTaskSample={runtimeTaskSample}
        onNavigateToProjectLatestRun={handleNavigateToProjectLatestRunFromStrategyPreview}
        onNavigateToTaskDetail={props.onNavigateToTask}
      />

      <StrategyRuleEditor projectId={projectId} />

      <ProjectLatestTaskPreview
        latestTask={runtimeTaskSample}
        projectTasks={projectTasks}
        projectId={projectId}
        drilldownContext={props.drilldownContext}
        onNavigateToStrategyPreview={props.onNavigateToStrategyPreview}
        onNavigateToTask={props.onNavigateToTask}
        onNavigateToTaskDetailFromLatestRun={handleNavigateToTaskDetailFromLatestRun}
      />

      <ProjectTaskTree
        tasks={projectTasks}
        isLoading={props.isLoading}
        errorMessage={props.errorMessage}
      />
    </div>
  );
}
