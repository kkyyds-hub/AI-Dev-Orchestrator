export type RunLogEvent = {
  timestamp: string;
  level: string;
  event: string;
  message: string;
  data: Record<string, unknown>;
};

export type RunLogResponse = {
  run_id: string;
  log_path: string | null;
  limit: number;
  truncated: boolean;
  events: RunLogEvent[];
};

export type FailureReview = {
  review_id: string;
  task_id: string;
  task_title: string;
  task_status: string;
  run_id: string;
  run_status: string;
  created_at: string;
  failure_category: string | null;
  quality_gate_passed: boolean | null;
  route_reason: string | null;
  result_summary: string | null;
  log_path: string | null;
  evidence_events: string[];
  action_summary: string;
  conclusion: string;
  storage_path: string | null;
};

export type DecisionTraceItem = {
  timestamp: string;
  stage: string;
  title: string;
  event: string;
  level: string;
  summary: string;
  data: Record<string, unknown>;
};

export type DecisionTraceResponse = {
  run_id: string;
  task_id: string;
  run_status: string;
  failure_category: string | null;
  quality_gate_passed: boolean | null;
  trace_items: DecisionTraceItem[];
  failure_review: FailureReview | null;
};

export type VerificationRunStatus = "passed" | "failed" | "skipped";

export type VerificationRunCommandSource = "template" | "manual";

export type VerificationRunFailureCategory =
  | "command_failed"
  | "command_timeout"
  | "configuration_error"
  | "precheck_blocked"
  | "manually_skipped"
  | "workspace_unavailable";

export type VerificationRun = {
  id: string;
  project_id: string;
  repository_workspace_id: string;
  repository_root_path: string;
  repository_display_name: string | null;
  change_plan_id: string;
  change_plan_title: string;
  change_batch_id: string;
  change_batch_title: string;
  task_title: string | null;
  verification_template_id: string | null;
  verification_template_name: string | null;
  verification_template_category:
    | "build"
    | "test"
    | "lint"
    | "typecheck"
    | null;
  command_source: VerificationRunCommandSource;
  command: string;
  working_directory: string;
  status: VerificationRunStatus;
  failure_category: VerificationRunFailureCategory | null;
  duration_seconds: number;
  output_summary: string;
  started_at: string;
  finished_at: string;
  created_at: string;
};

export type VerificationRunFeed = {
  project_id: string;
  repository_workspace_id: string;
  repository_root_path: string;
  repository_display_name: string | null;
  change_batch_id: string | null;
  total_runs: number;
  status_counts: Record<VerificationRunStatus, number>;
  latest_run: VerificationRun | null;
  runs: VerificationRun[];
};
