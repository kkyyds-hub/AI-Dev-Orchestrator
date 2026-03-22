import { useEffect, useMemo, useRef, useState } from "react";

import { StatusBadge } from "../../components/StatusBadge";
import {
  formatCurrencyUsd,
  formatDateTime,
  formatTokenCount,
} from "../../lib/format";
import {
  mapBudgetPressureTone,
  mapProjectRiskTone,
  mapProjectStatusTone,
  mapTaskStatusTone,
} from "../../lib/status";
import { ApprovalInboxPage } from "../approvals/ApprovalInboxPage";
import { DeliverableCenterPage } from "../deliverables/DeliverableCenterPage";
import { RoleCatalogPage } from "../roles/RoleCatalogPage";
import { RoleFlowPanel } from "../roles/RoleFlowPanel";
import { RoleWorkbenchPage } from "../roles/RoleWorkbenchPage";
import { ROLE_CODE_LABELS } from "../roles/types";
import { SkillRegistryPage } from "../skills/SkillRegistryPage";
import { StrategyDecisionPanel } from "../strategy/StrategyDecisionPanel";
import { StrategyRuleEditor } from "../strategy/StrategyRuleEditor";
import { RepositoryOverviewPage as ProjectRepositoryOverviewPage } from "../repositories/RepositoryOverviewPage";
import { RepositoryHomeCard } from "../repositories/RepositoryHomeCard";
import { MemorySearchPanel } from "./MemorySearchPanel";
import { ProjectMemoryPanel } from "./ProjectMemoryPanel";
import { ProjectCreateFlow } from "./ProjectCreateFlow";
import { ProjectRetrospectivePanel } from "./ProjectRetrospectivePanel";
import { ProjectSopPanel } from "./ProjectSopPanel";
import { ProjectTimelinePage } from "./ProjectTimelinePage";
import { ProjectMilestonePanel } from "./components/ProjectMilestonePanel";
import { ProjectSummaryCards } from "./components/ProjectSummaryCards";
import { ProjectStageTimeline } from "./components/ProjectStageTimeline";
import { ProjectTable } from "./components/ProjectTable";
import {
  useAdvanceProjectStage,
  useBossProjectOverview,
  useProjectDetail,
} from "./hooks";
import type { BossProjectItem, ProjectDetail, ProjectDetailTaskItem } from "./types";
import {
  HUMAN_STATUS_LABELS,
  PROJECT_RISK_LABELS,
  PROJECT_STAGE_LABELS,
  PROJECT_STATUS_LABELS,
  TASK_PRIORITY_LABELS,
  TASK_RISK_LABELS,
  TASK_STATUS_LABELS,
} from "./types";

