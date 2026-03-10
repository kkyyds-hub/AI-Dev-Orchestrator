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
  result_summary: string | null;
  context_summary: string | null;
  task_id: string | null;
  task_title: string | null;
  task_status: string | null;
  run_id: string | null;
  run_status: string | null;
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
