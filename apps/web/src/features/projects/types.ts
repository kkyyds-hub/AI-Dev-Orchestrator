import type { ConsoleBudget } from "../console/types";
import type { ChangeSession } from "../repositories/types";

export type ProjectTaskStats = {
  total_tasks: number;
  pending_tasks: number;
  running_tasks: number;
  paused_tasks: number;
  waiting_human_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  blocked_tasks: number;
  last_task_updated_at: string | null;
};

export type RepositoryWorkspace = {
  id: string;
  project_id: string;
  root_path: string;
  display_name: string;
  access_mode: "read_only";
  default_base_branch: string;
  ignore_rule_summary: string[];
  allowed_workspace_root: string;
  created_at: string;
  updated_at: string;
};

export type RepositorySnapshotStatus = "success" | "failed";

export type RepositoryLanguageStat = {
  language: string;
  file_count: number;
};

export type RepositoryTreeNode = {
  name: string;
  relative_path: string;
  kind: "directory" | "file";
  directory_count: number;
  file_count: number;
  children: RepositoryTreeNode[];
  truncated: boolean;
};

export type RepositorySnapshot = {
  id: string;
  project_id: string;
  repository_workspace_id: string;
  repository_root_path: string;
  status: RepositorySnapshotStatus;
  directory_count: number;
  file_count: number;
  ignored_directory_names: string[];
  language_breakdown: RepositoryLanguageStat[];
  tree: RepositoryTreeNode[];
  scan_error: string | null;
  scanned_at: string;
  created_at: string;
  updated_at: string;
};

export type BossProjectLatestTask = {
  task_id: string;
  title: string;
  status: string;
  priority: string;
  risk_level: string;
  human_status: string;
  updated_at: string;
  latest_run_status: string | null;
  latest_run_summary: string | null;
};

export type BossProjectItem = {
  id: string;
  name: string;
  summary: string;
  status: string;
  stage: string;
  task_stats: ProjectTaskStats;
  latest_progress_summary: string;
  latest_progress_at: string | null;
  key_risk_summary: string;
  risk_level: "healthy" | "warning" | "danger";
  blocked: boolean;
  estimated_cost: number;
  prompt_tokens: number;
  completion_tokens: number;
  attention_task_count: number;
  high_risk_task_count: number;
  latest_task: BossProjectLatestTask | null;
  repository_workspace: RepositoryWorkspace | null;
  latest_repository_snapshot: RepositorySnapshot | null;
  current_change_session: ChangeSession | null;
  created_at: string;
  updated_at: string;
};

export type ProjectStageDistributionItem = {
  stage: string;
  count: number;
};

export type BossProjectOverview = {
  total_projects: number;
  active_projects: number;
  completed_projects: number;
  blocked_projects: number;
  total_project_tasks: number;
  unassigned_tasks: number;
  stage_distribution: ProjectStageDistributionItem[];
  budget: ConsoleBudget;
  projects: BossProjectItem[];
};

export type ProjectDraft = {
  name: string;
  summary: string;
  status: string;
  stage: string;
};

export type PlannerTaskDraft = {
  draft_id: string;
  title: string;
  input_summary: string;
  priority: string;
  acceptance_criteria: string[];
  depends_on_draft_ids: string[];
  risk_level: string;
  human_status: string;
  paused_reason: string | null;
};

export type ProjectPlanDraft = {
  project_summary: string;
  planning_notes: string[];
  tasks: PlannerTaskDraft[];
  project: ProjectDraft | null;
};

export type ProjectPlanApplyProject = {
  id: string;
  name: string;
  summary: string;
  status: string;
  stage: string;
};

