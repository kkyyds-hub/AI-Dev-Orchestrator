import { useQuery } from "@tanstack/react-query";

import { fetchProjectCostDashboardSnapshot } from "./api";

function projectCostDashboardQueryKey(projectId: string | null) {
  return ["project-cost-dashboard", projectId] as const;
}

export function useProjectCostDashboardSnapshot(projectId: string | null) {
  return useQuery({
    queryKey: projectCostDashboardQueryKey(projectId),
    queryFn: () => fetchProjectCostDashboardSnapshot(projectId ?? ""),
    enabled: projectId !== null,
    staleTime: 10_000,
  });
}
