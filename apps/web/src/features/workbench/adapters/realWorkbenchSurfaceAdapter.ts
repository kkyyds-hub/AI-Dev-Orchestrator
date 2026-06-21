import { requestJson } from "../../../lib/http";
import type { ProjectApprovalInbox } from "../../approvals/types";
import type { ProjectDeliverableSnapshot } from "../../deliverables/types";
import type {
  ProjectDirectorAgentTeamConfigResponse,
  ProjectDirectorRepositoryBindingConfigResponse,
  ProjectDirectorSetupReadiness,
  ProjectDirectorSkillBindingConfigResponse,
  ProjectDirectorVerificationConfigResponse,
} from "../../project-director/types";
import type {
  BossProjectItem,
  ProjectDetail,
  ProjectMemoryGovernanceState,
  ProjectMemorySnapshot,
  RepositorySnapshot,
  RepositoryWorkspace,
} from "../../projects/types";
import type {
  ChangeSession,
  RepositoryVerificationBaseline,
  RepositoryVerificationCategory,
} from "../../repositories/types";
import type { ProjectRoleCatalog, ProjectRoleSkillConsumption, SystemRoleCatalogItem } from "../../roles/types";
import type { WorkspaceSettings } from "../../settings/api";
import type { ProjectSkillBindingSnapshot, SkillRegistrySnapshot } from "../../skills/types";
import type {
  DeliverableViewModel,
  ExecutionRunViewModel,
  GovernanceDirectorConfigViewModel,
  GovernanceMemoryViewModel,
  GovernanceRegistrySkill,
  GovernanceSkillViewModel,
  GovernanceSystemRole,
  ProjectOverviewViewModel,
  RepositoryPageViewModel,
  WorkbenchPageSurfaceData,
} from "../../ui-selection-lab/components/WorkbenchMockPages";