export type ProjectPlanApplyTask = {
  draft_id: string;
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
  upstream_role_code: string | null;
  downstream_role_code: string | null;
  human_status: string;
  paused_reason: string | null;
  source_draft_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectPlanApplyResult = {
  project_summary: string;
  created_count: number;
  tasks: ProjectPlanApplyTask[];
  project: ProjectPlanApplyProject | null;
};

export type ChangePlanStatus = "draft";

export type ChangePlanTargetFile = {
  relative_path: string;
  language: string;
  file_type: string;
  rationale: string | null;
  match_reasons: string[];
};

export type ChangePlanLinkedDeliverable = {
  deliverable_id: string;
  title: string;
  type: string;
  current_version_number: number;
};

export type ChangePlanVersion = {
  id: string;
  version_number: number;
  intent_summary: string;
  source_summary: string;
  focus_terms: string[];
  target_files: ChangePlanTargetFile[];
  expected_actions: string[];
  risk_notes: string[];
  verification_commands: string[];
  related_deliverables: ChangePlanLinkedDeliverable[];
  context_pack_generated_at: string | null;
  created_at: string;
};

export type ChangePlanSummary = {
  id: string;
  project_id: string;
  task_id: string;
  task_title: string;
  status: ChangePlanStatus;
  title: string;
  primary_deliverable_id: string | null;
  current_version_number: number;
  latest_version: ChangePlanVersion;
  created_at: string;
  updated_at: string;
};

export type ChangePlanDetail = ChangePlanSummary & {
  versions: ChangePlanVersion[];
};

export type ChangePlanDraftInput = {
  title?: string | null;
  primary_deliverable_id?: string | null;
  related_deliverable_ids: string[];
  intent_summary: string;
  source_summary: string;
  focus_terms: string[];
  target_files: ChangePlanTargetFile[];
  expected_actions: string[];
  risk_notes: string[];
  verification_commands: string[];
  context_pack_generated_at?: string | null;
};

export type ChangePlanCreateInput = ChangePlanDraftInput & {
  task_id: string;
};

export type ProjectDetailTaskItem = {
  id: string;
  project_id: string | null;
  title: string;
  status: string;
  priority: string;
  input_summary: string;
  acceptance_criteria: string[];
  depends_on_task_ids: string[];
  child_task_ids: string[];
  depth: number;
  risk_level: string;
  owner_role_code: string | null;
  upstream_role_code: string | null;
  downstream_role_code: string | null;
  human_status: string;
  paused_reason: string | null;
  source_draft_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectMilestone = {
  code: string;
  title: string;
  satisfied: boolean;
  summary: string;
  blocking_reasons: string[];
  related_task_ids: string[];
};

export type ProjectStageBlockingTask = {
  task_id: string;
  title: string;
  status: string;
  blocking_reasons: string[];
};

export type ProjectStageGuard = {
  current_stage: string;
  target_stage: string | null;
  can_advance: boolean;
  milestones: ProjectMilestone[];
  blocking_reasons: string[];
  blocking_tasks: ProjectStageBlockingTask[];
  total_tasks: number;
  ready_task_count: number;
  completed_task_count: number;
  current_stage_task_count: number;
  current_stage_completed_task_count: number;
};

export type ProjectStageTimelineEntry = {
  id: string;
  from_stage: string | null;
  to_stage: string;
  outcome: "applied" | "blocked";
  note: string | null;
  reasons: string[];
  created_at: string;
};

export type ProjectDetail = {
  id: string;
  name: string;
  summary: string;
  status: string;
  stage: string;
  task_stats: ProjectTaskStats;
  repository_workspace: RepositoryWorkspace | null;
  latest_repository_snapshot: RepositorySnapshot | null;
  current_change_session: ChangeSession | null;
  created_at: string;
  updated_at: string;
  tasks: ProjectDetailTaskItem[];
  stage_guard: ProjectStageGuard | null;
  stage_timeline: ProjectStageTimelineEntry[];
  sop_snapshot: ProjectSopSnapshot | null;
};

export type ProjectMemoryKind =
  | "conclusion"
  | "failure_pattern"
  | "approval_feedback"
  | "deliverable_summary";

export type ProjectMemoryCount = {
  memory_type: ProjectMemoryKind;
  count: number;
};

export type ProjectMemoryItem = {
  memory_id: string;
  memory_type: ProjectMemoryKind;
  title: string;
  summary: string;
  detail: string | null;
  stage: string | null;
  role_code: string | null;
  actor_name: string | null;
  source_kind: string;
  source_label: string;
  task_id: string | null;
  run_id: string | null;
  approval_id: string | null;
  deliverable_id: string | null;
  deliverable_version_id: string | null;
  tags: string[];
  created_at: string;
};

export type ProjectMemorySnapshot = {
  project_id: string;
  project_name: string;
  generated_at: string;
  total_memories: number;
  counts: ProjectMemoryCount[];
  latest_items: ProjectMemoryItem[];
};

export type ProjectMemorySearchHit = {
  score: number;
  matched_terms: string[];
  item: ProjectMemoryItem;
};

export type ProjectMemorySearchResult = {
  project_id: string;
  query: string;
  total_matches: number;
  hits: ProjectMemorySearchHit[];
};

export type ProjectStageAdvanceResult = {
  project_id: string;
  previous_stage: string;
  attempted_stage: string;
  current_stage: string;
  advanced: boolean;
  message: string;
  stage_guard: ProjectStageGuard;
  timeline_entry: ProjectStageTimelineEntry;
};

export type ProjectSopTemplateStagePreview = {
  stage: string;
  title: string;
  owner_role_codes: string[];
};

export type ProjectSopTemplateSummary = {
  code: string;
  name: string;
  summary: string;
  description: string;
  is_default: boolean;
  stages: ProjectSopTemplateStagePreview[];
};

export type ProjectSopOwnerRole = {
  role_code: string;
  name: string;
  summary: string;
  enabled: boolean;
};

export type ProjectSopStageTask = {
  task_id: string;
  task_code: string;
  title: string;
  status: string;
  owner_role_codes: string[];
  owner_role_names: string[];
};

export type ProjectSopSnapshot = {
  project_id: string;
  has_template: boolean;
  available_template_count: number;
  selected_template_code: string | null;
  selected_template_name: string | null;
  selected_template_summary: string | null;
  current_stage: string;
  current_stage_title: string | null;
  current_stage_summary: string | null;
  next_stage: string | null;
  can_advance: boolean | null;
  blocking_reasons: string[];
  required_inputs: string[];
  expected_outputs: string[];
  guard_conditions: string[];
  owner_roles: ProjectSopOwnerRole[];
  stage_tasks: ProjectSopStageTask[];
  current_stage_task_count: number;
  current_stage_completed_task_count: number;
  all_current_stage_tasks_completed: boolean;
  context_summary: string;
};

export type ProjectSopTemplateSelectResult = {
  project_id: string;
  template_code: string;
  template_name: string;
  created_task_count: number;
  message: string;
  created_tasks: Array<{
    id: string;
    title: string;
    status: string;
    source_draft_id: string | null;
  }>;
  sop_snapshot: ProjectSopSnapshot;
};

export type ProjectTimelineEventType =
  | "stage"
  | "deliverable"
  | "preflight"
  | "approval"
  | "role_handoff"
  | "decision";

export type ProjectTimelineEventTypeCount = {
  event_type: ProjectTimelineEventType;
  label: string;
  count: number;
};

export type ProjectTimelineEvent = {
  id: string;
  event_type: ProjectTimelineEventType;
  label: string;
  tone: "neutral" | "info" | "success" | "warning" | "danger";
  title: string;
  summary: string;
  occurred_at: string;
  stage: string | null;
  task_id: string | null;
  task_title: string | null;
  run_id: string | null;
  deliverable_id: string | null;
  deliverable_title: string | null;
  deliverable_version_id: string | null;
  deliverable_version_number: number | null;
  approval_id: string | null;
  approval_status: string | null;
  source_event: string | null;
  actor: string | null;
  metadata: Record<string, unknown>;
};

export type ProjectTimeline = {
  project_id: string;
  generated_at: string;
  total_events: number;
  event_type_counts: ProjectTimelineEventTypeCount[];
  events: ProjectTimelineEvent[];
};

export const PROJECT_STAGE_LABELS: Record<string, string> = {
  intake: "需求入口",
  planning: "规划中",
  execution: "执行中",
  verification: "验证中",
  delivery: "交付中",
};

export const PROJECT_STATUS_LABELS: Record<string, string> = {
  active: "进行中",
  on_hold: "挂起",
  completed: "已完成",
  archived: "已归档",
};

export const PROJECT_STAGE_HISTORY_OUTCOME_LABELS: Record<string, string> = {
  applied: "已推进",
  blocked: "被守卫拦截",
};

export const PROJECT_RISK_LABELS: Record<string, string> = {
  healthy: "健康",
  warning: "需关注",
  danger: "阻塞",
};

export const TASK_STATUS_LABELS: Record<string, string> = {
  pending: "待处理",
  running: "执行中",
  paused: "已暂停",
  waiting_human: "待人工",
  completed: "已完成",
  failed: "失败",
  blocked: "阻塞",
};

export const TASK_PRIORITY_LABELS: Record<string, string> = {
  low: "低",
  normal: "常规",
  high: "高",
  urgent: "紧急",
};

export const TASK_RISK_LABELS: Record<string, string> = {
  low: "低风险",
  normal: "常规",
  high: "高风险",
};

export const HUMAN_STATUS_LABELS: Record<string, string> = {
  none: "无需人工",
  requested: "待人工介入",
  in_progress: "人工处理中",
  resolved: "人工已处理",
};

export const PROJECT_TIMELINE_EVENT_TYPE_LABELS: Record<
  ProjectTimelineEventType,
  string
> = {
  stage: "阶段推进",
  deliverable: "交付件提交",
  preflight: "执行前预检",
  approval: "审批动作",
  role_handoff: "角色交接",
  decision: "运行决策",
};

export const PROJECT_MEMORY_KIND_LABELS: Record<ProjectMemoryKind, string> = {
  conclusion: "关键结论",
  failure_pattern: "失败模式",
  approval_feedback: "审批意见",
  deliverable_summary: "交付件摘要",
};

export const PROJECT_MEMORY_SOURCE_KIND_LABELS: Record<string, string> = {
  run: "运行记录",
  failure_review: "失败复盘",
  approval_decision: "审批决定",
  deliverable_version: "交付件版本",
};
