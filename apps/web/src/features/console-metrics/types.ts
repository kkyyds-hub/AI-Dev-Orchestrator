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
