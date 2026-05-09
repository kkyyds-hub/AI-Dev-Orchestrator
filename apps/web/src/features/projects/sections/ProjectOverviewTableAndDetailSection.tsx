import { StatusBadge } from "../../../components/StatusBadge";
import { formatCurrencyUsd, formatDateTime } from "../../../lib/format";
import {
  mapProjectRiskTone,
  mapProjectStatusTone,
  mapTaskStatusTone,
} from "../../../lib/status";
import { ProjectTable } from "../components/ProjectTable";
import type {
  BossDrilldownContext,
  BossDrilldownFeedback,
  BossProjectItem,
  BossProjectLatestTask,
  ProjectDetail,
  ProjectTaskStats,
} from "../types";
import {
  PROJECT_RISK_LABELS,
  PROJECT_STAGE_LABELS,
  PROJECT_STATUS_LABELS,
} from "../types";

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
      className="grid gap-8 xl:grid-cols-[minmax(0,1.62fr)_minmax(340px,0.82fr)]"
    >
      <ProjectTable
        projects={props.projects}
        selectedProjectId={props.selectedProjectId}
        onSelectProject={props.onSelectProject}
        maxRows={6}
      />

      <aside
        id="project-detail"
        data-testid="project-detail-panel"
        className="scroll-mt-24 border-l border-[#333333] pl-5 xl:sticky xl:top-24"
      >
        <div className="border-b border-[#333333] pb-4">
          <p className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-600">
            选中项目
          </p>
          <h2 className="mt-2 text-lg font-semibold text-zinc-100">项目摘要</h2>
          <p className="mt-1 text-sm text-zinc-500">
            只展示决策所需的状态、任务、仓库和最新运行入口。
          </p>
        </div>

        {props.drilldownFeedback ? (
          <div
            data-testid="project-detail-drilldown-feedback"
            className="mt-4 border-l-2 border-l-amber-300/70 py-2 pl-3 text-xs leading-5 text-amber-100"
          >
            {props.drilldownFeedback.text}
          </div>
        ) : null}

        {props.selectedProject || props.selectedProjectDetail ? (
          <CompactProjectDetail
            project={props.selectedProject}
            detail={props.selectedProjectDetail}
            activeDrilldownTaskSample={props.activeDrilldownTaskSample}
            isLoading={props.isProjectDetailLoading}
            errorMessage={props.projectDetailErrorMessage}
            onNavigateToTask={props.onNavigateToTask}
          />
        ) : (
          <div className="mt-4 border border-dashed border-[#3a3a3a] px-4 py-8 text-center text-sm text-zinc-500">
            选择一个项目后，在这里查看精简详情摘要。
          </div>
        )}
      </aside>
    </section>
  );
}

