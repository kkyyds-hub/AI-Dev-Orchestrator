export type MemoryGovernanceState = {
  project_id: string;
  generated_at: string;
  checkpoint_count: number;
  latest_checkpoint_id: string | null;
  latest_task_id: string | null;
  latest_run_id: string | null;
  latest_pressure_level: string | null;
  latest_usage_ratio: number | null;
  latest_bad_context_detected: boolean;
  latest_bad_context_reasons: string[];
  latest_rolling_summary: string | null;
  latest_compaction_applied: boolean;
  latest_compaction_reduction_ratio: number | null;
  latest_compaction_reason_codes: string[];
  latest_rehydrate_at: string | null;
  latest_rehydrate_used_checkpoint_id: string | null;
  latest_compacted_at: string | null;
  latest_reset_at: string | null;
  storage_path: string | null;
};

export type MemoryGovernanceRehydrateResult = {
  project_id: string;
  task_id: string | null;
  used_checkpoint_id: string | null;
  rehydrated_context_summary: string;
  rehydrated: boolean;
  generated_at: string;
};

export type MemoryGovernanceCompactResult = {
  project_id: string;
  checkpoint_id: string | null;
  compacted_summary: string;
  compacted_char_count: number;
  reduction_ratio: number;
  reason_codes: string[];
  created_at: string;
};

export type MemoryGovernanceResetResult = {
  project_id: string;
  reset_performed: boolean;
  generated_at: string;
};

export type MemoryGovernanceRunOnceEcho = {
  claimed: boolean;
  message: string;
  memory_governance_checkpoint_id: string | null;
  memory_governance_rolling_summary: string | null;
  memory_governance_bad_context_detected: boolean | null;
  memory_governance_bad_context_reasons: string[];
  memory_governance_pressure_level: string | null;
  memory_governance_usage_ratio: number | null;
  memory_governance_compaction_applied: boolean | null;
  memory_governance_compaction_ratio: number | null;
  memory_governance_rehydrated: boolean | null;
  memory_governance_rehydrate_source_checkpoint_id: string | null;
  run_id: string | null;
  task_id: string | null;
};
