export type HealthResponse = {
  status: string;
  service: string;
};

export type ConsoleBudget = {
  daily_budget_usd: number;
  daily_cost_used: number;
  daily_cost_remaining: number;
  daily_usage_ratio: number;
  daily_budget_exceeded: boolean;
  daily_window_started_at: string;
  session_budget_usd: number;
  session_cost_used: number;
  session_cost_remaining: number;
  session_usage_ratio: number;
  session_budget_exceeded: boolean;
  session_started_at: string;
  max_task_retries: number;
  pressure_level: "normal" | "warning" | "critical" | "blocked";
  suggested_action: "full_speed" | "conservative" | "degraded" | "block";
  strategy_code: string;
  strategy_label: string;
  strategy_summary: string;
  budget_blocked_runs_daily: number;
  budget_blocked_runs_session: number;
};

export type RoutingScoreItem = {
  code: string;
  label: string;
  score: number;
  detail: string;
};

export type ConsoleRun = {
  id: string;
  status: string;
  route_reason: string | null;
  routing_score: number | null;
  routing_score_breakdown: RoutingScoreItem[];
  owner_role_code: string | null;
  upstream_role_code: string | null;
  downstream_role_code: string | null;
  handoff_reason: string | null;
  dispatch_status: string | null;
  result_summary: string | null;
  provider_key: string | null;
  prompt_template_key: string | null;
  prompt_template_version: string | null;
  prompt_char_count: number | null;
  token_accounting_mode: string | null;
  provider_receipt_id: string | null;
  total_tokens: number | null;
  token_pricing_source: string | null;
  role_model_policy_source: string | null;
  role_model_policy_desired_tier: string | null;
  role_model_policy_adjusted_tier: string | null;
  role_model_policy_final_tier: string | null;
  role_model_policy_stage_override_applied: boolean;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_cost: number;
  log_path: string | null;
  verification_mode: string | null;
  verification_template: string | null;
  verification_command: string | null;
  verification_summary: string | null;
  failure_category: string | null;
  quality_gate_passed: boolean | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type TaskBlockingSignal = {
  code: string;
  category: string;
  message: string;
};

export type ConsoleTask = {
  id: string;
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
  created_at: string;
  updated_at: string;
  latest_run: ConsoleRun | null;
};

export type ConsoleOverview = {
  total_tasks: number;
  pending_tasks: number;
  running_tasks: number;
  paused_tasks: number;
  waiting_human_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  blocked_tasks: number;
  total_estimated_cost: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  budget: ConsoleBudget;
  tasks: ConsoleTask[];
};
