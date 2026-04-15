import { StatusBadge } from "../../../components/StatusBadge";
import {
  formatCurrencyUsd,
  formatDateTime,
  formatTokenCount,
} from "../../../lib/format";
import {
  mapProjectRiskTone,
  mapProjectStatusTone,
  mapTaskStatusTone,
} from "../../../lib/status";
import { RepositoryOverviewPage as ProjectRepositoryOverviewPage } from "../../repositories/RepositoryOverviewPage";
import { RoleFlowPanel } from "../../roles/RoleFlowPanel";
import { ROLE_CODE_LABELS } from "../../roles/types";
import { StrategyDecisionPanel } from "../../strategy/StrategyDecisionPanel";
import { StrategyRuleEditor } from "../../strategy/StrategyRuleEditor";
import { ProjectLatestRunControlSurface } from "../ProjectLatestRunControlSurface";
import { ProjectSopPanel } from "../ProjectSopPanel";
import { ProviderSettingsPanel } from "../ProviderSettingsPanel";
import { ProjectMilestonePanel } from "../components/ProjectMilestonePanel";
import { ProjectStageTimeline } from "../components/ProjectStageTimeline";
import type {
  BossDrilldownContext,
  BossProjectItem,
  BossProjectLatestTask,
  ProjectDetail,
  ProjectDetailTaskItem,
} from "../types";
import {
  HUMAN_STATUS_LABELS,
  PROJECT_RISK_LABELS,
  PROJECT_STAGE_LABELS,
  PROJECT_STATUS_LABELS,
  TASK_PRIORITY_LABELS,
  TASK_RISK_LABELS,
  TASK_STATUS_LABELS,
} from "../types";

