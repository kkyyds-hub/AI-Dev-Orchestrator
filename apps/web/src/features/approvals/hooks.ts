import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  applyApprovalAction,
  applyRepositoryPreflightAction,
  applyRepositoryReleaseGateAction,
  createApprovalRequest,
  fetchApprovalDetail,
  fetchApprovalHistory,
  fetchProjectChangeRework,
  fetchProjectApprovalInbox,
  fetchProjectRepositoryPreflightInbox,
  fetchProjectRepositoryReleaseGateInbox,
  fetchProjectApprovalRetrospective,
  fetchRepositoryReleaseGateDetail,
  fetchRepositoryPreflightDetail,
} from "./api";
import type {
  ApplyRepositoryPreflightActionInput,
  ApplyRepositoryReleaseGateActionInput,
  ApplyApprovalActionInput,
  CreateApprovalRequestInput,
} from "./types";

export function useProjectApprovalInbox(projectId: string | null) {
  return useQuery({
    queryKey: ["approvals", "project", projectId],
    queryFn: () => fetchProjectApprovalInbox(projectId as string),
    enabled: Boolean(projectId),
  });
}

export function useProjectRepositoryPreflightInbox(projectId: string | null) {
  return useQuery({
    queryKey: ["approvals", "repository-preflight", projectId],
    queryFn: () => fetchProjectRepositoryPreflightInbox(projectId as string),
    enabled: Boolean(projectId),
  });
}

export function useProjectRepositoryReleaseGateInbox(projectId: string | null) {
  return useQuery({
    queryKey: ["approvals", "repository-release-gate", projectId],
    queryFn: () => fetchProjectRepositoryReleaseGateInbox(projectId as string),
    enabled: Boolean(projectId),
  });
}

export function useProjectApprovalRetrospective(projectId: string | null) {
  return useQuery({
    queryKey: ["approvals", "retrospective", projectId],
    queryFn: () => fetchProjectApprovalRetrospective(projectId as string),
    enabled: Boolean(projectId),
  });
}

export function useProjectChangeRework(projectId: string | null) {
  return useQuery({
    queryKey: ["approvals", "change-rework", projectId],
    queryFn: () => fetchProjectChangeRework(projectId as string),
    enabled: Boolean(projectId),
  });
}

export function useApprovalDetail(approvalId: string | null, open = true) {
  return useQuery({
    queryKey: ["approvals", "detail", approvalId],
    queryFn: () => fetchApprovalDetail(approvalId as string),
    enabled: open && Boolean(approvalId),
  });
}

export function useRepositoryPreflightDetail(
  changeBatchId: string | null,
  open = true,
) {
  return useQuery({
    queryKey: ["approvals", "repository-preflight-detail", changeBatchId],
    queryFn: () => fetchRepositoryPreflightDetail(changeBatchId as string),
    enabled: open && Boolean(changeBatchId),
  });
}

export function useApprovalHistory(approvalId: string | null, open = true) {
  return useQuery({
    queryKey: ["approvals", "history", approvalId],
    queryFn: () => fetchApprovalHistory(approvalId as string),
    enabled: open && Boolean(approvalId),
  });
}

export function useRepositoryReleaseGateDetail(
  changeBatchId: string | null,
  open = true,
) {
  return useQuery({
    queryKey: ["approvals", "repository-release-gate-detail", changeBatchId],
    queryFn: () => fetchRepositoryReleaseGateDetail(changeBatchId as string),
    enabled: open && Boolean(changeBatchId),
  });
}

export function useCreateApprovalRequest(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CreateApprovalRequestInput) => createApprovalRequest(input),
    onSuccess: async (detail) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["approvals", "project", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["approvals", "detail", detail.id] }),
        queryClient.invalidateQueries({ queryKey: ["approvals", "history"] }),
        queryClient.invalidateQueries({ queryKey: ["approvals", "retrospective", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["boss-project-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["project-timeline", projectId] }),
        ...(projectId
          ? [
              queryClient.invalidateQueries({
                queryKey: ["project-detail", projectId],
              }),
            ]
          : []),
      ]);
    },
  });
}

export function useApplyApprovalAction(
  projectId: string | null,
  approvalId: string | null,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: ApplyApprovalActionInput) => {
      if (!approvalId) {
        throw new Error("当前没有可处理的审批项。");
      }

      return applyApprovalAction(approvalId, input);
    },
    onSuccess: async (detail) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["approvals", "project", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["approvals", "detail", detail.id] }),
        queryClient.invalidateQueries({ queryKey: ["approvals", "history"] }),
        queryClient.invalidateQueries({ queryKey: ["approvals", "retrospective", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["boss-project-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["project-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["project-timeline", projectId] }),
        ...(projectId
          ? [
              queryClient.invalidateQueries({
                queryKey: ["project-detail", projectId],
              }),
            ]
          : []),
      ]);
    },
  });
}

export function useApplyRepositoryPreflightAction(
  projectId: string | null,
  changeBatchId: string | null,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: ApplyRepositoryPreflightActionInput) => {
      if (!changeBatchId) {
        throw new Error("当前没有待处理的执行前预检。");
      }

      return applyRepositoryPreflightAction(changeBatchId, input);
    },
    onSuccess: async (detail) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["approvals", "repository-preflight", projectId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["approvals", "repository-preflight-detail", detail.change_batch_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["project-change-batches", detail.project_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["change-batch-detail", detail.change_batch_id],
        }),
        queryClient.invalidateQueries({ queryKey: ["project-detail", detail.project_id] }),
        queryClient.invalidateQueries({ queryKey: ["project-timeline", detail.project_id] }),
        ...(projectId
          ? [
              queryClient.invalidateQueries({
                queryKey: ["project-detail", projectId],
              }),
            ]
          : []),
      ]);
    },
  });
}

export function useApplyRepositoryReleaseGateAction(
  projectId: string | null,
  changeBatchId: string | null,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: ApplyRepositoryReleaseGateActionInput) => {
      if (!changeBatchId) {
        throw new Error("当前没有待处理的放行检查单。");
      }

      return applyRepositoryReleaseGateAction(changeBatchId, input);
    },
    onSuccess: async (detail) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["approvals", "repository-release-gate", detail.project_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["approvals", "repository-release-gate-detail", detail.change_batch_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["repositories", "release-gates", detail.project_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["repositories", "release-checklist", detail.change_batch_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["project-change-batches", detail.project_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["project-commit-candidates", detail.project_id],
        }),
        ...(projectId
          ? [
              queryClient.invalidateQueries({
                queryKey: ["project-detail", projectId],
              }),
            ]
          : []),
      ]);
    },
  });
}
