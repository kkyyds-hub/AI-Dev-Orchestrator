export type CostDashboardModeBreakdown = {
  mode: string;
  run_count: number;
  total_estimated_cost_usd: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
};

export type CostDashboardRoleBreakdown = {
  role_code: string;
  run_count: number;
  total_estimated_cost_usd: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
};

export type CostDashboardThreadBreakdown = {
  session_id: string;
  task_id: string;
  run_id: string;
  status: string;
  review_status: string;
  current_phase: string;
  owner_role_code: string;
  total_estimated_cost_usd: number;
  total_tokens: number;
  updated_at: string;
};

export type CostDashboardCacheMemoryCount = {
  memory_type: string;
  count: number;
};

export type CostDashboardCacheSummary = {
  total_memories: number;
  memory_type_counts: CostDashboardCacheMemoryCount[];
  cache_signal_note: string;
};

export type CostDashboardFallbackContract = {
  provider_reported_run_count: number;
  heuristic_run_count: number;
  missing_mode_run_count: number;
  fallback_active: boolean;
  fallback_reason: string;
};

export type ProjectCostDashboardSnapshot = {
  project_id: string;
  project_name: string;
  generated_at: string;
  task_count: number;
  task_count_with_runs: number;
  run_count: number;
  thread_count: number;
  total_estimated_cost_usd: number;
  avg_estimated_cost_per_run_usd: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  mode_breakdown: CostDashboardModeBreakdown[];
  role_breakdown: CostDashboardRoleBreakdown[];
  thread_breakdown: CostDashboardThreadBreakdown[];
  cache_summary: CostDashboardCacheSummary;
  fallback_contract: CostDashboardFallbackContract;
  day15_smoke_routes: string[];
};
