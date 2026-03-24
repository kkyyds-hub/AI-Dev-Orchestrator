export type DeliverableType =
  | "prd"
  | "design"
  | "task_breakdown"
  | "code_plan"
  | "acceptance_conclusion"
  | "stage_artifact";

export type DeliverableContentFormat =
  | "markdown"
  | "plain_text"
  | "json"
  | "link";

export type DeliverableVersionSummary = {
  id: string;
  version_number: number;
  author_role_code: string;
  summary: string;
  content_format: DeliverableContentFormat;
  source_task_id: string | null;
  source_run_id: string | null;
  created_at: string;
};

export type DeliverableVersion = DeliverableVersionSummary & {
  content: string;
};

export type DeliverableSummary = {
  id: string;
  project_id: string;
  type: DeliverableType;
  title: string;
  stage: string;
  created_by_role_code: string;
  current_version_number: number;
  total_versions: number;
  created_at: string;
  updated_at: string;
  latest_version: DeliverableVersionSummary;
};

export type ProjectDeliverableSnapshot = {
  project_id: string;
  total_deliverables: number;
  total_versions: number;
  generated_at: string;
  deliverables: DeliverableSummary[];
};

export type DeliverableDetail = {
  id: string;
  project_id: string;
  type: DeliverableType;
  title: string;
  stage: string;
  created_by_role_code: string;
  current_version_number: number;
  total_versions: number;
  created_at: string;
  updated_at: string;
  versions: DeliverableVersion[];
};

export type DeliverableDiffLine = {
  kind: "context" | "added" | "removed";
  content: string;
  base_line_number: number | null;
  target_line_number: number | null;
};

export type DeliverableVersionDiff = {
  deliverable_id: string;
  project_id: string;
  title: string;
  type: DeliverableType;
  stage: string;
  base_version: DeliverableVersion;
  target_version: DeliverableVersion;
  format_changed: boolean;
  added_line_count: number;
  removed_line_count: number;
  unchanged_line_count: number;
  changed_block_count: number;
  diff_lines: DeliverableDiffLine[];
};

export type TaskRelatedDeliverable = {
  deliverable_id: string;
  project_id: string;
  type: DeliverableType;
  title: string;
  stage: string;
  current_version_number: number;
  matched_version: DeliverableVersionSummary;
};

export type DiffComparisonMode = "baseline_to_worktree";

export type DiffFileChangeKind = "added" | "modified" | "deleted" | "untracked";

export type VerificationRunStatus = "passed" | "failed" | "skipped";

export type VerificationRunCommandSource = "template" | "manual";

export type VerificationRunFailureCategory =
  | "command_failed"
  | "command_timeout"
  | "configuration_error"
  | "precheck_blocked"
  | "manually_skipped"
  | "workspace_unavailable";

export type ChangeEvidenceApprovalStatus =
  | "pending_approval"
  | "approved"
  | "rejected"
  | "changes_requested";

export type ChangeEvidenceApprovalAction =
  | "approve"
  | "reject"
  | "request_changes";

export type ChangeEvidenceSnapshotKind =
  | "change_batch"
  | "deliverable_version"
  | "approval"
  | "verification_run";

export type DiffFileChange = {
  relative_path: string;
  change_kind: DiffFileChangeKind;
  added_line_count: number;
  deleted_line_count: number;
  changed_line_count: number;
  in_change_batch: boolean;
  in_dirty_workspace: boolean;
  linked_task_ids: string[];
  linked_change_plan_ids: string[];
  notes: string[];
};

export type DiffSummaryMetrics = {
  changed_file_count: number;
  key_file_count: number;
  added_file_count: number;
  modified_file_count: number;
  deleted_file_count: number;
  untracked_file_count: number;
  total_added_line_count: number;
  total_deleted_line_count: number;
};

export type DiffSummary = {
  project_id: string;
  repository_workspace_id: string;
  repository_root_path: string;
  baseline_label: string;
  target_label: string;
  comparison_mode: DiffComparisonMode;
  dirty_workspace: boolean;
  dirty_file_count: number;
  note: string | null;
  generated_at: string;
  metrics: DiffSummaryMetrics;
  key_files: DiffFileChange[];
  files: DiffFileChange[];
};

