import { useQuery } from "@tanstack/react-query";

import { fetchBackendHealth, fetchConsoleOverview } from "./api";

export function useConsoleOverview(options?: { enablePollingFallback?: boolean }) {
  return useQuery({
    queryKey: ["console-overview"],
    queryFn: fetchConsoleOverview,
    refetchInterval: options?.enablePollingFallback === false ? false : 5_000,
  });
}

export function useBackendHealth() {
  return useQuery({
    queryKey: ["backend-health"],
    queryFn: fetchBackendHealth,
    refetchInterval: 10_000,
  });
}
