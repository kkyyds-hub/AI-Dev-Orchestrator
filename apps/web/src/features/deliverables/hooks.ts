import { useQuery } from "@tanstack/react-query";

import {
  fetchDeliverableDetail,
  fetchProjectDeliverableSnapshot,
  fetchTaskRelatedDeliverables,
  fetchDeliverableVersionDiff,
} from "./api";

export function useProjectDeliverableSnapshot(projectId: string | null) {
  return useQuery({
    queryKey: ["deliverables", "project", projectId],
    queryFn: () => fetchProjectDeliverableSnapshot(projectId as string),
    enabled: Boolean(projectId),
  });
}

export function useDeliverableDetail(deliverableId: string | null) {
  return useQuery({
    queryKey: ["deliverables", "detail", deliverableId],
    queryFn: () => fetchDeliverableDetail(deliverableId as string),
    enabled: Boolean(deliverableId),
  });
}

export function useTaskRelatedDeliverables(taskId: string | null) {
  return useQuery({
    queryKey: ["deliverables", "task-related", taskId],
    queryFn: () => fetchTaskRelatedDeliverables(taskId as string),
    enabled: Boolean(taskId),
  });
}

export function useDeliverableVersionDiff(input: {
  deliverableId: string | null;
  baseVersion: number | null;
  targetVersion: number | null;
}) {
  return useQuery({
    queryKey: [
      "deliverables",
      "diff",
      input.deliverableId,
      input.baseVersion,
      input.targetVersion,
    ],
    queryFn: () =>
      fetchDeliverableVersionDiff({
        deliverableId: input.deliverableId as string,
        baseVersion: input.baseVersion as number,
        targetVersion: input.targetVersion as number,
      }),
    enabled:
      Boolean(input.deliverableId) &&
      input.baseVersion !== null &&
      input.targetVersion !== null,
  });
}
