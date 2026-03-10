import { requestJson } from "../../lib/http";

import type { DecisionTraceResponse, RunLogResponse } from "./types";

export function fetchRunLogs(runId: string, limit = 100): Promise<RunLogResponse> {
  return requestJson<RunLogResponse>(`/runs/${runId}/logs?limit=${limit}`);
}

export function fetchDecisionTrace(runId: string): Promise<DecisionTraceResponse> {
  return requestJson<DecisionTraceResponse>(`/runs/${runId}/decision-trace`);
}
