import { requestJson } from "../../../lib/http";

export type WorkbenchTask = {
  id: string;
  project_id: string | null;
  title: string;
  status: string;
  priority: string;
  input_summary: string;
  acceptance_criteria: string[];
  depends_on_task_ids: string[];
  risk_level: string;
  owner_role_code: string | null;
  human_status: string;
  paused_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkbenchTaskRun = {
  id: string;
  status: string;
  result_summary: string | null;
  owner_role_code: string | null;
  dispatch_status: string | null;
  failure_category: string | null;
  quality_gate_passed: boolean | null;
  verification_summary: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type WorkbenchRunLogEvent = {
  timestamp: string;
  level: string;
  event: string;
  message: string;
  data: Record<string, unknown>;
};

export type WorkbenchRunLog = {
  run_id: string;
  limit: number;
  truncated: boolean;
  events: WorkbenchRunLogEvent[];
};

export function fetchWorkbenchTasks(): Promise<WorkbenchTask[]> {
  return requestJson<WorkbenchTask[]>("/tasks");
}

export function fetchWorkbenchTask(taskId: string): Promise<WorkbenchTask> {
  return requestJson<WorkbenchTask>(`/tasks/${taskId}`);
}

export function fetchWorkbenchTaskRuns(
  taskId: string,
): Promise<WorkbenchTaskRun[]> {
  return requestJson<WorkbenchTaskRun[]>(`/tasks/${taskId}/runs`);
}

export function fetchWorkbenchRunLogs(runId: string): Promise<WorkbenchRunLog> {
  return requestJson<WorkbenchRunLog>(`/runs/${runId}/logs?limit=20`);
}
