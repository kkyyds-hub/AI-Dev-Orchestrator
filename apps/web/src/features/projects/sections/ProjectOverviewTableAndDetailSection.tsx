import { StatusBadge } from "../../../components/StatusBadge";
import { formatCurrencyUsd, formatDateTime } from "../../../lib/format";
import {
  mapProjectRiskTone,
  mapProjectStatusTone,
  mapTaskStatusTone,
} from "../../../lib/status";
import { ProjectTable } from "../components/ProjectTable";
import { ProjectDirectorSourceCard } from "../components/ProjectDirectorSourceCard";
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
  TASK_STATUS_LABELS,
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
  onNavigateToRepositoryWorkspace: () => void;
  onNavigateToStrategyPreview: (context: BossDrilldownContext) => void;
  onNavigateToProjectLatestRun: (context: BossDrilldownContext) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onAdvanceStage: (note: string | null) => Promise<void> | void;
  isAdvancingStage: boolean;
  stageActionFeedback: StageActionFeedback;
  isProjectDetailLoading: boolean;
  projectDetailErrorMessage: string | null;
  onCreateProjectDraft: () => void;
};

export function ProjectOverviewTableAndDetailSection(
  props: ProjectOverviewTableAndDetailSectionProps,
) {
  return (
    <section
      data-testid="project-overview-detail-workspace"
      className="grid gap-7 2xl:grid-cols-[minmax(0,1fr)_minmax(380px,420px)]"
    >
      <ProjectTable
        projects={props.projects}
        selectedProjectId={props.selectedProjectId}
        onSelectProject={props.onSelectProject}
        maxRows={6}
        onCreateProjectDraft={props.onCreateProjectDraft}
      />

      <aside
        id="project-detail"
        data-testid="project-detail-panel"
        className="scroll-mt-24 border border-[#333333] px-5 py-5 xl:sticky xl:top-24 xl:self-start"
      >
        <div className="border-b border-[#333333] pb-4">
          <p className="text-xs font-medium tracking-[0.24em] text-zinc-600">
            选中项目
          </p>
          <h2 className="mt-2 text-lg font-semibold text-zinc-100">当前项目摘要</h2>
          <p className="mt-1 text-sm text-zinc-500">
            汇总状态、任务、仓库和运行信息；进展与风险可按需查看。
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
            onNavigateToRepositoryWorkspace={props.onNavigateToRepositoryWorkspace}
          />
        ) : (
          <div className="mt-4 border border-dashed border-[#3a3a3a] px-4 py-8 text-center text-sm text-zinc-500">
            选择一个项目后，在这里查看精简摘要。
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
  onNavigateToRepositoryWorkspace: () => void;
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
    <div data-testid="project-detail-section" className="mt-4 space-y-4">
      <div>
        <div className="space-y-3">
          <h3 className="break-words text-xl font-semibold leading-7 text-zinc-50">
            {projectName}
          </h3>
          <div className="flex flex-wrap gap-2">
            <StatusBadge
              label={PROJECT_STAGE_LABELS[projectStage] ?? "未知阶段"}
              tone="info"
            />
            <StatusBadge
              label={PROJECT_STATUS_LABELS[projectStatus] ?? "未知状态"}
              tone={mapProjectStatusTone(projectStatus)}
            />
            {props.project ? (
              <StatusBadge
                label={
                  PROJECT_RISK_LABELS[props.project.risk_level] ??
                  "未知风险"
                }
                tone={mapProjectRiskTone(props.project.risk_level)}
              />
            ) : null}
          </div>
          {props.project ? (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-600">
              <span>更新 {formatDateTime(props.project.updated_at)}</span>
              <span>{formatCurrencyUsd(props.project.estimated_cost)}</span>
            </div>
          ) : null}
        </div>
        <p className="mt-4 line-clamp-2 text-sm leading-6 text-zinc-400">
          {projectSummary}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={props.onNavigateToRepositoryWorkspace}
            className="inline-flex rounded border border-zinc-300 bg-zinc-100 px-3 py-2 text-xs font-semibold text-zinc-950 transition hover:bg-white"
          >
            进入仓库工作区
          </button>
          {!repositoryWorkspace ? (
            <span className="self-center text-xs leading-5 text-amber-100">
              未绑定也可先进入，工作区内会引导去设置页绑定主仓库。
            </span>
          ) : null}
        </div>
      </div>

      <ProjectDirectorSourceCard
        project={props.project}
        detail={props.detail}
        compact
      />

      {taskStats ? <TaskStatsLine taskStats={taskStats} /> : null}

      <div className="space-y-3 border-t border-[#333333] pt-4">
        <div className="text-xs font-medium tracking-[0.22em] text-zinc-600">
          仓库上下文
        </div>
        <div className="grid gap-2 text-sm leading-6 text-zinc-400">
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
          <div className="space-y-3">
            <div className="min-w-0">
              <div className="text-xs font-medium tracking-[0.22em] text-zinc-600">
                最新任务
              </div>
              <div className="mt-2 line-clamp-2 text-sm font-medium leading-6 text-zinc-100">
                {latestTask.title}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusBadge
                label={TASK_STATUS_LABELS[latestTask.status] ?? "未知任务状态"}
                tone={mapTaskStatusTone(latestTask.status)}
              />
            </div>
          </div>
          <button
            type="button"
            onClick={() =>
              props.onNavigateToTask?.(latestTask.task_id, {
                runId: latestTask.latest_run_id,
              })
            }
            className="inline-flex whitespace-nowrap rounded border border-[#4a4a4a] bg-transparent px-3 py-2 text-xs font-medium text-zinc-100 transition hover:border-zinc-500 hover:bg-[#292929]"
          >
            打开任务
          </button>
        </div>
      ) : null}

      {props.project || latestTask?.latest_run_summary ? (
        <details className="group border-t border-[#333333] pt-4">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm text-zinc-400 transition hover:text-zinc-100">
            <span>展开进展、风险与运行摘要</span>
            <span className="text-xs text-zinc-600 group-open:hidden">展开</span>
            <span className="hidden text-xs text-zinc-600 group-open:inline">收起</span>
          </summary>
          <div className="mt-4 space-y-4">
            {props.project ? (
              <div className="space-y-3">
                <LongTextBlock title="最新进展" text={props.project.latest_progress_summary} />
                <LongTextBlock title="关键风险" text={props.project.key_risk_summary} />
              </div>
            ) : null}
            {latestTask?.latest_run_summary ? (
              <LongTextBlock title="运行摘要" text={latestTask.latest_run_summary} />
            ) : null}
          </div>
        </details>
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
  const completionRatio = props.taskStats.total_tasks
    ? Math.round((props.taskStats.completed_tasks / props.taskStats.total_tasks) * 100)
    : 0;

  const stats = [
    ["完成率", `${completionRatio}%`, `${props.taskStats.completed_tasks}/${props.taskStats.total_tasks}`],
    ["执行中", String(props.taskStats.running_tasks), "运行任务"],
    ["待处理", String(props.taskStats.pending_tasks), "排队任务"],
    ["阻塞/人工", `${props.taskStats.blocked_tasks}/${props.taskStats.waiting_human_tasks}`, "需关注"],
  ];

  return (
    <div className="grid grid-cols-2 gap-3 border-t border-[#333333] pt-4">
      {stats.map(([label, value, hint]) => (
        <div key={label} className="border border-[#333333] px-3 py-3">
          <div className="text-xs text-zinc-600">{label}</div>
          <div className="mt-1 font-mono text-xl font-semibold text-zinc-100">
            {value}
          </div>
          <div className="mt-1 text-xs text-zinc-600">{hint}</div>
        </div>
      ))}
    </div>
  );
}

function SummaryRow(props: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[3rem_minmax(0,1fr)] gap-3 border-b border-[#333333]/70 pb-2 last:border-b-0">
      <span className="text-xs text-zinc-600">{props.label}</span>
      <span className="min-w-0 truncate text-zinc-300" title={props.value}>
        {props.value}
      </span>
    </div>
  );
}

function LongTextBlock(props: { title: string; text: string }) {
  return (
    <div>
      <div className="text-xs text-zinc-600">{props.title}</div>
      <p className="mt-2 text-sm leading-6 text-zinc-400">{props.text}</p>
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
