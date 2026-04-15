import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { StatusBadge } from "../../components/StatusBadge";
import { requestJson } from "../../lib/http";
import { formatDateTime } from "../../lib/format";
import { mapBudgetPressureTone } from "../../lib/status";
import { ApprovalInboxPage } from "../approvals/ApprovalInboxPage";
import { DeliverableCenterPage } from "../deliverables/DeliverableCenterPage";
import { RoleCatalogPage } from "../roles/RoleCatalogPage";
import { RoleWorkbenchPage } from "../roles/RoleWorkbenchPage";
import { SkillRegistryPage } from "../skills/SkillRegistryPage";
import { RepositoryHomeCard } from "../repositories/RepositoryHomeCard";
import { MemorySearchPanel } from "./MemorySearchPanel";
import { ProjectMemoryPanel } from "./ProjectMemoryPanel";
import { ProjectCreateFlow } from "./ProjectCreateFlow";
import { ProjectRetrospectivePanel } from "./ProjectRetrospectivePanel";
import { ProjectTimelinePage } from "./ProjectTimelinePage";
import { ProjectSummaryCards } from "./components/ProjectSummaryCards";
import { ProjectDeliverySnapshotCard } from "./components/ProjectDeliverySnapshotCard";
import { ProjectTable } from "./components/ProjectTable";
import { ProjectDetailSection } from "./sections/ProjectDetailSection";
import { FeaturedProjectsSection } from "./sections/FeaturedProjectsSection";
import {
  useAdvanceProjectStage,
  useBossProjectOverview,
  useProjectDetail,
} from "./hooks";
import type {
  BossDrilldownContext,
  BossDrilldownSource,
  BossProjectItem,
  BossProjectLatestTask,
} from "./types";
import type { TaskDetail } from "../task-detail/types";

