export interface RealGitWritePilotGateSnapshotSummary {
  total_gates: number;
  passed_gates: number;
  blocked_gates: number;
  pending_gates: number;
  not_applicable_gates: number;
  all_passed: boolean;
  blocking_reasons: string[];
}

export interface RealGitWritePilotDryRunStep {
  step_id: string;
  step_order: number;
  step_kind: string;
  safe_summary: string;
  requires_human_confirmation: boolean;
  produces_repository_side_effect: boolean;
}

export interface RealGitWritePilotDryRunPlan {
  pilot_id: string;
  readiness_ready_for_preview: boolean;
  preview_status: string;
  gate_snapshot_summary: RealGitWritePilotGateSnapshotSummary;
  semantic_steps: RealGitWritePilotDryRunStep[];
  forbidden_operations: string[];
  rollback_plan_summary: string;
  audit_event_summaries: string[];
  dry_run_ready: boolean;
  ready_for_execution: false;
  product_runtime_git_write_executed: false;
  real_executor_started: false;
  created_at: string;
}

export interface RealGitWritePilotApprovalReadbackRequest {
  pilot_id: string;
  dry_run_plan: RealGitWritePilotDryRunPlan;
  approved_by: string;
  approval_phrase: string;
  approved_scope_summary: string;
  requested_at: string;
  expires_at: string;
}

export interface RealGitWritePilotApprovalReadback {
  approval_id: string;
  pilot_id: string;
  decision: string;
  approved_by: string;
  approval_phrase_matched: boolean;
  approved_scope_summary: string;
  dry_run_ready: boolean;
  ready_for_execution: false;
  one_shot_token_issued: false;
  product_runtime_git_write_executed: false;
  real_executor_started: false;
  safe_summary: string;
  audit_event_summaries: string[];
  created_at: string;
  expires_at: string;
}
