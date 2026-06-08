export interface GitWriteChangedFileInput {
  path: string;
  change_type: string;
  additions: number;
  deletions: number;
  reviewed: boolean;
  safe_summary: string | null;
}

export interface GitWriteCreateIntentRequest {
  intent_id?: string;
  workspace_id: string;
  repository_id?: string;
  project_id?: string;
  task_id?: string;
  run_id?: string;
  requested_by?: string;
  target_branch: string;
  base_branch?: string;
  file_paths: string[];
  changed_files: GitWriteChangedFileInput[];
  allowed_branches: string[];
  feature_flag_enabled: boolean;
  diff_summary?: string;
  commit_message?: string;
  force_push_requested: boolean;
  destructive_operation_requested: boolean;
  ci_trigger_requested: boolean;
}

export interface GitWriteIntentReadback {
  intent_id: string;
  workspace_id: string;
  repository_id: string | null;
  project_id: string | null;
  task_id: string | null;
  run_id: string | null;
  requested_by: string | null;
  target_branch: string;
  base_branch: string | null;
  file_paths: string[];
  commit_message: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface GitWriteSafetyGateReadback {
  gate_name: string;
  status: string;
  passed: boolean;
  block_reason: string | null;
  safe_summary: string | null;
  checked_at: string | null;
}

export interface GitWriteSafetySnapshotReadback {
  gate_checks: GitWriteSafetyGateReadback[];
  all_passed: boolean;
  preview_gates_passed: boolean;
  blocking_reasons: string[];
  evaluated_at: string;
}

export interface GitWritePreviewFileReadback {
  path: string;
  change_type: string;
  additions: number;
  deletions: number;
  reviewed: boolean;
  contains_secret: boolean;
  safe_summary: string | null;
}

export interface GitWriteRollbackPlanReadback {
  plan_id: string;
  summary: string;
  restore_branch_hint: string | null;
  restore_commit_hint: string | null;
  generated_at: string;
}

export interface GitWritePreviewReadback {
  preview_id: string;
  intent_id: string;
  status: string;
  target_branch: string;
  files: GitWritePreviewFileReadback[];
  diff_summary: string | null;
  commit_message_preview: string | null;
  rollback_plan: GitWriteRollbackPlanReadback | null;
  safety_snapshot: GitWriteSafetySnapshotReadback;
  created_at: string;
}

export interface GitWriteOneShotTokenReadback {
  token_id: string;
  token_hint: string;
  status: string;
  expires_at: string;
}

export interface GitWriteApprovalReadback {
  approval_id: string;
  intent_id: string;
  preview_id: string;
  decision: string;
  decided_by: string | null;
  decided_at: string | null;
  approval_note: string | null;
  one_shot_token: GitWriteOneShotTokenReadback;
}

export interface GitWriteAuditEventReadback {
  event_id: string;
  intent_id: string;
  event_type: string;
  timestamp: string;
  safe_summary: string;
  append_only: boolean;
  metadata_count: number;
}

export interface GitWriteReadbackRecord {
  intent: GitWriteIntentReadback;
  preview: GitWritePreviewReadback;
  rollback_plan: GitWriteRollbackPlanReadback | null;
  approval: GitWriteApprovalReadback | null;
  approval_summary: string | null;
  audit_events?: GitWriteAuditEventReadback[];
  product_runtime_git_write_executed: boolean;
}

export interface GitWriteApprovalRequest {
  actor: string;
  approval_note?: string;
}
