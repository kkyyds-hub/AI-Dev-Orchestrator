export type SystemRoleCatalogItem = {
  code: string;
  name: string;
  summary: string;
  responsibilities: string[];
  input_boundary: string[];
  output_boundary: string[];
  default_skill_slots: string[];
  enabled_by_default: boolean;
  sort_order: number;
};

export type ProjectRoleConfig = {
  id: string;
  project_id: string;
  role_code: string;
  enabled: boolean;
  name: string;
  summary: string;
  responsibilities: string[];
  input_boundary: string[];
  output_boundary: string[];
  default_skill_slots: string[];
  custom_notes: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

export type ProjectRoleCatalog = {
  project_id: string;
  available_role_count: number;
  enabled_role_count: number;
  roles: ProjectRoleConfig[];
};

export type ProjectRoleUpdateInput = {
  enabled: boolean;
  name: string;
  summary: string;
  responsibilities: string[];
  input_boundary: string[];
  output_boundary: string[];
  default_skill_slots: string[];
  custom_notes: string | null;
  sort_order: number;
};

export type RoleWorkbenchTaskItem = {
  task_id: string;
  project_id: string | null;
  project_name: string | null;
  title: string;
  status: string;
  priority: string;
  risk_level: string;
  human_status: string;
  input_summary: string;
  owner_role_code: string | null;
  upstream_role_code: string | null;
  downstream_role_code: string | null;
  created_at: string;
  updated_at: string;
  latest_run_id: string | null;
  latest_run_status: string | null;
  latest_run_summary: string | null;
  latest_run_log_path: string | null;
};

export type RoleWorkbenchHandoffItem = {
  id: string;
  timestamp: string;
  project_id: string | null;
  project_name: string | null;
  task_id: string;
  task_title: string;
  run_id: string | null;
  run_status: string | null;
  owner_role_code: string | null;
  upstream_role_code: string | null;
  downstream_role_code: string | null;
  dispatch_status: string | null;
  handoff_reason: string | null;
  message: string;
  log_path: string | null;
};

export type RoleWorkbenchLane = {
  role_code: string;
  role_name: string;
  role_summary: string;
  enabled: boolean;
  current_task_count: number;
  blocked_task_count: number;
  running_task_count: number;
  recent_handoff_count: number;
  current_tasks: RoleWorkbenchTaskItem[];
  blocked_tasks: RoleWorkbenchTaskItem[];
  running_tasks: RoleWorkbenchTaskItem[];
  recent_handoffs: RoleWorkbenchHandoffItem[];
};

export type RoleWorkbenchSnapshot = {
  project_id: string | null;
  project_name: string | null;
  project_status: string | null;
  project_stage: string | null;
  scope_label: string;
  total_roles: number;
  enabled_roles: number;
  total_tasks: number;
  active_tasks: number;
  running_tasks: number;
  blocked_tasks: number;
  unassigned_tasks: number;
  recent_handoff_count: number;
  budget: {
    strategy_label: string;
    pressure_level: string;
    daily_usage_ratio: number;
    session_usage_ratio: number;
  };
  lanes: RoleWorkbenchLane[];
  recent_handoffs: RoleWorkbenchHandoffItem[];
  generated_at: string;
};

export const ROLE_CODE_LABELS: Record<string, string> = {
  product_manager: "产品经理",
  architect: "架构师",
  engineer: "工程师",
  reviewer: "评审者",
};
