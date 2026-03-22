import { requestJson } from "../../lib/http";
import type {
  DeliverableDetail,
  ProjectDeliverableSnapshot,
  TaskRelatedDeliverable,
  DeliverableVersionDiff,
} from "./types";

export function fetchProjectDeliverableSnapshot(
  projectId: string,
): Promise<ProjectDeliverableSnapshot> {
  return requestJson<ProjectDeliverableSnapshot>(`/deliverables/projects/${projectId}`);
}

export function fetchDeliverableDetail(
  deliverableId: string,
): Promise<DeliverableDetail> {
  return requestJson<DeliverableDetail>(`/deliverables/${deliverableId}`);
}

export function fetchDeliverableVersionDiff(input: {
  deliverableId: string;
  baseVersion: number;
  targetVersion: number;
}): Promise<DeliverableVersionDiff> {
  const searchParams = new URLSearchParams({
    base_version: String(input.baseVersion),
    target_version: String(input.targetVersion),
  });
  return requestJson<DeliverableVersionDiff>(
    `/deliverables/${input.deliverableId}/compare?${searchParams.toString()}`,
  );
}

export function fetchTaskRelatedDeliverables(
  taskId: string,
): Promise<TaskRelatedDeliverable[]> {
  return requestJson<TaskRelatedDeliverable[]>(`/deliverables/tasks/${taskId}`);
}
