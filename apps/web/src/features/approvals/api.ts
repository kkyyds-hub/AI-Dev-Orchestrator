import { requestJson } from "../../lib/http";

import type {
  ApprovalDetail,
  ApprovalHistory,
  ApplyRepositoryPreflightActionInput,
  ApplyRepositoryReleaseGateActionInput,
  ApplyApprovalActionInput,
  CreateApprovalRequestInput,
  ProjectRepositoryReleaseGateInbox,
  ProjectRepositoryPreflightInbox,
  ProjectApprovalInbox,
  ProjectApprovalRetrospective,
  ProjectChangeRework,
  RepositoryReleaseGateDetail,
  RepositoryPreflightApprovalDetail,
} from "./types";

export function fetchProjectApprovalInbox(
  projectId: string,
): Promise<ProjectApprovalInbox> {
  return requestJson<ProjectApprovalInbox>(`/approvals/projects/${projectId}`);
}

export function fetchProjectRepositoryPreflightInbox(
  projectId: string,
): Promise<ProjectRepositoryPreflightInbox> {
  return requestJson<ProjectRepositoryPreflightInbox>(
    `/approvals/projects/${projectId}/repository-preflight`,
  );
}

export function fetchProjectRepositoryReleaseGateInbox(
  projectId: string,
): Promise<ProjectRepositoryReleaseGateInbox> {
  return requestJson<ProjectRepositoryReleaseGateInbox>(
    `/approvals/projects/${projectId}/repository-release-gate`,
  );
}

export function fetchProjectApprovalRetrospective(
  projectId: string,
): Promise<ProjectApprovalRetrospective> {
  return requestJson<ProjectApprovalRetrospective>(
    `/approvals/projects/${projectId}/retrospective`,
  );
}

export function fetchProjectChangeRework(
  projectId: string,
): Promise<ProjectChangeRework> {
  return requestJson<ProjectChangeRework>(
    `/approvals/projects/${projectId}/change-rework`,
  );
}

export function fetchApprovalDetail(approvalId: string): Promise<ApprovalDetail> {
  return requestJson<ApprovalDetail>(`/approvals/${approvalId}`);
}

export function fetchRepositoryPreflightDetail(
  changeBatchId: string,
): Promise<RepositoryPreflightApprovalDetail> {
  return requestJson<RepositoryPreflightApprovalDetail>(
    `/approvals/repository-preflight/${changeBatchId}`,
  );
}

export function fetchApprovalHistory(approvalId: string): Promise<ApprovalHistory> {
  return requestJson<ApprovalHistory>(`/approvals/${approvalId}/history`);
}

export function fetchRepositoryReleaseGateDetail(
  changeBatchId: string,
): Promise<RepositoryReleaseGateDetail> {
  return requestJson<RepositoryReleaseGateDetail>(
    `/approvals/repository-release-gate/${changeBatchId}`,
  );
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

export function applyRepositoryPreflightAction(
  changeBatchId: string,
  input: ApplyRepositoryPreflightActionInput,
): Promise<RepositoryPreflightApprovalDetail> {
  return requestJson<RepositoryPreflightApprovalDetail>(
    `/approvals/repository-preflight/${changeBatchId}/actions`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function applyRepositoryReleaseGateAction(
  changeBatchId: string,
  input: ApplyRepositoryReleaseGateActionInput,
): Promise<RepositoryReleaseGateDetail> {
  return requestJson<RepositoryReleaseGateDetail>(
    `/approvals/repository-release-gate/${changeBatchId}/actions`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}