export function ProjectDetailSection(props: {
  project: BossProjectItem | null;
  detail: ProjectDetail | null;
  drilldownContext: BossDrilldownContext | null;
  activeDrilldownTaskSample: BossProjectLatestTask | null;
  onNavigateToStrategyPreview: (context: BossDrilldownContext) => void;
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
  const completionRatio =
    taskStats && taskStats.total_tasks > 0
      ? Math.round(
          (taskStats.completed_tasks / taskStats.total_tasks) *
            100,
        )
      : 0;
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

  return (
    <div data-testid="project-detail-section" className="mt-4 space-y-5">
      <div>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-xl font-semibold text-slate-50">
              {projectName}
            </h3>
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

          <div className="text-right text-xs text-slate-500">
            {projectCreatedAt ? <div>创建于 {formatDateTime(projectCreatedAt)}</div> : null}
            {projectUpdatedAt ? (
              <div className="mt-1">更新时间 {formatDateTime(projectUpdatedAt)}</div>
            ) : null}
          </div>
        </div>

        <p className="mt-4 text-sm leading-6 text-slate-300">
          {projectSummary}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <MiniStat label="完成度" value={`${completionRatio}%`} />
        <MiniStat
          label="总任务数"
          value={String(taskStats?.total_tasks ?? 0)}
        />
        <MiniStat
          label="执行中 / 待处理"
          value={`${taskStats?.running_tasks ?? 0} / ${taskStats?.pending_tasks ?? 0}`}
        />
        <MiniStat
          label="阻塞 / 待人工"
          value={`${taskStats?.blocked_tasks ?? 0} / ${taskStats?.waiting_human_tasks ?? 0}`}
        />
        <MiniStat
          label="Prompt Tokens"
          value={
            props.project
              ? formatTokenCount(props.project.prompt_tokens)
              : "仅老板首页汇总提供"
          }
        />
        <MiniStat
          label="预估成本"
          value={
            props.project
              ? formatCurrencyUsd(props.project.estimated_cost)
              : "仅老板首页汇总提供"
          }
        />
      </div>

      {props.project ? (
        <>
          <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
              最新进度
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-200">
              {props.project.latest_progress_summary}
            </p>
            <div className="mt-3 text-xs text-slate-500">
              最近进度时间：{formatDateTime(props.project.latest_progress_at)}
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
                关键风险
              </div>
              <StatusBadge
                label={
                  PROJECT_RISK_LABELS[props.project.risk_level] ??
                  props.project.risk_level
                }
                tone={mapProjectRiskTone(props.project.risk_level)}
              />
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-200">
              {props.project.key_risk_summary}
            </p>
            <div className="mt-3 text-xs text-slate-500">
              重点关注任务 {props.project.attention_task_count} 个，高风险任务{" "}
              {props.project.high_risk_task_count} 个。
            </div>
          </section>
        </>
      ) : (
        <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 text-sm leading-6 text-slate-300">
          该项目刚通过 Day03 规划入口创建，老板首页汇总数据还在刷新；你已经可以先查看下面的阶段守卫、角色协作链、任务树和草案来源。
        </section>
      )}

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

      <ProjectSopPanel
        projectId={props.detail?.id ?? props.project?.id ?? null}
        detail={props.detail}
      />

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
        onNavigateToTaskDetail={props.onNavigateToTask}
      />

      <StrategyRuleEditor projectId={projectId} />
      <ProviderSettingsPanel />

      <section
        data-testid="project-detail-latest-task-preview"
        className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4"
      >
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
          最近任务预览
        </div>
        {runtimeTaskSample ? (
          <div className="mt-3 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="text-sm font-medium text-slate-50">
                {runtimeTaskSample.title}
              </div>
              <StatusBadge
                label={
                  TASK_STATUS_LABELS[runtimeTaskSample.status] ??
                  runtimeTaskSample.status
                }
                tone={mapTaskStatusTone(runtimeTaskSample.status)}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <MiniStat
                label="优先级"
                value={
                  TASK_PRIORITY_LABELS[runtimeTaskSample.priority] ??
                  runtimeTaskSample.priority
                }
              />
              <MiniStat
                label="风险等级"
                value={
                  TASK_RISK_LABELS[runtimeTaskSample.risk_level] ??
                  runtimeTaskSample.risk_level
                }
              />
              <MiniStat
                label="人工状态"
                value={
                  HUMAN_STATUS_LABELS[runtimeTaskSample.human_status] ??
                  runtimeTaskSample.human_status
                }
              />
              <MiniStat
                label="最近运行"
                value={runtimeTaskSample.latest_run_status ?? "尚无运行"}
              />
            </div>
            {runtimeTaskSample.latest_run_summary ? (
              <p className="text-sm leading-6 text-slate-300">
                运行摘要：{runtimeTaskSample.latest_run_summary}
              </p>
            ) : null}
            <div data-testid="project-detail-latest-run-control-surface-slot">
              <ProjectLatestRunControlSurface
              latestTask={runtimeTaskSample}
              drilldownContext={props.drilldownContext}
              onNavigateToStrategyPreview={
                projectId && runtimeTaskSample?.latest_run_id
                  ? () =>
                      props.onNavigateToStrategyPreview({
                        source: props.drilldownContext?.source ?? "project_latest_run",
                        project_id: projectId,
                        task_id: runtimeTaskSample.task_id,
                        run_id: runtimeTaskSample.latest_run_id,
                      })
                  : null
              }
              />
            </div>
          </div>
        ) : props.detail && projectTasks.length > 0 ? (
          <p className="mt-3 text-sm leading-6 text-slate-300">
            老板首页聚合数据还未返回最新任务快照；当前可先查看上方的阶段守卫，以及下方的任务树与草案来源。
          </p>
        ) : (
          <p className="mt-3 text-sm leading-6 text-slate-400">
            当前还没有可展示的任务快照；可以先通过上方规划入口生成项目草案并映射任务。
          </p>
        )}
      </section>

      <section data-testid="project-detail-task-tree" className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
            任务树与草案来源
          </div>
          <span className="text-xs text-slate-500">
            {projectTasks.length} 个任务
          </span>
        </div>

        {props.isLoading ? (
          <p className="mt-3 text-sm leading-6 text-slate-400">
            正在加载项目任务树...
          </p>
        ) : props.errorMessage ? (
          <p className="mt-3 text-sm leading-6 text-rose-200">
            项目详情加载失败：{props.errorMessage}
          </p>
        ) : projectTasks.length > 0 ? (
          <div className="mt-4 space-y-3">
            {projectTasks.map((task) => (
              <ProjectTaskTreeRow key={task.id} task={task} />
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm leading-6 text-slate-400">
            当前还没有项目级任务树；可以先通过上方规划入口生成草案并应用到项目。
          </p>
        )}
      </section>
    </div>
  );
}

function MiniStat(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
        {props.label}
      </div>
      <div className="mt-2 text-sm font-medium text-slate-100">
        {props.value}
      </div>
    </div>
  );
}

function ProjectTaskTreeRow(props: { task: ProjectDetailTaskItem }) {
  const indent = Math.min(props.task.depth, 5) * 18;
  const dependencyText =
    props.task.depends_on_task_ids.length > 0
      ? `依赖 ${props.task.depends_on_task_ids.join(", ")}`
      : "根任务";

  return (
    <div
      className="rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-4"
      style={{ marginLeft: `${indent}px` }}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-slate-50">
              {props.task.title}
            </span>
            <StatusBadge
              label={TASK_STATUS_LABELS[props.task.status] ?? props.task.status}
              tone={mapTaskStatusTone(props.task.status)}
            />
            <StatusBadge
              label={TASK_PRIORITY_LABELS[props.task.priority] ?? props.task.priority}
              tone="info"
            />
            {props.task.owner_role_code ? (
              <StatusBadge
                label={`责任 ${ROLE_CODE_LABELS[props.task.owner_role_code] ?? props.task.owner_role_code}`}
                tone="success"
              />
            ) : null}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            {props.task.input_summary}
          </p>
        </div>

        <div className="flex flex-wrap gap-2 text-xs">
          <StatusBadge
            label={TASK_RISK_LABELS[props.task.risk_level] ?? props.task.risk_level}
            tone="warning"
          />
          <StatusBadge
            label={
              HUMAN_STATUS_LABELS[props.task.human_status] ?? props.task.human_status
            }
            tone={props.task.human_status === "none" ? "neutral" : "warning"}
          />
          <StatusBadge
            label={
              props.task.source_draft_id
                ? `草案 ${props.task.source_draft_id}`
                : "手动创建"
            }
            tone={props.task.source_draft_id ? "info" : "neutral"}
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
        <span>{dependencyText}</span>
        <span>子任务 {props.task.child_task_ids.length} 个</span>
        <span>更新时间 {formatDateTime(props.task.updated_at)}</span>
        {props.task.upstream_role_code ? (
          <span>
            上游 {ROLE_CODE_LABELS[props.task.upstream_role_code] ?? props.task.upstream_role_code}
          </span>
        ) : null}
        {props.task.downstream_role_code ? (
          <span>
            下游{" "}
            {ROLE_CODE_LABELS[props.task.downstream_role_code] ?? props.task.downstream_role_code}
          </span>
        ) : null}
      </div>

      {props.task.acceptance_criteria.length > 0 ? (
        <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-300">
          {props.task.acceptance_criteria.map((criterion) => (
            <li
              key={criterion}
              className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-2"
            >
              {criterion}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
