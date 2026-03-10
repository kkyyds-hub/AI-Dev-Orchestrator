export type RunLogEvent = {
  timestamp: string;
  level: string;
  event: string;
  message: string;
  data: Record<string, unknown>;
};

export type RunLogResponse = {
  run_id: string;
  log_path: string | null;
  limit: number;
  truncated: boolean;
  events: RunLogEvent[];
};

export type FailureReview = {
  review_id: string;
  task_id: string;
  task_title: string;
  task_status: string;
  run_id: string;
  run_status: string;
  created_at: string;
  failure_category: string | null;
  quality_gate_passed: boolean | null;
  route_reason: string | null;
  result_summary: string | null;
  log_path: string | null;
  evidence_events: string[];
  action_summary: string;
  conclusion: string;
  storage_path: string | null;
};

export type DecisionTraceItem = {
  timestamp: string;
  stage: string;
  title: string;
  event: string;
  level: string;
  summary: string;
  data: Record<string, unknown>;
};

export type DecisionTraceResponse = {
  run_id: string;
  task_id: string;
  run_status: string;
  failure_category: string | null;
  quality_gate_passed: boolean | null;
  trace_items: DecisionTraceItem[];
  failure_review: FailureReview | null;
};
