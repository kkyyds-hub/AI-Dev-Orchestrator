import { requestJson } from "../../lib/http";

import type { DecisionHistoryItem, ReviewCluster } from "./types";

export function fetchTaskDecisionHistory(taskId: string): Promise<DecisionHistoryItem[]> {
  return requestJson<DecisionHistoryItem[]>(`/tasks/${taskId}/decision-history`);
}

export function fetchReviewClusters(): Promise<ReviewCluster[]> {
  return requestJson<ReviewCluster[]>("/console/review-clusters");
}
