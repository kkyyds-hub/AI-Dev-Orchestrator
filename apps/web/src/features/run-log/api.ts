import { requestJson } from "../../lib/http";

import type {
  DecisionTraceResponse,
  RunLogResponse,
  VerificationRunFeed,
} from "./types";

export function fetchRunLogs(runId: string, limit = 100): Promise<RunLogResponse> {
  return requestJson<RunLogResponse>(`/runs/${runId}/logs?limit=${limit}`);
}

export function fetchDecisionTrace(runId: string): Promise<DecisionTraceResponse> {
  return requestJson<DecisionTraceResponse>(`/runs/${runId}/decision-trace`);
}

export function fetchProjectVerificationRuns(input: {
  projectId: string;
  changeBatchId?: string | null;
  limit?: number;
}): Promise<VerificationRunFeed> {
  const searchParams = new URLSearchParams();
  if (input.changeBatchId) {
    searchParams.set("change_batch_id", input.changeBatchId);
  }
  if (input.limit) {
    searchParams.set("limit", String(input.limit));
  }

  const query = searchParams.toString();
  return requestJson<VerificationRunFeed>(
    `/runs/verification/projects/${input.projectId}${query ? `?${query}` : ""}`,
  );
}
