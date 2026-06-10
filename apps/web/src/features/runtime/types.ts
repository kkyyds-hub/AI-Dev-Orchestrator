export interface RuntimeWorkspaceReadback {
  workspace_id: string | null;
  workspace_path_hint: string | null;
  repository_id: string | null;
  branch_name: string | null;
  worktree_id: string | null;
  workspace_bound: boolean;
}

export interface RuntimeProcessReadback {
  process_id: number | null;
  exit_code: number | null;
  started_at: string | null;
  finished_at: string | null;
  last_activity_at: string | null;
  heartbeat_at: string | null;
}

export interface RuntimeUsageReadback {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: string | number | null;
  cost_currency: string | null;
}

export interface RuntimeSessionReadback {
  session_id: string;
  executor_id: string;
  launch_preview_id: string | null;
  project_id: string | null;
  task_id: string | null;
  run_id: string | null;
  state: string;
  source: string;
  workspace: RuntimeWorkspaceReadback;
  process: RuntimeProcessReadback;
  usage: RuntimeUsageReadback;
  exit_reason: string | null;
  result_summary: string | null;
  error_summary: string | null;
  blocking_reasons: string[];
  created_by: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface RuntimeEventPayloadReadback {
  message: string | null;
  reason_code: string | null;
  state: string | null;
  metadata_count: number;
}

export interface RuntimeEventReadback {
  event_id: string;
  session_id: string;
  event_type: string;
  timestamp: string;
  payload: RuntimeEventPayloadReadback;
  append_only: boolean;
}

export interface RuntimeEventStreamReadback {
  session_id: string;
  events: RuntimeEventReadback[];
  total: number;
}

export interface RealExecutorSafetyBoundaryReadback {
  feature_flag_enabled: boolean;
  human_confirmation_present: boolean;
  executor_readiness_available: boolean;
  workspace_worktree_gate_passed: boolean;
  budget_cost_gate_passed: boolean;
  concurrency_gate_passed: boolean;
  timeout_supported: boolean;
  cancel_supported: boolean;
  kill_supported: boolean;
  audit_events_append_only: boolean;
  credential_exposure_blocked: boolean;
  environment_dump_blocked: boolean;
  product_runtime_git_write_allowed: boolean;
}

export interface RealExecutorLaunchReadbackRequest {
  request_id: string;
  executor_label: string;
  command_summary: string;
  workspace_hint: string;
  safety_boundary: RealExecutorSafetyBoundaryReadback;
}

export interface RealExecutorLaunchReadbackResponse {
  readback_id: string;
  executor_label: string;
  preflight_ready: boolean;
  preflight_status: string;
  preview_ready: boolean;
  preview_executable: boolean;
  adapter_enabled: boolean;
  adapter_launch_status: string;
  blocking_reasons: string[];
  display_steps: string[];
  safe_summary: string | null;
  redaction_applied: boolean;
  product_runtime_git_write_allowed: boolean;
  real_executor_launch_started: boolean;
  api_mode: "read_only";
  created_at: string;
}
