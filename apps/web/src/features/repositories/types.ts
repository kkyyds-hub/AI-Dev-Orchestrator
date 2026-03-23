import type {
  ChangePlanLinkedDeliverable,
  ChangePlanTargetFile,
} from "../projects/types";

export type ChangeSessionWorkspaceStatus = "clean" | "dirty";

export type ChangeSessionGuardStatus = "ready" | "blocked";

export type ChangeSessionDirtyFileScope =
  | "untracked"
  | "staged"
  | "unstaged"
  | "mixed";

export type ChangeSessionDirtyFile = {
  path: string;
  git_status: string;
  change_scope: ChangeSessionDirtyFileScope;
};

export type ChangeSession = {
  id: string;
  project_id: string;
  repository_workspace_id: string;
  repository_root_path: string;
  current_branch: string;
  head_ref: string;
  head_commit_sha: string | null;
  baseline_branch: string;
  baseline_ref: string;
  baseline_commit_sha: string | null;
  workspace_status: ChangeSessionWorkspaceStatus;
  guard_status: ChangeSessionGuardStatus;
  guard_summary: string;
  blocking_reasons: string[];
  dirty_file_count: number;
  dirty_files_truncated: boolean;
  dirty_files: ChangeSessionDirtyFile[];
  created_at: string;
  updated_at: string;
};

export type FileLocatorQuery = {
  task_id: string | null;
  task_title: string | null;
  task_query: string | null;
  keywords: string[];
  path_prefixes: string[];
  module_names: string[];
  file_types: string[];
  limit: number;
  summary: string;
};

export type FileLocatorCandidate = {
  relative_path: string;
  language: string;
  file_type: string;
  byte_size: number;
  line_count: number;
  score: number;
  match_reasons: string[];
  matched_keywords: string[];
  preview: string | null;
};

export type FileLocatorResult = {
  project_id: string;
  repository_root_path: string;
  ignored_directory_names: string[];
  query: FileLocatorQuery;
  scanned_file_count: number;
  candidate_count: number;
  total_match_count: number;
  truncated: boolean;
  generated_at: string;
  candidates: FileLocatorCandidate[];
};

export type CodeContextPackEntry = {
  relative_path: string;
  language: string;
  file_type: string;
  byte_size: number;
  line_count: number;
  included_bytes: number;
  included_line_count: number;
  start_line: number;
  end_line: number;
  truncated: boolean;
  match_reasons: string[];
  excerpt: string;
};

export type CodeContextPack = {
  project_id: string | null;
  repository_root_path: string;
  source_summary: string;
  focus_terms: string[];
  selected_paths: string[];
  omitted_paths: string[];
  max_total_bytes: number;
  max_bytes_per_file: number;
  included_file_count: number;
  total_included_bytes: number;
  truncated: boolean;
  generated_at: string;
  entries: CodeContextPackEntry[];
};

export type FileLocatorSearchInput = {
  task_id?: string | null;
  task_query?: string | null;
  keywords?: string[];
  path_prefixes?: string[];
  module_names?: string[];
  file_types?: string[];
  limit?: number;
};

export type CodeContextPackBuildInput = FileLocatorSearchInput & {
  selected_paths: string[];
  max_total_bytes?: number;
  max_bytes_per_file?: number;
  selection_reasons_by_path?: Record<string, string[]>;
};

export type ChangeBatchStatus = "preparing" | "superseded";

export type ChangeBatchRiskCategory =
  | "sensitive_directory"
  | "sensitive_file"
  | "dangerous_command"
  | "wide_change";

export type ChangeBatchRiskSeverity = "low" | "medium" | "high" | "critical";

export type ChangeBatchPreflightStatus =
  | "not_started"
  | "ready_for_execution"
  | "blocked_requires_confirmation"
  | "manual_confirmed"
  | "manual_rejected";

export type ChangeBatchManualConfirmationStatus =
  | "not_required"
  | "pending"
  | "approved"
  | "rejected";

export type ChangeBatchManualConfirmationAction = "approve" | "reject";

