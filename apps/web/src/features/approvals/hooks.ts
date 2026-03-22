import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  applyApprovalAction,
  createApprovalRequest,
  fetchApprovalDetail,
  fetchApprovalHistory,
  fetchProjectApprovalInbox,
  fetchProjectApprovalRetrospective,
} from "./api";
import type {
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

export function useProjectApprovalRetrospective(projectId: string | null) {
  return useQuery({
    queryKey: ["approvals", "retrospective", projectId],
    queryFn: () => fetchProjectApprovalRetrospective(projectId as string),
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

export function useApprovalHistory(approvalId: string | null, open = true) {
  return useQuery({
    queryKey: ["approvals", "history", approvalId],
    queryFn: () => fetchApprovalHistory(approvalId as string),
    enabled: open && Boolean(approvalId),
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