export type WorkbenchTask = {
  id: string;
  project_id: string | null;
  title: string;
  status: string;
  priority: string;
  input_summary: string;
  acceptance_criteria: string[];
  depends_on_task_ids: string[];
  risk_level: string;
  owner_role_code: string | null;
  human_status: string;
  paused_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkbenchTaskRun = {
  id: string;
  status: string;
  result_summary: string | null;
  owner_role_code: string | null;
  dispatch_status: string | null;
  failure_category: string | null;
  quality_gate_passed: boolean | null;
  verification_summary: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type WorkbenchRunLogEvent = {
  timestamp: string;
  level: string;
  event: string;
  message: string;
  data: Record<string, unknown>;
};

export type WorkbenchRunLog = {
  run_id: string;
  limit: number;
  truncated: boolean;
  events: WorkbenchRunLogEvent[];
};

export function fetchWorkbenchTasks(): Promise<WorkbenchTask[]> {
  return requestJson<WorkbenchTask[]>("/tasks");
}

export function fetchWorkbenchTask(taskId: string): Promise<WorkbenchTask> {
  return requestJson<WorkbenchTask>(`/tasks/${taskId}`);
}

export function fetchWorkbenchTaskRuns(taskId: string): Promise<WorkbenchTaskRun[]> {
  return requestJson<WorkbenchTaskRun[]>(`/tasks/${taskId}/runs`);
}

export function fetchWorkbenchRunLogs(runId: string): Promise<WorkbenchRunLog> {
  return requestJson<WorkbenchRunLog>(`/runs/${runId}/logs?limit=20`);
}

export function buildWorkbenchSurfaceData(input: {
  selectedProjectId: string | null;
  selectedProjectName: string;
  projects: BossProjectItem[];
  projectDetail: ProjectDetail | null;
  tasks: WorkbenchTask[];
  selectedTask: WorkbenchTask | null;
  taskRuns: WorkbenchTaskRun[];
  taskRunLogs: WorkbenchRunLog | null;
  deliverables: ProjectDeliverableSnapshot | null;
  approvals: ProjectApprovalInbox | null;
  repositorySnapshot: RepositorySnapshot | null;
  repositoryVerificationBaseline: RepositoryVerificationBaseline | null;
  changeSession: ChangeSession | null;
  workspaceSettings: WorkspaceSettings | null;
  roleCatalog: ProjectRoleCatalog | null;
  systemRoles: SystemRoleCatalogItem[];
  skillRegistry: SkillRegistrySnapshot | null;
  skillBindings: ProjectSkillBindingSnapshot | null;
  roleSkillConsumption: ProjectRoleSkillConsumption | null;
  projectMemory: ProjectMemorySnapshot | null;
  memoryGovernance: ProjectMemoryGovernanceState | null;
  directorSetupReadiness: ProjectDirectorSetupReadiness | null;
  directorAgentTeamConfig: ProjectDirectorAgentTeamConfigResponse | null;
  directorSkillBindingConfig: ProjectDirectorSkillBindingConfigResponse | null;
  directorRepositoryBindingConfig: ProjectDirectorRepositoryBindingConfigResponse | null;
  directorVerificationConfig: ProjectDirectorVerificationConfigResponse | null;
  loading: {
    project: boolean;
    execution: boolean;
    deliverables: boolean;
    repository: boolean;
    governance: boolean;
  };
  error: {
    project: boolean;
    execution: boolean;
    deliverables: boolean;
    repository: boolean;
    governance: boolean;
  };
}): WorkbenchPageSurfaceData {
  const selectedProject =
    input.projects.find((project) => project.id === input.selectedProjectId) ?? null;
  const scopedTasks = input.selectedProjectId
    ? input.tasks.filter((task) => task.project_id === input.selectedProjectId)
    : input.tasks;

  return {
    projects: {
      viewState: resolveProjectViewState(input),
      overview: buildProjectOverview({
        project: selectedProject,
        detail: input.projectDetail,
        selectedProjectName: input.selectedProjectName,
      }),
    },
    execution: {
      viewState: resolveExecutionViewState({
        selectedProjectId: input.selectedProjectId,
        loading: input.loading.execution,
        error: input.error.execution,
        tasks: scopedTasks,
      }),
      run: buildExecutionRun({
        tasks: scopedTasks,
        selectedTask: input.selectedTask,
        taskRuns: input.taskRuns,
        taskRunLogs: input.taskRunLogs,
      }),
    },
    deliverables: {
      viewState: resolveDeliverablesViewState({
        selectedProjectId: input.selectedProjectId,
        loading: input.loading.deliverables,
        error: input.error.deliverables,
        total: input.deliverables?.total_deliverables ?? 0,
      }),
      projectName: input.selectedProjectName,
      deliverables: mapDeliverables(input.deliverables),
      pendingApprovalCount: input.approvals?.pending_requests ?? 0,
    },
    repository: buildRepositoryPage({
      selectedProjectId: input.selectedProjectId,
      selectedProjectName: input.selectedProjectName,
      workspace: input.projectDetail?.repository_workspace ?? selectedProject?.repository_workspace ?? null,
      snapshot:
        input.repositorySnapshot ??
        input.projectDetail?.latest_repository_snapshot ??
        selectedProject?.latest_repository_snapshot ??
        null,
      verificationBaseline: input.repositoryVerificationBaseline,
      changeSession:
        input.changeSession ??
        input.projectDetail?.current_change_session ??
        selectedProject?.current_change_session ??
        null,
      workspaceSettings: input.workspaceSettings,
      loading: input.loading.repository,
      error: input.error.repository,
    }),
    governance: {
      viewState: resolveGovernanceViewState({
        selectedProjectId: input.selectedProjectId,
        loading: input.loading.governance,
        error: input.error.governance,
        roles: input.roleCatalog?.roles.length ?? 0,
        registry: input.skillRegistry?.skills.length ?? 0,
      }),
      skills: mapGovernanceSkills({
        bindings: input.skillBindings,
        consumption: input.roleSkillConsumption,
      }),
      registrySkills: mapRegistrySkills(input.skillRegistry),
      roles: input.roleCatalog?.roles ?? [],
      systemRoles: mapSystemRoles(input.systemRoles),
      memory: buildGovernanceMemorySummary({
        snapshot: input.projectMemory,
        governance: input.memoryGovernance,
      }),
      directorConfig: buildDirectorConfigSummary({
        readiness: input.directorSetupReadiness,
        agentTeam: input.directorAgentTeamConfig,
        skillBinding: input.directorSkillBindingConfig,
        repositoryBinding: input.directorRepositoryBindingConfig,
        verification: input.directorVerificationConfig,
      }),
    },
  };
}

function resolveProjectViewState(input: {
  selectedProjectId: string | null;
  projects: BossProjectItem[];
  projectDetail: ProjectDetail | null;
  loading: { project: boolean };
  error: { project: boolean };
}) {
  if (input.loading.project) return "loading" as const;
  if (input.error.project) return "error" as const;
  if (input.selectedProjectId && !input.projectDetail) return "no_project" as const;
  if (input.projects.length === 0) return "empty" as const;
  return "ready" as const;
}

function resolveExecutionViewState(input: {
  selectedProjectId: string | null;
  loading: boolean;
  error: boolean;
  tasks: WorkbenchTask[];
}) {
  if (input.loading) return "loading" as const;
  if (input.error) return "error" as const;
  if (input.selectedProjectId === null) return "no_project" as const;
  if (input.tasks.length === 0) return "idle" as const;
  if (input.tasks.every((task) => task.status === "completed")) return "completed" as const;
  if (input.tasks.some((task) => task.status === "blocked" || task.status === "failed")) {
    return "blocked" as const;
  }
  return "ready" as const;
}

function resolveDeliverablesViewState(input: {
  selectedProjectId: string | null;
  loading: boolean;
  error: boolean;
  total: number;
}) {
  if (input.loading) return "loading" as const;
  if (input.error) return "error" as const;
  if (input.selectedProjectId === null) return "no_project" as const;
  if (input.total === 0) return "empty" as const;
  return "ready" as const;
}

function resolveGovernanceViewState(input: {
  selectedProjectId: string | null;
  loading: boolean;
  error: boolean;
  roles: number;
  registry: number;
}) {
  if (input.loading) return "loading" as const;
  if (input.error) return "error" as const;
  if (input.selectedProjectId === null) return "no_project" as const;
  if (input.roles === 0 && input.registry === 0) return "empty" as const;
  return "ready" as const;
}

function buildProjectOverview(input: {
  project: BossProjectItem | null;
  detail: ProjectDetail | null;
  selectedProjectName: string;
}): ProjectOverviewViewModel | null {
  const detail = input.detail;
  const project = input.project;
  if (!project && !detail) return null;

  const stats = detail?.task_stats ?? project?.task_stats;
  const stage = detail?.stage ?? project?.stage ?? "planning";
  const updatedAt = detail?.updated_at ?? project?.updated_at ?? null;
  const tasks = detail?.tasks ?? [];
  const latestTask = project?.latest_task ?? tasks[0] ?? null;

  return {
    id: detail?.id ?? project?.id ?? "project",
    name: detail?.name ?? project?.name ?? input.selectedProjectName,
    status: mapProjectStatus(detail?.status ?? project?.status ?? "active"),
    status_label: formatProjectStatus(detail?.status ?? project?.status ?? "active"),
    current_stage: formatStage(stage),
    updated_at: formatDateTime(updatedAt),
    summary: detail?.summary ?? project?.summary ?? "当前项目已接入真实项目数据。",
    recommendation:
      project?.latest_progress_summary ||
      project?.key_risk_summary ||
      "建议继续围绕当前阶段推进任务、成果和仓库准备。",
    scope_rows: [
      ["项目目标", detail?.summary ?? project?.summary ?? "等待 AI 主管沉淀项目目标"],
      ["当前阶段", formatStage(stage)],
      ["关键风险", project?.key_risk_summary || "暂无显著风险"],
      ["交付标准", detail?.stage_guard?.can_advance ? "当前阶段具备推进条件" : "等待阶段任务和验收证据补齐"],
    ],
    stages: buildProjectStages(stage, detail),
    context_items: [
      {
        id: "ctx_task",
        label: "最近任务",
        value: latestTask?.title ?? "暂无任务",
        meta: latestTask ? formatDateTime(latestTask.updated_at) : "暂无",
        dialogKey: "task",
      },
      {
        id: "ctx_timeline",
        label: "最近操作",
        value: project?.latest_progress_summary || "暂无进展摘要",
        meta: project?.latest_progress_at ? formatDateTime(project.latest_progress_at) : "暂无",
        dialogKey: "timeline",
      },
      {
        id: "ctx_repo",
        label: "仓库绑定",
        value: detail?.repository_workspace?.display_name ?? project?.repository_workspace?.display_name ?? "未绑定",
        meta: detail?.repository_workspace || project?.repository_workspace ? "已绑定" : "未绑定",
        dialogKey: "repository",
      },
      {
        id: "ctx_approval",
        label: "审批 / 交付物",
        value: `待处理 ${project?.attention_task_count ?? 0} 项 / 高风险 ${project?.high_risk_task_count ?? 0} 项`,
        meta: project?.attention_task_count ? "待处理" : "正常",
        dialogKey: "approval",
      },
    ],
    task_total: stats?.total_tasks ?? tasks.length,
    task_done: stats?.completed_tasks ?? tasks.filter((task) => task.status === "completed").length,
    task_running: stats?.running_tasks ?? tasks.filter((task) => task.status === "running").length,
    manual_pending:
      stats?.waiting_human_tasks ??
      tasks.filter((task) => task.human_status && task.human_status !== "none").length,
    backend_status: "real",
  };
}

function buildProjectStages(stage: string, detail: ProjectDetail | null) {
  const guard = detail?.stage_guard;
  const labels = [stage, guard?.target_stage, "执行", "交付验收"].filter(
    (value, index, arr): value is string => Boolean(value) && arr.indexOf(value) === index,
  );
  const normalized = labels.length > 0 ? labels.slice(0, 4) : ["规划", "执行", "验收"];

  return normalized.map((label, index) => ({
    id: `stage_${index + 1}`,
    label: formatStage(label),
    status_label:
      index === 0 ? "当前阶段" : guard?.target_stage === label ? "下一阶段" : "待开始",
    state: index === 0 ? ("current" as const) : ("pending" as const),
    summary:
      index === 0
        ? guard?.blocking_reasons.join("；") || "当前阶段正在推进。"
        : "等待前置事项完成后推进。",
    meta:
      index === 0
        ? `${guard?.completed_task_count ?? 0}/${guard?.total_tasks ?? 0} 任务完成`
        : "待开始",
  }));
}

function buildExecutionRun(input: {
  tasks: WorkbenchTask[];
  selectedTask: WorkbenchTask | null;
  taskRuns: WorkbenchTaskRun[];
  taskRunLogs: WorkbenchRunLog | null;
}): ExecutionRunViewModel | null {
  const task =
    input.selectedTask ??
    input.tasks.find((item) => item.status === "running") ??
    input.tasks.find((item) => item.human_status && item.human_status !== "none") ??
    input.tasks[0] ??
    null;
  if (!task) return null;

  const latestRun = input.taskRuns[0] ?? null;
  const status = mapExecutionStatus(task.status, latestRun?.status ?? null);
  const currentSummary =
    latestRun?.result_summary ??
    latestRun?.verification_summary ??
    task.input_summary ??
    "当前任务正在等待执行摘要。";

  const processEvents = mapRunLogEvents(input.taskRunLogs, latestRun?.id ?? null);

  return {
    id: task.id,
    title: `AI 正在处理：${task.title}`,
    status,
    status_label: formatTaskStatus(task.status),
    executor_label: formatRole(task.owner_role_code),
    worker_label: "自动处理",
    environment_label: "运行环境已接入",
    budget_label: "预算读取中",
    git_write_status: "disabled",
    started_at: formatDateTime(latestRun?.started_at ?? task.created_at),
    updated_at: formatDateTime(latestRun?.finished_at ?? task.updated_at),
    current_summary: currentSummary,
    safety_note: "当前页面只展示处理进展，不执行提交、推送或写入操作。",
    status_rows: [
      ["任务", task.title],
      ["状态", formatTaskStatus(task.status)],
      ["优先级", task.priority],
      ["风险", formatRisk(task.risk_level)],
      ["人工处理", formatHumanStatus(task.human_status)],
      ["最近结果", latestRun ? "已记录" : "暂无运行记录"],
    ],
    steps: [
      {
        id: "task_received",
        title: "任务已进入队列",
        detail: formatDateTime(task.created_at),
        state: "done",
        rows: [
          ["任务", task.title],
          ["优先级", task.priority],
          ["风险", formatRisk(task.risk_level)],
          ["接收时间", formatDateTime(task.created_at)],
        ],
        footer: "仅展示任务读取，不触发执行操作",
      },
      {
        id: "task_processing",
        title: status === "completed" ? "处理已完成" : "处理中",
        detail: currentSummary,
        state: status === "completed" ? "done" : status === "blocked" || status === "failed" ? "blocked" : "current",
        rows: [
          ["当前摘要", currentSummary],
          ["处理状态", formatTaskStatus(task.status)],
          ["质量结果", formatQuality(latestRun?.quality_gate_passed)],
        ],
        footer: "高级详情只展示用户可读摘要。",
      },
      {
        id: "task_next",
        title: "等待下一步",
        detail:
          task.human_status && task.human_status !== "none"
            ? "需要用户处理后继续"
            : "等待执行结果或成果沉淀",
        state: status === "completed" ? "done" : "pending",
        rows: [
          ["下一步", task.paused_reason ?? "等待执行结果或成果沉淀"],
          ["人工处理", formatHumanStatus(task.human_status)],
        ],
        footer: "只读展示下一步安排。",
      },
    ],
    evidence_tabs: [
      {
        key: "context",
        label: "上下文",
        title: "上下文",
        description: "当前任务输入摘要",
        rows: [
          ["任务", task.title],
          ["输入摘要", task.input_summary],
          ["验收项", task.acceptance_criteria.length ? task.acceptance_criteria.join("；") : "暂无"],
        ],
        footer: "上下文来自真实任务接口。",
      },
      ...(processEvents.length > 0
        ? [
            {
              key: "process",
              label: "过程",
              title: "处理过程",
              description: "来自真实运行日志的用户可读摘要",
              rows: processEvents,
              footer: input.taskRunLogs?.truncated
                ? "仅展示最近处理事件摘要，已省略更早记录。"
                : "仅展示处理事件摘要，不暴露内部标识、存储位置或凭据细节。",
            },
          ]
        : []),
      {
        key: "safety",
        label: "安全",
        title: "安全边界",
        description: "只读处理边界",
        rows: [
          ["默认方式", "只读查看"],
          ["写入操作", "需要用户确认"],
          ["当前页面", "不执行提交、推送或本地写入"],
        ],
        footer: "仅展示用户可理解的安全边界。",
      },
    ],
    queue_items: input.tasks
      .filter((item) => item.id !== task.id)
      .slice(0, 3)
      .map((item, index) => ({
        id: item.id,
        state:
          item.human_status && item.human_status !== "none"
            ? ("manual_required" as const)
            : item.status === "blocked" || item.status === "failed"
              ? ("blocked" as const)
              : item.status === "completed"
                ? ("done" as const)
                : ("queued" as const),
        state_label: formatTaskStatus(item.status),
        title: item.title,
        note: index === 0 ? "后续优先处理" : "排队中",
        description: "后续安排详情",
        rows: [
          ["状态", formatTaskStatus(item.status)],
          ["优先级", item.priority],
          ["摘要", item.input_summary],
        ],
        footer: "仅展示队列任务，不触发执行操作",
        can_add_to_workbench: Boolean(item.human_status && item.human_status !== "none"),
      })),
    backend_status: "real",
  };
}

function mapRunLogEvents(
  log: WorkbenchRunLog | null,
  latestRunId: string | null,
): readonly (readonly [string, string])[] {
  if (!log || !latestRunId || log.run_id !== latestRunId || log.events.length === 0) {
    return [];
  }

  return log.events.slice(-6).map((event) => [
    formatDateTime(event.timestamp),
    sanitizeRunLogMessage(event),
  ] as const);
}

function sanitizeRunLogMessage(event: WorkbenchRunLogEvent): string {
  const message = `${formatRunLogEventName(event.event)}：${event.message || "处理事件已记录"}`;
  const forbiddenPattern =
    /\b(run_id|provider_receipt|receipt|token|log_path|worker|sk-[a-z0-9_-]+)\b|日志路径|运行 ID|调试/i;

  if (forbiddenPattern.test(message)) {
    return `${formatRunLogEventName(event.event)}：处理事件已记录`;
  }

  return message.length > 96 ? `${message.slice(0, 96)}...` : message;
}

function formatRunLogEventName(value: string): string {
  const normalized = value.replace(/[_-]+/g, " ").trim().toLowerCase();
  if (normalized.includes("claimed")) return "已领取";
  if (normalized.includes("context")) return "上下文";
  if (normalized.includes("handoff")) return "协作";
  if (normalized.includes("verification")) return "验证";
  if (normalized.includes("completed") || normalized.includes("finished")) return "完成";
  if (normalized.includes("failed") || normalized.includes("error")) return "异常";
  return "处理";
}

function mapDeliverables(snapshot: ProjectDeliverableSnapshot | null): DeliverableViewModel[] {
  return (
    snapshot?.deliverables.map((item) => ({
      id: item.id,
      project_id: item.project_id,
      title: item.title,
      type: mapDeliverableType(item.type),
      type_label: formatDeliverableType(item.type),
      status: mapDeliverableStatus(item.status),
      status_label: formatDeliverableStatus(item.status),
      stage: item.stage,
      stage_label: formatStage(item.stage),
      version_no: item.version_no ?? item.current_version_number,
      total_versions: item.total_versions,
      latest_version: true,
      summary: item.summary,
      content_markdown: item.content_markdown ?? item.latest_version?.content_markdown ?? item.summary,
      created_by: item.created_by,
      created_at: formatDateTime(item.created_at),
      updated_at: formatDateTime(item.updated_at),
      source_task_id: item.task_id ?? item.source_draft_id ?? undefined,
      source_run_id: item.run_id ?? undefined,
      source_label: item.source_label ?? "真实成果接口",
      evidence_refs: item.evidence_refs
        .map((ref) => ref.label ?? ref.ref ?? ref.kind ?? null)
        .filter((value): value is string => Boolean(value)),
      git_write_status: "disabled",
      backend_status: "real",
      can_be_acceptance_evidence: item.status === "approved",
    })) ?? []
  );
}

function buildRepositoryPage(input: {
  selectedProjectId: string | null;
  selectedProjectName: string;
  workspace: RepositoryWorkspace | null;
  snapshot: RepositorySnapshot | null;
  verificationBaseline: RepositoryVerificationBaseline | null;
  changeSession: ChangeSession | null;
  workspaceSettings: WorkspaceSettings | null;
  loading: boolean;
  error: boolean;
}): RepositoryPageViewModel {
  const workspace = input.workspace;
  const snapshot = input.snapshot;
  const changeSession = input.changeSession;
  const viewState = input.loading
    ? "loading"
    : input.error
      ? "error"
      : !input.selectedProjectId
        ? "no_project"
        : !workspace
          ? "pending_binding"
          : "ready";
  const repositoryName = workspace?.display_name ?? input.selectedProjectName;
  const workspacePath = workspace?.root_path ?? "尚未绑定仓库";
  const statusLabel =
    snapshot?.status === "failed"
      ? "快照失败"
      : snapshot
        ? "已就绪"
        : workspace
          ? "已绑定"
      : "未绑定";
  const verificationBaseline = input.verificationBaseline;
  const enabledTemplates =
    verificationBaseline?.templates.filter((template) => template.enabled_by_default) ?? [];
  const verificationTemplateNames = enabledTemplates
    .slice(0, 3)
    .map((template) => template.name.trim())
    .filter(Boolean);

  return {
    viewState,
    projectName: input.selectedProjectName,
    repositoryName,
    workspacePath,
    defaultBranch: workspace?.default_base_branch ?? "main",
    currentBranch: changeSession?.current_branch ?? null,
    statusLabel,
    summary: workspace
      ? "当前项目的本地仓库、快照和变更会话状态。"
      : "当前项目还没有绑定本地仓库。",
    readiness: [
      workspace ? "✓ 已绑定本地仓库" : "○ 等待绑定本地仓库",
      workspace && isPathUnderAllowedRoots(workspace.root_path, input.workspaceSettings)
        ? "✓ 位于允许的工作区目录"
        : workspace
          ? "○ 等待工作区检查"
          : "○ 等待工作区检查",
      snapshot ? `✓ 已识别 ${snapshot.file_count} 个文件` : "○ 等待仓库快照",
      verificationBaseline
        ? `✓ 验证基线已配置 ${verificationBaseline.template_count} 项`
        : "○ 等待验证基线",
      changeSession
        ? `✓ 当前变更会话：${formatWorkspaceStatus(changeSession.workspace_status)}`
        : "○ 等待生成变更会话",
      "○ 写入、提交和推送需用户显式确认",
    ],
    detailItems: [
      {
        title: "当前绑定",
        description: "当前项目使用的本地仓库。",
        rows: [
          ["仓库名称", repositoryName],
          ["本地路径", workspacePath],
          ["默认分支", workspace?.default_base_branch ?? "—"],
          ["查看方式", "只读查看"],
        ],
      },
      {
        title: "工作区范围",
        description: "当前后端允许读取和准备变更的位置。",
        rows: [
          ["默认工作区", input.workspaceSettings?.default_workspace_root ?? "—"],
          [
            "允许位置",
            input.workspaceSettings?.allowed_workspace_roots.join("、") ?? "—",
          ],
          [
            "当前路径状态",
            workspace
              ? isPathUnderAllowedRoots(workspace.root_path, input.workspaceSettings)
                ? "位于允许位置内"
                : "等待确认"
              : "暂无仓库",
          ],
        ],
      },
      {
        title: "仓库快照",
        description: "当前项目仓库的只读扫描结果。",
        rows: [
          ["快照状态", snapshot ? formatSnapshotStatus(snapshot.status) : "暂无快照"],
          ["文件数", snapshot ? String(snapshot.file_count) : "—"],
          ["目录数", snapshot ? String(snapshot.directory_count) : "—"],
          ["扫描时间", snapshot ? formatDateTime(snapshot.scanned_at) : "—"],
        ],
      },
      {
        title: "验证基线",
        description: "当前项目用于只读检查的验证准备情况。",
        rows: [
          [
            "模板数量",
            verificationBaseline ? String(verificationBaseline.template_count) : "—",
          ],
          [
            "覆盖类别",
            verificationBaseline
              ? formatVerificationCategories(
                  verificationBaseline.configured_categories,
                )
              : "—",
          ],
          [
            "默认启用",
            verificationBaseline ? `${enabledTemplates.length} 项` : "—",
          ],
          [
            "示例检查",
            verificationTemplateNames.length > 0
              ? verificationTemplateNames.join("、")
              : "暂无默认启用项",
          ],
          [
            "更新时间",
            verificationBaseline?.last_updated_at
              ? formatDateTime(verificationBaseline.last_updated_at)
              : "—",
          ],
        ],
      },
      {
        title: "变更会话",
        description: "当前工作区变更状态。",
        rows: [
          ["当前分支", changeSession?.current_branch ?? "—"],
          ["工作区状态", changeSession ? formatWorkspaceStatus(changeSession.workspace_status) : "—"],
          ["待处理文件", changeSession ? String(changeSession.dirty_file_count) : "—"],
          ["保护状态", changeSession ? formatGuardStatus(changeSession.guard_status) : "—"],
        ],
      },
    ],
  };
}

function formatVerificationCategories(
  categories: RepositoryVerificationCategory[],
): string {
  if (categories.length === 0) return "暂无";
  const labels = categories.map((category) => {
    if (category === "build") return "构建";
    if (category === "test") return "测试";
    if (category === "lint") return "代码检查";
    if (category === "typecheck") return "类型检查";
    return category;
  });
  return labels.join("、");
}

function isPathUnderAllowedRoots(
  workspacePath: string,
  settings: WorkspaceSettings | null,
): boolean {
  if (!settings || settings.allowed_workspace_roots.length === 0) {
    return false;
  }

  return settings.allowed_workspace_roots.some((root) => {
    const normalizedRoot = root.endsWith("/") ? root : `${root}/`;
    return workspacePath === root || workspacePath.startsWith(normalizedRoot);
  });
}

function mapGovernanceSkills(input: {
  bindings: ProjectSkillBindingSnapshot | null;
  consumption: ProjectRoleSkillConsumption | null;
}): GovernanceSkillViewModel[] {
  const consumptionBySkill = new Map(
    input.consumption?.skills.map((item) => [item.skill_code, item]) ?? [],
  );
  return (
    input.bindings?.roles.flatMap((role) =>
      role.skills.map((skill) => {
        const consumption = consumptionBySkill.get(skill.skill_code);
        return {
          id: `${role.role_code}:${skill.skill_code}`,
          skill_id: skill.skill_id,
          skill_code: skill.skill_code,
          skill_name: skill.skill_name,
          summary: skill.summary,
          purpose: skill.purpose,
          bound_version: skill.bound_version,
          registry_current_version: skill.registry_current_version,
          registry_enabled: skill.registry_enabled,
          upgrade_available: skill.upgrade_available,
          applicable_role_codes: skill.applicable_role_codes,
          binding_source: skill.binding_source,
          owner_role_code: role.role_code,
          owner_role_name: role.role_name,
          run_count: consumption?.run_count ?? 0,
          succeeded_run_count: consumption?.succeeded_run_count ?? 0,
          failed_run_count: consumption?.failed_run_count ?? 0,
          total_tokens: consumption?.total_tokens ?? 0,
          estimated_cost: consumption?.estimated_cost ?? 0,
          latest_run_id: consumption?.latest_run_id ?? null,
          latest_run_status: consumption?.latest_run_status ?? null,
          latest_run_summary: consumption?.latest_run_summary ?? null,
          latest_used_at: consumption?.latest_run_created_at
            ? formatDateTime(consumption.latest_run_created_at)
            : null,
          recommendation: skill.upgrade_available ? "observe" : "retain",
          recommendation_label: skill.upgrade_available ? "观察" : "建议保留",
          recommendation_reason: skill.upgrade_available
            ? "该绑定存在新版本，建议观察后再调整。"
            : "该绑定来自真实项目 Skill 配置，当前保持启用。",
          evidence_rows: [
            ["最近运行次数", String(consumption?.run_count ?? 0)],
            ["成功次数", String(consumption?.succeeded_run_count ?? 0)],
            ["失败次数", String(consumption?.failed_run_count ?? 0)],
            ["最近运行", consumption?.latest_run_id ? "已记录" : "—"],
            ["最近状态", consumption?.latest_run_status ?? "—"],
            ["最近摘要", consumption?.latest_run_summary ?? "暂无摘要"],
          ],
          version_rows: [
            ["当前绑定版本", skill.bound_version],
            ["注册表版本", skill.registry_current_version ?? "—"],
            ["是否启用", skill.registry_enabled ? "是" : "否"],
            ["是否有升级", skill.upgrade_available ? "是" : "否"],
            ["绑定来源", skill.binding_source === "manual" ? "手动绑定" : "默认映射"],
          ],
          suggestion_rows: [
            ["建议", skill.upgrade_available ? "观察" : "保留"],
            ["理由", skill.upgrade_available ? "存在新版本，建议确认差异后升级。" : "当前绑定可继续使用。"],
            ["影响范围", role.role_name],
            ["建议动作", "保持只读检查，具体调整需用户确认"],
          ],
        };
      }),
    ) ?? []
  );
}

function mapRegistrySkills(snapshot: SkillRegistrySnapshot | null): GovernanceRegistrySkill[] {
  return (
    snapshot?.skills.map((skill) => ({
      id: skill.id,
      code: skill.code,
      name: skill.name,
      summary: skill.summary,
      purpose: skill.purpose,
      applicable_role_codes: skill.applicable_role_codes,
      enabled: skill.enabled,
      current_version: skill.current_version,
      version_history: skill.version_history,
    })) ?? []
  );
}

function mapSystemRoles(roles: SystemRoleCatalogItem[]): GovernanceSystemRole[] {
  return roles.map((role) => ({
    code: role.code,
    name: role.name,
    summary: role.summary,
    responsibilities: role.responsibilities,
    input_boundary: role.input_boundary,
    output_boundary: role.output_boundary,
    default_skill_slots: role.default_skill_slots,
    enabled_by_default: role.enabled_by_default,
    sort_order: role.sort_order,
  }));
}

function buildGovernanceMemorySummary(input: {
  snapshot: ProjectMemorySnapshot | null;
  governance: ProjectMemoryGovernanceState | null;
}): GovernanceMemoryViewModel | null {
  const snapshot = input.snapshot;
  const governance = input.governance;
  if (!snapshot && !governance) {
    return null;
  }

  const totalMemories = snapshot?.total_memories ?? 0;
  const healthLabel = governance?.latest_bad_context_detected
    ? "需要整理"
    : governance
      ? "健康"
      : "待读取";
  const pressureLabel = formatMemoryPressure(governance?.latest_pressure_level);
  const latestSummary =
    sanitizeUserFacingSummary(
      governance?.latest_rolling_summary ??
        snapshot?.latest_items[0]?.summary ??
        "当前项目记忆已接入真实治理数据。",
    );

  return {
    statusLabel: totalMemories > 0 || (governance?.checkpoint_count ?? 0) > 0 ? "已接入" : "待沉淀",
    summary: latestSummary,
    rows: [
      ["记忆总数", String(totalMemories)],
      ["上下文状态", healthLabel],
      ["治理检查点", String(governance?.checkpoint_count ?? 0)],
      ["压力水平", pressureLabel],
      ["最近整理", governance?.latest_compaction_applied ? "已整理" : "未触发"],
      [
        "记忆类型",
        snapshot?.counts.length
          ? snapshot.counts
              .map((item) => `${formatMemoryKind(item.memory_type)} ${item.count}`)
              .join("、")
          : "暂无",
      ],
    ],
    latestItems:
      snapshot?.latest_items.slice(0, 3).map((item) => ({
        id: item.memory_id,
        title: sanitizeUserFacingSummary(item.title),
        summary: sanitizeUserFacingSummary(item.summary),
        meta: [
          formatMemoryKind(item.memory_type),
          item.stage ? formatStage(item.stage) : null,
          item.actor_name,
        ]
          .filter((value): value is string => Boolean(value))
          .join(" · ") || "项目记忆",
      })) ?? [],
  };
}

function sanitizeUserFacingSummary(value: string): string {
  const forbiddenPattern =
    /\b(run_id|provider_receipt|receipt|token|log_path|storage_path|latest_run_id|worker|sk-[a-z0-9_-]+)\b|运行 ID|日志路径|存储路径|凭据|调试/i;
  if (forbiddenPattern.test(value)) {
    return "已记录项目记忆，内部标识、存储位置或凭据细节已省略。";
  }
  return value.length > 140 ? `${value.slice(0, 140)}...` : value;
}

function buildDirectorConfigSummary(input: {
  readiness: ProjectDirectorSetupReadiness | null;
  agentTeam: ProjectDirectorAgentTeamConfigResponse | null;
  skillBinding: ProjectDirectorSkillBindingConfigResponse | null;
  repositoryBinding: ProjectDirectorRepositoryBindingConfigResponse | null;
  verification: ProjectDirectorVerificationConfigResponse | null;
}): GovernanceDirectorConfigViewModel | null {
  const readiness = input.readiness;
  const hasAnyConfig =
    Boolean(readiness) ||
    Boolean(input.agentTeam?.config) ||
    Boolean(input.skillBinding?.config) ||
    Boolean(input.repositoryBinding?.config) ||
    Boolean(input.verification?.config);

  if (!hasAnyConfig) {
    return null;
  }

  const pending = readiness?.pending_confirmation_count ?? [
    input.agentTeam?.config?.status,
    input.skillBinding?.config?.status,
    input.repositoryBinding?.config?.status,
    input.verification?.config?.status,
  ].filter((status) => status === "pending_confirmation").length;
  const confirmed = readiness?.confirmed_count ?? [
    input.agentTeam?.config?.status,
    input.skillBinding?.config?.status,
    input.repositoryBinding?.config?.status,
    input.verification?.config?.status,
  ].filter((status) => status === "confirmed").length;

  return {
    statusLabel:
      readiness?.ready_for_manual_execution
        ? "已就绪"
        : pending > 0
          ? "待确认"
          : confirmed > 0
            ? "已接入"
            : "读取中",
    summary:
      readiness?.created_by_director
        ? "AI 主管已沉淀团队、Skill、仓库和验证配置。"
        : "当前治理页正在读取真实 AI 主管配置状态。",
    rows: [
      ["团队配置", formatConfigStatus(input.agentTeam?.config?.status ?? readiness?.agent_team_config_status)],
      ["Skill 绑定", formatConfigStatus(input.skillBinding?.config?.status ?? readiness?.skill_binding_config_status)],
      ["仓库配置", formatConfigStatus(input.repositoryBinding?.config?.status ?? readiness?.repository_binding_config_status)],
      ["验证配置", formatConfigStatus(input.verification?.config?.status ?? readiness?.verification_config_status)],
      ["团队角色", input.agentTeam?.config ? `${input.agentTeam.config.agent_team.length} 个角色` : "暂无"],
      ["Skill 建议", input.skillBinding?.config ? `${input.skillBinding.config.skill_bindings.length} 项` : "暂无"],
      ["仓库绑定", input.repositoryBinding?.config ? `${input.repositoryBinding.config.repository_bindings.length} 项` : "暂无"],
      ["验证机制", input.verification?.config ? `${input.verification.config.verification_mechanisms.length} 项` : "暂无"],
    ],
    nextSteps: readiness?.next_steps ?? [
      input.agentTeam?.next_action,
      input.skillBinding?.next_action,
      input.repositoryBinding?.next_action,
      input.verification?.next_action,
    ].filter((value): value is string => Boolean(value)),
    warnings: [
      ...(readiness?.warnings ?? []),
      ...(input.agentTeam?.config?.warnings ?? []),
      ...(input.skillBinding?.config?.warnings ?? []),
      ...(input.repositoryBinding?.config?.warnings ?? []),
      ...(input.verification?.config?.warnings ?? []),
    ],
  };
}

function formatConfigStatus(status: string | null | undefined): string {
  if (status === "confirmed") return "已确认";
  if (status === "pending_confirmation") return "待确认";
  if (status === "rejected") return "已驳回";
  if (status === "missing") return "未生成";
  return "暂无";
}

function formatMemoryKind(kind: string): string {
  const labels: Record<string, string> = {
    conclusion: "关键结论",
    failure_pattern: "失败模式",
    approval_feedback: "审批意见",
    deliverable_summary: "交付件摘要",
  };
  return labels[kind] ?? kind;
}

function formatMemoryPressure(level: string | null | undefined): string {
  if (!level) return "暂无";
  const labels: Record<string, string> = {
    low: "低",
    medium: "中",
    high: "高",
    critical: "关键",
  };
  return labels[level] ?? level;
}

function mapProjectStatus(status: string): ProjectOverviewViewModel["status"] {
  if (status === "blocked" || status === "failed") return "blocked";
  if (status === "archived" || status === "completed") return "archived";
  if (status === "pending" || status === "draft") return "pending";
  return "active";
}

function mapExecutionStatus(taskStatus: string, runStatus: string | null): ExecutionRunViewModel["status"] {
  const status = runStatus ?? taskStatus;
  if (status === "completed" || status === "succeeded") return "completed";
  if (status === "blocked") return "blocked";
  if (status === "failed") return "failed";
  if (status === "running" || status === "in_progress") return "running";
  return "idle";
}

function mapDeliverableStatus(status: string): DeliverableViewModel["status"] {
  if (status === "approved") return "locked";
  if (status === "needs_rework") return "needs_more_evidence";
  if (status === "archived") return "archived";
  if (status === "pending_review") return "pending_review";
  return "draft";
}

function mapDeliverableType(type: string): DeliverableViewModel["type"] {
  if (type === "task_breakdown") return "task_split";
  if (type === "acceptance_conclusion") return "review_report";
  if (type === "code_plan") return "code_change_summary";
  if (type === "stage_artifact") return "delivery_doc";
  return "plan_draft";
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatProjectStatus(status: string): string {
  if (status === "completed") return "已完成";
  if (status === "blocked" || status === "failed") return "阻塞";
  if (status === "pending" || status === "draft") return "待开始";
  return "进行中";
}

function formatStage(stage: string): string {
  return stage.replace(/_/g, " ");
}

function formatTaskStatus(status: string): string {
  const labels: Record<string, string> = {
    pending: "待执行",
    running: "进行中",
    completed: "已完成",
    failed: "失败",
    blocked: "阻塞",
    paused: "暂停",
  };
  return labels[status] ?? status;
}

function formatRisk(risk: string): string {
  const labels: Record<string, string> = {
    low: "低",
    normal: "正常",
    medium: "中",
    high: "高",
    critical: "关键",
  };
  return labels[risk] ?? risk;
}

function formatHumanStatus(status: string): string {
  if (!status || status === "none") return "无需人工处理";
  return "需要你处理";
}

function formatRole(roleCode: string | null): string {
  const labels: Record<string, string> = {
    product_manager: "产品经理",
    architect: "架构师",
    engineer: "工程师",
    reviewer: "评审者",
  };
  return roleCode ? labels[roleCode] ?? roleCode : "AI 主管";
}

function formatQuality(value: boolean | null | undefined): string {
  if (value === true) return "通过";
  if (value === false) return "未通过";
  return "暂无结果";
}

function formatDeliverableType(type: string): string {
  const labels: Record<string, string> = {
    spec: "说明",
    prd: "需求文档",
    design: "设计",
    task_breakdown: "任务拆分",
    code_plan: "变更计划",
    acceptance_conclusion: "验收结论",
    stage_artifact: "阶段材料",
  };
  return labels[type] ?? type;
}

function formatDeliverableStatus(status: string): string {
  const labels: Record<string, string> = {
    draft: "草稿",
    pending_review: "待审查",
    approved: "已锁定",
    needs_rework: "需补充",
    archived: "已归档",
  };
  return labels[status] ?? status;
}

function formatSnapshotStatus(status: string): string {
  if (status === "success") return "已刷新";
  if (status === "failed") return "刷新失败";
  return status;
}

function formatWorkspaceStatus(status: string): string {
  return status === "clean" ? "干净" : "有本地变更";
}

function formatGuardStatus(status: string): string {
  return status === "ready" ? "可继续" : "需处理";
}