export type ChangeBatchRiskFinding = {
  category: ChangeBatchRiskCategory;
  severity: ChangeBatchRiskSeverity;
  code: string;
  title: string;
  summary: string;
  affected_paths: string[];
  related_commands: string[];
};

export type ChangeBatchManualConfirmationDecision = {
  action: ChangeBatchManualConfirmationAction;
  actor_name: string;
  summary: string;
  comment: string | null;
  highlighted_risks: string[];
  created_at: string;
};

export type ChangeBatchPreflight = {
  status: ChangeBatchPreflightStatus;
  summary: string | null;
  overall_severity: ChangeBatchRiskSeverity | null;
  blocked: boolean;
  ready_for_execution: boolean;
  findings: ChangeBatchRiskFinding[];
  finding_count: number;
  critical_risk_count: number;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  scanned_target_file_count: number;
  unique_directory_count: number;
  inspected_command_count: number;
  inspected_commands: string[];
  manual_confirmation_required: boolean;
  manual_confirmation_status: ChangeBatchManualConfirmationStatus;
  requested_at: string | null;
  evaluated_at: string | null;
  decided_at: string | null;
  decision_history: ChangeBatchManualConfirmationDecision[];
};

export type ChangeBatchDependency = {
  task_id: string;
  task_title: string;
  in_batch: boolean;
  missing: boolean;
  order_index: number | null;
};

export type ChangeBatchTask = {
  order_index: number;
  task_id: string;
  task_title: string;
  task_priority: string;
  task_risk_level: string;
  change_plan_id: string;
  change_plan_title: string;
  selected_version_number: number;
  intent_summary: string;
  expected_actions: string[];
  verification_commands: string[];
  related_deliverables: ChangePlanLinkedDeliverable[];
  dependencies: ChangeBatchDependency[];
  target_files: ChangePlanTargetFile[];
  overlap_file_paths: string[];
};

export type ChangeBatchTargetFileAggregate = {
  relative_path: string;
  language: string;
  file_type: string;
  match_reasons: string[];
  rationales: string[];
  task_ids: string[];
  task_titles: string[];
  change_plan_ids: string[];
  change_plan_titles: string[];
  overlap_count: number;
};

export type ChangeBatchTimelineEntry = {
  entry_type: string;
  label: string;
  summary: string;
  occurred_at: string;
};

export type ChangeBatchSummary = {
  id: string;
  project_id: string;
  repository_workspace_id: string | null;
  status: ChangeBatchStatus;
  title: string;
  summary: string;
  active: boolean;
  change_plan_count: number;
  task_count: number;
  target_file_count: number;
  overlap_file_count: number;
  dependency_count: number;
  verification_command_count: number;
  preflight: ChangeBatchPreflight;
  created_at: string;
  updated_at: string;
};

export type ChangeBatchDetail = ChangeBatchSummary & {
  tasks: ChangeBatchTask[];
  target_files: ChangeBatchTargetFileAggregate[];
  overlap_files: ChangeBatchTargetFileAggregate[];
  timeline: ChangeBatchTimelineEntry[];
};

export type ChangeBatchCreateInput = {
  title?: string | null;
  change_plan_ids: string[];
};

export type ChangeBatchPreflightInput = {
  candidate_commands?: string[];
};

export const CHANGE_BATCH_PREFLIGHT_STATUS_LABELS: Record<
  ChangeBatchPreflightStatus,
  string
> = {
  not_started: "未预检",
  ready_for_execution: "可进入执行",
  blocked_requires_confirmation: "已阻断待人工确认",
  manual_confirmed: "人工已放行",
  manual_rejected: "人工已驳回",
};

export const CHANGE_BATCH_RISK_SEVERITY_LABELS: Record<
  ChangeBatchRiskSeverity,
  string
> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
  critical: "严重风险",
};

export const CHANGE_BATCH_RISK_CATEGORY_LABELS: Record<
  ChangeBatchRiskCategory,
  string
> = {
  sensitive_directory: "敏感目录",
  sensitive_file: "敏感文件",
  dangerous_command: "危险命令",
  wide_change: "大范围变更",
};
