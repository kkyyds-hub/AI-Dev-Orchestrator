import { requestJson } from "../../lib/http";
import type {
  ChangeEvidencePackage,
  DeliverableDetail,
  DeliverableVersionDiff,
  ProjectDeliverableSnapshot,
  TaskRelatedDeliverable,
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

export function fetchProjectChangeEvidence(
  projectId: string,
  changeBatchId?: string | null,
): Promise<ChangeEvidencePackage> {
  const searchParams = new URLSearchParams();
  if (changeBatchId) {
    searchParams.set("change_batch_id", changeBatchId);
  }

  const suffix = searchParams.size > 0 ? `?${searchParams.toString()}` : "";
  return requestJson<ChangeEvidencePackage>(
    `/deliverables/projects/${projectId}/change-evidence${suffix}`,
  );
}

export function fetchDeliverableChangeEvidence(
  deliverableId: string,
): Promise<ChangeEvidencePackage> {
  return requestJson<ChangeEvidencePackage>(
    `/deliverables/${deliverableId}/change-evidence`,
  );
}

export function fetchApprovalChangeEvidence(
  approvalId: string,
): Promise<ChangeEvidencePackage> {
  return requestJson<ChangeEvidencePackage>(
    `/deliverables/approvals/${approvalId}/change-evidence`,
  );
}
