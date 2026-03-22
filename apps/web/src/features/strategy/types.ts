export type StrategyReasonItem = {
  code: string;
  label: string;
  detail: string;
  score: number | null;
};

export type StrategyRoutingScoreItem = {
  code: string;
  label: string;
  score: number;
  detail: string;
};

export type StrategyCandidate = {
  task_id: string;
  title: string;
  ready: boolean;
  routing_score: number | null;
  route_reason: string;
  project_stage: string | null;
  owner_role_code: string | null;
  upstream_role_code: string | null;
  downstream_role_code: string | null;
  dispatch_status: string;
  handoff_reason: string;
  matched_terms: string[];
  model_name: string | null;
  model_tier: string | null;
  selected_skill_codes: string[];
  selected_skill_names: string[];
  strategy_code: string;
  strategy_summary: string;
  strategy_reasons: StrategyReasonItem[];
  routing_score_breakdown: StrategyRoutingScoreItem[];
  execution_attempts: number;
  recent_failure_count: number;
  budget_pressure_level: "normal" | "warning" | "critical" | "blocked";
  budget_action: "full_speed" | "conservative" | "degraded" | "block";
  budget_strategy_code: string;
  budget_score_adjustment: number;
  blocking_signals: Array<{
    code: string;
    category: string;
    message: string;
  }>;
};

export type ProjectStrategyPreview = {
  project_id: string;
  project_name: string;
  project_stage: string;
  selected_task_id: string | null;
  selected_task_title: string | null;
  message: string;
  budget_pressure_level: "normal" | "warning" | "critical" | "blocked";
  budget_action: "full_speed" | "conservative" | "degraded" | "block";
  budget_strategy_code: string;
  budget_strategy_summary: string;
  owner_role_code: string | null;
  upstream_role_code: string | null;
  downstream_role_code: string | null;
  dispatch_status: string | null;
  handoff_reason: string | null;
  model_name: string | null;
  model_tier: string | null;
  selected_skill_codes: string[];
  selected_skill_names: string[];
  strategy_code: string | null;
  strategy_summary: string | null;
  strategy_reasons: StrategyReasonItem[];
  routing_score: number | null;
  route_reason: string | null;
  routing_score_breakdown: StrategyRoutingScoreItem[];
  candidates: StrategyCandidate[];
};

export type StrategyRulesSnapshot = {
  source: string;
  storage_path: string;
  rules: Record<string, unknown>;
};
