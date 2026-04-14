export type WorkerRunOnceResponse = {
  claimed: boolean;
  message: string;
  execution_mode: string | null;
  verification_mode: string | null;
  verification_template: string | null;
  verification_summary: string | null;
  failure_category: string | null;
  quality_gate_passed: boolean | null;
  route_reason: string | null;
  routing_score: number | null;
  routing_score_breakdown: Array<{
    code: string;
    label: string;
    score: number;
    detail: string;
  }>;
  owner_role_code: string | null;
  upstream_role_code: string | null;
  downstream_role_code: string | null;
  handoff_reason: string | null;
  dispatch_status: string | null;
  project_memory_enabled: boolean | null;
  project_memory_query_text: string | null;
  project_memory_item_count: number | null;
  project_memory_context_summary: string | null;
  result_summary: string | null;
  context_summary: string | null;
  model_name: string | null;
  model_tier: string | null;
  selected_skill_codes: string[];
  selected_skill_names: string[];
  strategy_code: string | null;
  strategy_summary: string | null;
  role_model_policy_source: string | null;
  role_model_policy_desired_tier: string | null;
  role_model_policy_adjusted_tier: string | null;
  role_model_policy_final_tier: string | null;
  role_model_policy_stage_override_applied: boolean;
  task_id: string | null;
  task_title: string | null;
  task_status: string | null;
  run_id: string | null;
  run_status: string | null;
  run_created_at: string | null;
  run_finished_at: string | null;
  provider_key: string | null;
  prompt_template_key: string | null;
  prompt_template_version: string | null;
  prompt_char_count: number | null;
  token_accounting_mode: string | null;
  provider_receipt_id: string | null;
  total_tokens: number | null;
  token_pricing_source: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  estimated_cost: number | null;
  log_path: string | null;
};

export type WorkerSlot = {
  slot_id: number;
  state: string;
  worker_name: string | null;
  task_id: string | null;
  task_title: string | null;
  run_id: string | null;
  acquired_at: string | null;
  last_task_id: string | null;
  last_task_title: string | null;
  last_run_id: string | null;
  last_released_at: string | null;
};

export type WorkerSlotSnapshot = {
  max_concurrent_workers: number;
  running_slots: number;
  idle_slots: number;
  slots: WorkerSlot[];
};

export type WorkerPoolRunResponse = {
  requested_workers: number;
  launched_workers: number;
  claimed_runs: number;
  idle_workers: number;
  results: WorkerRunOnceResponse[];
  slot_snapshot: WorkerSlotSnapshot;
};

export type TaskRetryResponse = {
  message: string;
  task_id: string;
  task_title: string;
  previous_status: string;
  current_status: string;
  updated_at: string;
};

export type TaskStateActionResponse = {
  message: string;
  task_id: string;
  task_title: string;
  previous_status: string;
  current_status: string;
  human_status: string;
  paused_reason: string | null;
  updated_at: string;
};
