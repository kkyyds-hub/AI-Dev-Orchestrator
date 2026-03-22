import { requestJson } from "../../lib/http";

import type {
  ApprovalDetail,
  ApprovalHistory,
  ApplyApprovalActionInput,
  CreateApprovalRequestInput,
  ProjectApprovalInbox,
  ProjectApprovalRetrospective,
} from "./types";

export function fetchProjectApprovalInbox(
  projectId: string,
): Promise<ProjectApprovalInbox> {
  return requestJson<ProjectApprovalInbox>(`/approvals/projects/${projectId}`);
}

export function fetchProjectApprovalRetrospective(
  projectId: string,
): Promise<ProjectApprovalRetrospective> {
  return requestJson<ProjectApprovalRetrospective>(
    `/approvals/projects/${projectId}/retrospective`,
  );
}

export function fetchApprovalDetail(approvalId: string): Promise<ApprovalDetail> {
  return requestJson<ApprovalDetail>(`/approvals/${approvalId}`);
}

export function fetchApprovalHistory(approvalId: string): Promise<ApprovalHistory> {
  return requestJson<ApprovalHistory>(`/approvals/${approvalId}/history`);
}

export function createApprovalRequest(
  input: CreateApprovalRequestInput,
): Promise<ApprovalDetail> {
  return requestJson<ApprovalDetail>("/approvals", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function applyApprovalAction(
  approvalId: string,
  input: ApplyApprovalActionInput,
): Promise<ApprovalDetail> {
  return requestJson<ApprovalDetail>(`/approvals/${approvalId}/actions`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}
