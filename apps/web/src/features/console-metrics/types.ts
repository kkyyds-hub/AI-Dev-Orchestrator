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

export type WorkerSlotOverview = {
  pending_tasks: number;
  running_tasks: number;
  blocked_tasks: number;
  budget_guard_active: boolean;
  slot_snapshot: WorkerSlotSnapshot;
};

export type ConsoleMetricsOverview = {
  total_runs: number;
  queued_runs: number;
  running_runs: number;
  succeeded_runs: number;
  failed_runs: number;
  cancelled_runs: number;
  total_estimated_cost: number;
  avg_estimated_cost: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  avg_prompt_tokens: number;
  avg_completion_tokens: number;
  latest_run_created_at: string | null;
};

export type ConsoleBudgetHealth = {
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

export type RunStatusDistribution = {
  status: string;
  label: string;
  count: number;
};

export type FailureCategoryDistribution = {
  category_code: string;
  category_label: string;
  count: number;
};

export type ConsoleFailureDistribution = {
  total_runs: number;
  failed_or_cancelled_runs: number;
  status_distribution: RunStatusDistribution[];
  failure_category_distribution: FailureCategoryDistribution[];
};

export type RoutingDistributionItem = {
  reason_code: string;
  reason_label: string;
  count: number;
};

export type ConsoleRoutingDistribution = {
  total_routed_runs: number;
  distribution: RoutingDistributionItem[];
};

export type DecisionHistoryItem = {
  run_id: string;
  status: string;
  failure_category: string | null;
  quality_gate_passed: boolean | null;
  created_at: string;
  headline: string;
  stages: string[];
};

export type ReviewCluster = {
  cluster_key: string;
  failure_category: string;
  count: number;
  latest_run_created_at: string;
  route_reason_excerpt: string | null;
  sample_task_titles: string[];
  run_ids: string[];
};
