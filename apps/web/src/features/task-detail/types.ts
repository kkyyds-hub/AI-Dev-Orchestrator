import type { ConsoleRun, ConsoleTask, TaskBlockingSignal } from "../console/types";

export type TaskContextDependency = {
  task_id: string;
  title: string;
  status: string;
  latest_run_status: string | null;
  latest_run_summary: string | null;
  latest_failure_category: string | null;
  missing: boolean;
};

export type TaskContextRecentRun = {
  run_id: string;
  status: string;
  result_summary: string | null;
  verification_summary: string | null;
  failure_category: string | null;
  created_at: string;
};

export type TaskContextPreview = {
  task_id: string;
  task_title: string;
  input_summary: string;
  acceptance_criteria: string[];
  priority: string;
  risk_level: string;
  human_status: string;
  paused_reason: string | null;
  ready_for_execution: boolean;
  blocking_signals: TaskBlockingSignal[];
  blocking_reasons: string[];
  dependency_items: TaskContextDependency[];
  recent_runs: TaskContextRecentRun[];
  context_summary: string;
};

export type TaskDetail = ConsoleTask & {
  runs: ConsoleRun[];
  context_preview: TaskContextPreview;
};
