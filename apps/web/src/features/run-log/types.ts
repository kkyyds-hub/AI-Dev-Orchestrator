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