type ProjectOverviewPageProps = {
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

type ProjectDay15FlowOverview = {
  project_id: string;
  project_name: string;
  generated_at: string;
  overall_status: "in_progress" | "blocked" | "ready_for_review";
  summary: string;
  completed_step_count: number;
  total_step_count: number;
  blocked_step_count: number;
  selected_change_batch_id: string | null;
  selected_change_batch_title: string | null;
  release_status: string | null;
  release_qualification_established: boolean;
  git_write_actions_triggered: boolean;
};

type BossDrilldownEventDetail = {
  source?: BossDrilldownSource;
  projectId?: string | null;
  taskId?: string | null;
  runId?: string | null;
};

type TaskOwnershipResponse = {
  project_id: string | null;
};

function buildBossDrilldownHash(detail: BossDrilldownContext): string {
  const params = new URLSearchParams();
  params.set("source", detail.source);
  params.set("taskId", detail.task_id);
  if (detail.project_id) {
    params.set("projectId", detail.project_id);
  }
  if (detail.run_id) {
    params.set("runId", detail.run_id);
  }
  return `#boss-drilldown?${params.toString()}`;
}

function parseBossDrilldownHash(hashValue: string): BossDrilldownEventDetail | null {
  if (!hashValue.startsWith("#boss-drilldown")) {
    return null;
  }
  const queryIndex = hashValue.indexOf("?");
  const searchValue = queryIndex >= 0 ? hashValue.slice(queryIndex + 1) : "";
  const params = new URLSearchParams(searchValue);
  const taskId = params.get("taskId");
  if (!taskId) {
    return null;
  }

  return {
    source: (params.get("source") as BossDrilldownSource | null) ?? "home_latest_run",
    projectId: params.get("projectId"),
    taskId,
    runId: params.get("runId"),
  };
}

function buildTaskSampleFromDetail(
  detail: TaskDetail,
  preferredRunId: string | null,
): BossProjectLatestTask | null {
  const matchedRun =
    (preferredRunId
      ? detail.runs.find((run) => run.id === preferredRunId)
      : null) ?? detail.latest_run;
  if (!matchedRun) {
    return null;
  }

  return {
    task_id: detail.id,
    title: detail.title,
    status: detail.status,
    priority: detail.priority,
    risk_level: detail.risk_level,
    human_status: detail.human_status,
    updated_at: detail.updated_at,
    latest_run_status: matchedRun.status,
    latest_run_summary: matchedRun.result_summary,
    latest_run_id: matchedRun.id,
    latest_run_log_path: matchedRun.log_path,
    latest_run_model_name: null,
    latest_run_model_tier: null,
    latest_run_strategy_code: null,
    latest_run_provider_key: matchedRun.provider_key,
    latest_run_prompt_template_key: matchedRun.prompt_template_key,
    latest_run_prompt_template_version: matchedRun.prompt_template_version,
    latest_run_prompt_char_count: matchedRun.prompt_char_count,
    latest_run_token_accounting_mode: matchedRun.token_accounting_mode,
    latest_run_token_pricing_source: matchedRun.token_pricing_source,
    latest_run_provider_receipt_id: matchedRun.provider_receipt_id,
    latest_run_prompt_tokens: matchedRun.prompt_tokens,
    latest_run_completion_tokens: matchedRun.completion_tokens,
    latest_run_total_tokens: matchedRun.total_tokens,
    latest_run_estimated_cost: matchedRun.estimated_cost,
    latest_run_created_at: matchedRun.created_at,
    latest_run_finished_at: matchedRun.finished_at,
    latest_run_role_model_policy_source: matchedRun.role_model_policy_source,
    latest_run_role_model_policy_desired_tier:
      matchedRun.role_model_policy_desired_tier,
    latest_run_role_model_policy_adjusted_tier:
      matchedRun.role_model_policy_adjusted_tier,
    latest_run_role_model_policy_final_tier: matchedRun.role_model_policy_final_tier,
    latest_run_role_model_policy_stage_override_applied:
      matchedRun.role_model_policy_stage_override_applied,
  };
}

function useProjectDay15FlowOverview(projectId: string | null) {
  return useQuery({
    queryKey: ["project-day15-repository-flow", projectId],
    queryFn: () =>
      requestJson<ProjectDay15FlowOverview>(
        `/projects/${projectId}/day15-repository-flow`,
      ),
    enabled: Boolean(projectId),
  });
}

export function ProjectOverviewPage(props: ProjectOverviewPageProps) {
  const overviewQuery = useBossProjectOverview();
  const detailRef = useRef<HTMLElement | null>(null);
  const lastAppliedDrilldownHashRef = useRef<string | null>(null);
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
  const [drilldownContext, setDrilldownContext] = useState<BossDrilldownContext | null>(
    null,
  );
  const [drilldownFeedback, setDrilldownFeedback] = useState<{
    tone: "success" | "warning";
    text: string;
  } | null>(null);

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
  const day15FlowOverviewQuery = useProjectDay15FlowOverview(selectedProjectId);
  const selectedProjectDetail = projectDetailQuery.data ?? null;
  const drilldownTaskDetailQuery = useQuery({
    queryKey: ["project-drilldown-task-detail", drilldownContext?.task_id],
    queryFn: () =>
      requestJson<TaskDetail>(`/tasks/${drilldownContext?.task_id ?? ""}/detail`),
    enabled: Boolean(drilldownContext?.task_id),
  });
  const activeDrilldownTaskSample = useMemo<BossProjectLatestTask | null>(() => {
    if (!drilldownContext || !drilldownTaskDetailQuery.data) {
      return null;
    }
    return buildTaskSampleFromDetail(
      drilldownTaskDetailQuery.data,
      drilldownContext.run_id,
    );
  }, [drilldownContext, drilldownTaskDetailQuery.data]);

  const featuredProjects = useMemo(() => projects.slice(0, 3), [projects]);
  const lastUpdatedText = overviewQuery.dataUpdatedAt
    ? formatDateTime(new Date(overviewQuery.dataUpdatedAt).toISOString())
    : "尚未刷新";

  const resolveProjectOwnershipByTaskId = async (
    taskId: string,
  ): Promise<string | null> => {
    const task = await requestJson<TaskOwnershipResponse>(`/tasks/${taskId}`);
    return task.project_id ?? null;
  };

  const handleSelectProject = (
    projectId: string,
    options?: {
      scrollIntoDetail?: boolean;
      requestedDeliverableId?: string | null;
      requestedApprovalId?: string | null;
      preserveDrilldownContext?: boolean;
    },
  ) => {
    setSelectedProjectId(projectId);
    setStageActionFeedback(null);
    setRequestedDeliverableId(options?.requestedDeliverableId ?? null);
    setRequestedApprovalId(options?.requestedApprovalId ?? null);
    if (!options?.preserveDrilldownContext) {
      setDrilldownContext(null);
      setDrilldownFeedback(null);
    }

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

  const handleBossDrilldownNavigate = async (input: BossDrilldownEventDetail) => {
    if (!input.taskId) {
      return;
    }

    let resolvedProjectId: string | null = null;
    try {
      resolvedProjectId = await resolveProjectOwnershipByTaskId(input.taskId);
    } catch (error) {
      setDrilldownFeedback({
        tone: "warning",
        text:
          error instanceof Error
            ? `Unable to resolve authoritative project ownership for task ${input.taskId}: ${error.message}`
            : `Unable to resolve authoritative project ownership for task ${input.taskId}.`,
      });
      return;
    }

    if (!resolvedProjectId) {
      setDrilldownFeedback({
        tone: "warning",
        text:
          "Unable to resolve authoritative project ownership for this task. Drill-down was not applied.",
      });
      return;
    }

    let availableProjects = projects;
    if (!availableProjects.some((project) => project.id === resolvedProjectId)) {
      const refreshedOverview = await overviewQuery.refetch();
      availableProjects = refreshedOverview.data?.projects ?? availableProjects;
    }
    if (!availableProjects.some((project) => project.id === resolvedProjectId)) {
      setDrilldownFeedback({
        tone: "warning",
        text: `Task ${input.taskId} belongs to project ${resolvedProjectId}, but that project is not available in current homepage overview.`,
      });
      return;
    }

    const nextContext: BossDrilldownContext = {
      source: input.source ?? "home_latest_run",
      project_id: resolvedProjectId,
      task_id: input.taskId,
      run_id: input.runId ?? null,
    };

    setDrilldownContext(nextContext);
    setDrilldownFeedback({
      tone: "success",
      text:
        input.projectId && input.projectId !== resolvedProjectId
          ? `Drill-down context active with authoritative project override (${input.projectId} -> ${resolvedProjectId}): task ${nextContext.task_id}, run ${nextContext.run_id ?? "n/a"}.`
          : `Drill-down context active: task ${nextContext.task_id}, run ${nextContext.run_id ?? "n/a"}.`,
    });
    const nextHash = buildBossDrilldownHash(nextContext);
    window.location.hash = nextHash;
    lastAppliedDrilldownHashRef.current = nextHash;

    handleSelectProject(resolvedProjectId, {
      scrollIntoDetail: true,
      preserveDrilldownContext: true,
    });

    requestAnimationFrame(() => {
      document.getElementById("project-latest-run-control-surface")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  };

  const handleNavigateToStrategyPreview = (context: BossDrilldownContext) => {
    setDrilldownContext(context);
    setDrilldownFeedback({
      tone: "success",
      text: `Continue drill-down to Strategy Preview with run ${context.run_id ?? "n/a"}.`,
    });
    const nextHash = buildBossDrilldownHash(context);
    window.location.hash = nextHash;
    lastAppliedDrilldownHashRef.current = nextHash;

    requestAnimationFrame(() => {
      document.getElementById("strategy-preview-panel")?.scrollIntoView({
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

  useEffect(() => {
    const handleDrilldownNavigation = (event: Event) => {
      const detail = (event as CustomEvent<BossDrilldownEventDetail>).detail;
      void handleBossDrilldownNavigate(detail);
    };

    window.addEventListener(
      "boss:drilldown-navigate",
      handleDrilldownNavigation as EventListener,
    );

    return () => {
      window.removeEventListener(
        "boss:drilldown-navigate",
        handleDrilldownNavigation as EventListener,
      );
    };
  }, [projects]);

  useEffect(() => {
    const applyHashDrilldown = () => {
      if (window.location.hash === lastAppliedDrilldownHashRef.current) {
        return;
      }

      const parsed = parseBossDrilldownHash(window.location.hash);
      if (!parsed?.taskId) {
        return;
      }
      void handleBossDrilldownNavigate(parsed);
    };

    applyHashDrilldown();
    window.addEventListener("hashchange", applyHashDrilldown);

    return () => {
      window.removeEventListener("hashchange", applyHashDrilldown);
    };
  }, [projects]);

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

      {selectedProjectId ? (
        <ProjectDeliverySnapshotCard
          overview={day15FlowOverviewQuery.data ?? null}
          isLoading={day15FlowOverviewQuery.isLoading}
          errorMessage={
            day15FlowOverviewQuery.isError ? day15FlowOverviewQuery.error.message : null
          }
        />
      ) : null}

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
            <FeaturedProjectsSection
              featuredProjects={featuredProjects}
              selectedProjectId={selectedProjectId}
              onSelectProject={(projectId) =>
                handleSelectProject(projectId, { scrollIntoDetail: true })
              }
            />
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
              data-testid="project-detail-panel"
              className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl shadow-slate-950/30"
            >
              <h2 className="text-lg font-semibold text-slate-50">项目详情</h2>
              <p className="mt-1 text-sm text-slate-400">
                从项目卡片或列表进入，查看老板视角的项目详情；Day04 已把仓库绑定、目录快照和当前变更会话合并到同一详情视图中，仓库首页仍只保留最小入口，不扩展到文件级编辑、代码上下文包或验证证据视图。
              </p>

              {drilldownFeedback ? (
                <div
                  className={`mt-3 rounded-xl border p-3 text-xs ${
                    drilldownFeedback.tone === "success"
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
                      : "border-amber-500/30 bg-amber-500/10 text-amber-100"
                  }`}
                >
                  {drilldownFeedback.text}
                </div>
              ) : null}

              {selectedProject || selectedProjectDetail ? (
                <ProjectDetailSection
                  project={selectedProject}
                  detail={selectedProjectDetail}
                  drilldownContext={
                    drilldownContext &&
                    drilldownContext.project_id === (selectedProjectDetail?.id ?? selectedProject?.id ?? null)
                      ? drilldownContext
                      : null
                  }
                  activeDrilldownTaskSample={
                    drilldownContext &&
                    drilldownContext.project_id ===
                      (selectedProjectDetail?.id ?? selectedProject?.id ?? null)
                      ? activeDrilldownTaskSample
                      : null
                  }
                  onNavigateToStrategyPreview={handleNavigateToStrategyPreview}
                  onNavigateToTask={props.onNavigateToTask}
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