type ProjectOverviewPageProps = {
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

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
    },
  ) => {
    setSelectedProjectId(projectId);
    setStageActionFeedback(null);
    setRequestedDeliverableId(options?.requestedDeliverableId ?? null);
    setRequestedApprovalId(options?.requestedApprovalId ?? null);

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
      <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">
            V4 Day04 Boss Entry
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-50">
            老板首页、项目总览与仓库入口整合
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-slate-300">
            用户进入系统时先看项目全局，再同步看见仓库是否已绑定、最新目录快照和当前变更会话；Day04 只把仓库视角整合进老板入口与项目详情，不扩展到文件级编辑、代码上下文包、验证证据视图或任何真实 Git 写操作。
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
          <StatusBadge
            label={overviewQuery.data?.budget.strategy_label ?? "预算快照"}
            tone={mapBudgetPressureTone(
              overviewQuery.data?.budget.pressure_level ?? "normal",
            )}
          />
          <span>最近刷新：{lastUpdatedText}</span>
        </div>
      </header>

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
            <section className="space-y-4">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-slate-50">
                    仓库入口概览
                  </h2>
                  <p className="mt-1 text-sm text-slate-400">
                    把项目阶段统计、任务概览和仓库摘要放在同一屏联动查看；每张卡片只展示绑定、快照和变更会话的 Day04 最小入口。
                  </p>
                </div>
                <div className="text-xs text-slate-500">
                  默认展示当前排序最靠前的 {featuredProjects.length} 个项目
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-3">
                {featuredProjects.map((project) => (
                  <RepositoryHomeCard
                    key={`repository-home-${project.id}`}
                    workspace={project.repository_workspace}
                    snapshot={project.latest_repository_snapshot}
                    changeSession={project.current_change_session}
                    title={project.name}
                    description={project.summary}
                    variant="compact"
                    actionLabel={
                      project.id === selectedProjectId ? "已在详情中" : "查看项目详情"
                    }
                    onAction={() =>
                      handleSelectProject(project.id, {
                        scrollIntoDetail: true,
                      })
                    }
                  />
                ))}
              </div>
            </section>
          ) : null}

          {featuredProjects.length > 0 ? (
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-50">
                  重点项目卡片
                </h2>
                <p className="text-xs text-slate-500">
                  默认按阻塞风险和最近进展排序
                </p>
              </div>

              <div className="grid gap-4 xl:grid-cols-3">
                {featuredProjects.map((project) => (
                  <button
                    key={project.id}
                    type="button"
                    onClick={() =>
                      handleSelectProject(project.id, {
                        scrollIntoDetail: true,
                      })
                    }
                    className={`rounded-2xl border p-5 text-left transition ${
                      project.id === selectedProjectId
                        ? "border-cyan-500/40 bg-cyan-500/10 shadow-lg shadow-cyan-950/20"
                        : "border-slate-800 bg-slate-900/70 hover:border-slate-700 hover:bg-slate-900"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-lg font-semibold text-slate-50">
                          {project.name}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <StatusBadge
                            label={
                              PROJECT_STAGE_LABELS[project.stage] ??
                              project.stage
                            }
                            tone="info"
                          />
                          <StatusBadge
                            label={
                              PROJECT_STATUS_LABELS[project.status] ??
                              project.status
                            }
                            tone={mapProjectStatusTone(project.status)}
                          />
                        </div>
                      </div>

                      <StatusBadge
                        label={
                          PROJECT_RISK_LABELS[project.risk_level] ??
                          project.risk_level
                        }
                        tone={mapProjectRiskTone(project.risk_level)}
                      />
                    </div>

                    <p className="mt-4 text-sm leading-6 text-slate-300">
                      {project.summary}
                    </p>
                    <p className="mt-4 text-sm leading-6 text-slate-200">
                      {project.latest_progress_summary}
                    </p>
                    <p className="mt-3 text-xs leading-6 text-slate-400">
                      {project.key_risk_summary}
                    </p>

                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <MiniStat
                        label="任务状态"
                        value={`${project.task_stats.completed_tasks}/${project.task_stats.total_tasks} 完成`}
                      />
                      <MiniStat
                        label="预估成本"
                        value={formatCurrencyUsd(project.estimated_cost)}
                      />
                    </div>
                  </button>
                ))}
              </div>
            </section>
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
              className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-slate-950/30"
            >
              <h2 className="text-lg font-semibold text-slate-50">项目详情</h2>
              <p className="mt-1 text-sm text-slate-400">
                从项目卡片或列表进入，查看老板视角的项目详情；Day04 已把仓库绑定、目录快照和当前变更会话合并到同一详情视图中，仓库首页仍只保留最小入口，不扩展到文件级编辑、代码上下文包或验证证据视图。
              </p>

              {selectedProject || selectedProjectDetail ? (
                <ProjectDetailBody
                  project={selectedProject}
                  detail={selectedProjectDetail}
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

function ProjectDetailBody(props: {
  project: BossProjectItem | null;
  detail: ProjectDetail | null;
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

  return (
    <div className="mt-4 space-y-5">
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

      <StrategyDecisionPanel projectId={projectId} />

      <StrategyRuleEditor projectId={projectId} />

      <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">
          最近任务预览
        </div>
        {props.project?.latest_task ? (
          <div className="mt-3 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="text-sm font-medium text-slate-50">
                {props.project.latest_task.title}
              </div>
              <StatusBadge
                label={
                  TASK_STATUS_LABELS[props.project.latest_task.status] ??
                  props.project.latest_task.status
                }
                tone={mapTaskStatusTone(props.project.latest_task.status)}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <MiniStat
                label="优先级"
                value={
                  TASK_PRIORITY_LABELS[props.project.latest_task.priority] ??
                  props.project.latest_task.priority
                }
              />
              <MiniStat
                label="风险等级"
                value={
                  TASK_RISK_LABELS[props.project.latest_task.risk_level] ??
                  props.project.latest_task.risk_level
                }
              />
              <MiniStat
                label="人工状态"
                value={
                  HUMAN_STATUS_LABELS[props.project.latest_task.human_status] ??
                  props.project.latest_task.human_status
                }
              />
              <MiniStat
                label="最近运行"
                value={props.project.latest_task.latest_run_status ?? "尚无运行"}
              />
            </div>
            {props.project.latest_task.latest_run_summary ? (
              <p className="text-sm leading-6 text-slate-300">
                运行摘要：{props.project.latest_task.latest_run_summary}
              </p>
            ) : null}
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

      <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
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
