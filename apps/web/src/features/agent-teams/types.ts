export type TeamAssemblyMember = {
  role_code: string;
  enabled: boolean;
  display_name: string;
  allocation_percent: number;
  notes: string | null;
};

export type TeamPolicy = {
  collaboration_mode: string;
  intervention_mode: string;
  escalation_enabled: boolean;
  handoff_required: boolean;
  review_gate: string;
};

export type BudgetPolicy = {
  daily_budget_usd: number;
  per_run_budget_usd: number;
  hard_stop_enabled: boolean;
  pressure_mode: string;
};

export type RoleModelPreference = {
  role_code: string;
  model_tier: "economy" | "balanced" | "premium";
};

export type RoleModelStageOverride = {
  stage: string;
  role_code: string;
  model_tier: "economy" | "balanced" | "premium";
};

export type RoleModelPolicy = {
  role_preferences: RoleModelPreference[];
  stage_overrides: RoleModelStageOverride[];
};

export type TeamControlCenterSnapshot = {
  project_id: string;
  team_name: string;
  team_mission: string;
  assembly: TeamAssemblyMember[];
  team_policy: TeamPolicy;
  budget_policy: BudgetPolicy;
  role_model_policy: RoleModelPolicy;
  day14_prerequisites: {
    team_size: number;
    enabled_role_codes: string[];
    budget_policy_keys: string[];
    role_preference_count: number;
    stage_override_count: number;
  };
  runtime_consumption_boundary: {
    role_model_policy_paths: string[];
    budget_policy_paths: string[];
    note: string;
  };
};

export type TeamControlCenterUpdateRequest = {
  team_name: string;
  team_mission: string;
  assembly: TeamAssemblyMember[];
  team_policy: TeamPolicy;
  budget_policy: BudgetPolicy;
  role_model_policy: RoleModelPolicy;
};