export type ChangeEvidencePlanItem = {
  change_plan_id: string;
  change_plan_title: string;
  selected_version_number: number;
  task_id: string;
  task_title: string;
  intent_summary: string;
  expected_actions: string[];
  risk_notes: string[];
  target_file_paths: string[];
  verification_commands: string[];
  verification_template_names: string[];
  related_deliverable_ids: string[];
  related_deliverable_titles: string[];
};

export type ChangeEvidenceVerificationRunItem = {
  verification_run_id: string;
  change_batch_id: string;
  change_batch_title: string;
  change_plan_id: string;
  change_plan_title: string;
  task_title: string | null;
  verification_template_name: string | null;
  status: VerificationRunStatus;
  failure_category: VerificationRunFailureCategory | null;
  command_source: VerificationRunCommandSource;
  command: string;
  output_summary: string;
  started_at: string;
  finished_at: string;
};

export type ChangeEvidenceVerificationSummary = {
  total_runs: number;
  passed_runs: number;
  failed_runs: number;
  skipped_runs: number;
  latest_finished_at: string | null;
  runs: ChangeEvidenceVerificationRunItem[];
};

export type ChangeEvidenceDeliverableReference = {
  deliverable_id: string;
  title: string;
  type: DeliverableType;
  stage: string;
  current_version_number: number;
  latest_version_id: string | null;
  latest_version_summary: string | null;
  latest_version_created_at: string | null;
  source_task_id: string | null;
  source_run_id: string | null;
  selected: boolean;
};

export type ChangeEvidenceApprovalReference = {
  approval_id: string;
  deliverable_id: string;
  deliverable_title: string;
  deliverable_version_number: number;
  status: ChangeEvidenceApprovalStatus;
  request_note: string | null;
  latest_summary: string | null;
  latest_decision_action: ChangeEvidenceApprovalAction | null;
  latest_decision_summary: string | null;
  latest_decision_actor_name: string | null;
  latest_decision_at: string | null;
  requested_changes: string[];
  highlighted_risks: string[];
  requested_at: string;
  due_at: string;
  decided_at: string | null;
  selected: boolean;
};

export type ChangeEvidenceSnapshot = {
  snapshot_id: string;
  label: string;
  summary: string;
  snapshot_kind: ChangeEvidenceSnapshotKind;
  source_id: string | null;
  recorded_at: string;
  selected: boolean;
};

export type ChangeEvidenceReverseLookup = {
  project_id: string;
  change_batch_id: string | null;
  deliverable_ids: string[];
  approval_ids: string[];
};

export type ChangeEvidencePackage = {
  project_id: string;
  repository_workspace_id: string;
  repository_root_path: string;
  package_key: string;
  summary: string;
  selected_change_batch_id: string | null;
  selected_change_batch_title: string | null;
  selected_deliverable_id: string | null;
  selected_approval_id: string | null;
  generated_at: string;
  diff_summary: DiffSummary;
  plan_items: ChangeEvidencePlanItem[];
  verification_summary: ChangeEvidenceVerificationSummary;
  deliverables: ChangeEvidenceDeliverableReference[];
  approvals: ChangeEvidenceApprovalReference[];
  snapshots: ChangeEvidenceSnapshot[];
  reverse_lookup: ChangeEvidenceReverseLookup;
};

export const DELIVERABLE_TYPE_LABELS: Record<DeliverableType, string> = {
  prd: "PRD",
  design: "设计稿",
  task_breakdown: "任务拆分",
  code_plan: "代码计划",
  acceptance_conclusion: "验收结论",
  stage_artifact: "阶段产物",
};

export const DELIVERABLE_CONTENT_FORMAT_LABELS: Record<
  DeliverableContentFormat,
  string
> = {
  markdown: "Markdown",
  plain_text: "文本",
  json: "JSON",
  link: "链接",
};
