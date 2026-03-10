import { useQuery } from "@tanstack/react-query";

import { fetchTaskDetail } from "./api";

export function useTaskDetail(
  taskId: string | null,
  options?: { enablePollingFallback?: boolean },
) {
  return useQuery({
    queryKey: ["task-detail", taskId],
    queryFn: () => fetchTaskDetail(taskId as string),
    enabled: Boolean(taskId),
    refetchInterval:
      taskId && options?.enablePollingFallback !== false ? 5_000 : false,
  });
}