function CompactProjectDetail(props: {
  project: BossProjectItem | null;
  detail: ProjectDetail | null;
  activeDrilldownTaskSample: BossProjectLatestTask | null;
  isLoading: boolean;
  errorMessage: string | null;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
}) {
  const projectName = props.project?.name ?? props.detail?.name ?? "未命名项目";
  const projectSummary = props.project?.summary ?? props.detail?.summary ?? "暂无项目摘要。";
  const projectStage = props.project?.stage ?? props.detail?.stage ?? "planning";
  const projectStatus = props.project?.status ?? props.detail?.status ?? "active";
  const taskStats = props.project?.task_stats ?? props.detail?.task_stats ?? null;
  const repositoryWorkspace =
    props.project?.repository_workspace ?? props.detail?.repository_workspace ?? null;
  const repositorySnapshot =
    props.project?.latest_repository_snapshot ??
    props.detail?.latest_repository_snapshot ??
    null;
  const changeSession =
    props.project?.current_change_session ?? props.detail?.current_change_session ?? null;
  const latestTask = props.activeDrilldownTaskSample ?? props.project?.latest_task ?? null;

  return (
    <div data-testid="project-detail-section" className="mt-4 space-y-5">
      <div>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-xl font-semibold text-zinc-50">{projectName}</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              <StatusBadge
                label={PROJECT_STAGE_LABELS[projectStage] ?? projectStage}
                tone="info"
              />
              <StatusBadge
                label={PROJECT_STATUS_LABELS[projectStatus] ?? projectStatus}
                tone={mapProjectStatusTone(projectStatus)}
              />
              {props.project ? (
                <StatusBadge
                  label={
                    PROJECT_RISK_LABELS[props.project.risk_level] ??
                    props.project.risk_level
                  }
                  tone={mapProjectRiskTone(props.project.risk_level)}
                />
              ) : null}
            </div>
          </div>
          {props.project ? (
            <div className="text-right text-xs leading-5 text-zinc-600">
              <div>{formatDateTime(props.project.updated_at)}</div>
              <div>{formatCurrencyUsd(props.project.estimated_cost)}</div>
            </div>
          ) : null}
        </div>
        <p className="mt-4 text-sm leading-6 text-zinc-400">{projectSummary}</p>
      </div>

      {taskStats ? <TaskStatsLine taskStats={taskStats} /> : null}

      {props.project ? (
        <div className="space-y-2 border-t border-[#333333] pt-4">
          <div className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-600">
            进展 / 风险
          </div>
          <p className="text-sm leading-6 text-zinc-400">
            {props.project.latest_progress_summary}
          </p>
          <p className="text-xs leading-5 text-zinc-500">
            {props.project.key_risk_summary}
          </p>
        </div>
      ) : null}

      <div className="space-y-3 border-t border-[#333333] pt-4">
        <div className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-600">
          仓库上下文
        </div>
        <div className="space-y-2 text-sm leading-6 text-zinc-400">
          <SummaryRow
            label="仓库"
            value={repositoryWorkspace?.display_name ?? "待绑定主仓库"}
          />
          <SummaryRow
            label="快照"
            value={buildSnapshotSummary(repositorySnapshot)}
          />
          <SummaryRow
            label="会话"
            value={buildChangeSessionSummary(changeSession)}
          />
        </div>
      </div>

      {latestTask ? (
        <div className="space-y-3 border-t border-[#333333] pt-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-xs font-medium uppercase tracking-[0.22em] text-zinc-600">
                最新任务
              </div>
              <div className="mt-2 text-sm font-medium text-zinc-100">
                {latestTask.title}
              </div>
            </div>
            <StatusBadge
              label={latestTask.status}
              tone={mapTaskStatusTone(latestTask.status)}
            />
          </div>
          {latestTask.latest_run_summary ? (
            <p className="text-xs leading-5 text-zinc-500">
              {latestTask.latest_run_summary}
            </p>
          ) : null}
          <button
            type="button"
            onClick={() =>
              props.onNavigateToTask?.(latestTask.task_id, {
                runId: latestTask.latest_run_id,
              })
            }
            className="inline-flex rounded border border-[#4a4a4a] bg-transparent px-3 py-2 text-xs font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929]"
          >
            打开任务
          </button>
        </div>
      ) : null}

      {props.isLoading ? (
        <p className="border-t border-[#333333] pt-4 text-xs text-zinc-600">
          正在补齐项目详情...
        </p>
      ) : null}

      {props.errorMessage ? (
        <p className="border-l-2 border-l-rose-400 py-2 pl-3 text-xs leading-5 text-rose-100">
          项目详情加载失败：{props.errorMessage}
        </p>
      ) : null}
    </div>
  );
}

function TaskStatsLine(props: { taskStats: ProjectTaskStats }) {
  const stats = [
    ["总任务", props.taskStats.total_tasks],
    ["完成", props.taskStats.completed_tasks],
    ["执行中", props.taskStats.running_tasks],
    ["阻塞/人工", `${props.taskStats.blocked_tasks}/${props.taskStats.waiting_human_tasks}`],
  ];

  return (
    <div className="grid grid-cols-2 gap-x-5 gap-y-3 border-t border-[#333333] pt-4 sm:grid-cols-4 xl:grid-cols-2">
      {stats.map(([label, value]) => (
        <div key={label}>
          <div className="text-xs text-zinc-600">{label}</div>
          <div className="mt-1 font-mono text-xl font-semibold text-zinc-100">
            {value}
          </div>
        </div>
      ))}
    </div>
  );
}

function SummaryRow(props: { label: string; value: string }) {
  return (
    <div className="flex gap-4 border-b border-[#333333]/70 pb-2 last:border-b-0">
      <span className="w-12 shrink-0 text-xs text-zinc-600">{props.label}</span>
      <span className="min-w-0 break-words text-zinc-300">{props.value}</span>
    </div>
  );
}

function buildSnapshotSummary(
  snapshot: BossProjectItem["latest_repository_snapshot"] | ProjectDetail["latest_repository_snapshot"],
) {
  if (!snapshot) {
    return "尚未生成目录快照";
  }
  if (snapshot.status === "failed") {
    return `刷新失败 · ${formatDateTime(snapshot.scanned_at)}`;
  }
  return `${formatDateTime(snapshot.scanned_at)} · ${snapshot.directory_count} 目录 / ${snapshot.file_count} 文件`;
}

function buildChangeSessionSummary(
  changeSession: BossProjectItem["current_change_session"] | ProjectDetail["current_change_session"],
) {
  if (!changeSession) {
    return "尚未记录变更会话";
  }
  if (changeSession.workspace_status === "dirty") {
    return `${changeSession.current_branch} · ${changeSession.dirty_file_count} 项未提交`;
  }
  return `${changeSession.current_branch} · 基线 ${changeSession.baseline_branch}`;
}
