import { useQuery } from "@tanstack/react-query";

import { fetchRunLogs } from "./api";

export function useRunLogs(runId: string | null, limit = 100) {
  return useQuery({
    queryKey: ["run-logs", runId, limit],
    queryFn: () => fetchRunLogs(runId as string, limit),
    enabled: Boolean(runId),
  });
}
