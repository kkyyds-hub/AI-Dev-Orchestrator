import { useQuery } from "@tanstack/react-query";

import { fetchReviewClusters, fetchTaskDecisionHistory } from "./decision-api";

export function useTaskDecisionHistory(taskId: string | null) {
  return useQuery({
    queryKey: ["task-decision-history", taskId],
    queryFn: () => fetchTaskDecisionHistory(taskId as string),
    enabled: Boolean(taskId),
    refetchInterval: taskId ? 10_000 : false,
  });
}

export function useReviewClusters() {
  return useQuery({
    queryKey: ["review-clusters"],
    queryFn: fetchReviewClusters,
    refetchInterval: 10_000,
  });
}
