import { requestJson } from "../../lib/http";

import type { RunLogResponse } from "./types";

export function fetchRunLogs(runId: string, limit = 100): Promise<RunLogResponse> {
  return requestJson<RunLogResponse>(`/runs/${runId}/logs?limit=${limit}`);
}
