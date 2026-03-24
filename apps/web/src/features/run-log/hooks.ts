import { useQuery } from "@tanstack/react-query";

import {
  fetchDecisionTrace,
  fetchProjectVerificationRuns,
  fetchRunLogs,
} from "./api";

export function useRunLogs(runId: string | null, limit = 100) {
  return useQuery({
    queryKey: ["run-logs", runId, limit],
    queryFn: () => fetchRunLogs(runId as string, limit),
    enabled: Boolean(runId),
  });
}

export function useDecisionTrace(runId: string | null) {
  return useQuery({
    queryKey: ["decision-trace", runId],
    queryFn: () => fetchDecisionTrace(runId as string),
    enabled: Boolean(runId),
  });
}

export function useProjectVerificationRuns(
  projectId: string | null,
  changeBatchId: string | null = null,
  limit = 10,
) {
  return useQuery({
    queryKey: ["project-verification-runs", projectId, changeBatchId, limit],
    queryFn: () =>
      fetchProjectVerificationRuns({
        projectId: projectId as string,
        changeBatchId,
        limit,
      }),
    enabled: Boolean(projectId),
  });
}
