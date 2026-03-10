export type HealthResponse = {
  status: string;
  service: string;
};

export type ConsoleRun = {
  id: string;
  status: string;
  result_summary: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_cost: number;
  log_path: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type ConsoleTask = {
  id: string;
  title: string;
  status: string;
  priority: string;
  input_summary: string;
  created_at: string;
  updated_at: string;
  latest_run: ConsoleRun | null;
};

export type ConsoleOverview = {
  total_tasks: number;
  pending_tasks: number;
  running_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  blocked_tasks: number;
  total_estimated_cost: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  tasks: ConsoleTask[];
};
