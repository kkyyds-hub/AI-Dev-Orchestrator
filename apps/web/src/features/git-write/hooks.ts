import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createGitWriteIntent,
  getGitWriteIntent,
  listGitWriteAuditEvents,
  recordGitWriteApproval,
} from "./api";
import type { GitWriteApprovalRequest } from "./types";

export function useGitWriteIntentReadback(intentId: string | null) {
  return useQuery({
    queryKey: ["git-write", "intent", intentId],
    queryFn: () => getGitWriteIntent(intentId as string),
    enabled: Boolean(intentId),
    retry: false,
  });
}

export function useGitWriteAuditReadback(intentId: string | null) {
  return useQuery({
    queryKey: ["git-write", "audit", intentId],
    queryFn: () => listGitWriteAuditEvents(intentId as string),
    enabled: Boolean(intentId),
    retry: false,
  });
}

export function useCreateGitWriteIntentReadback() {
  return useMutation({
    mutationFn: () => createGitWriteIntent(),
  });
}

export function useRecordGitWriteApprovalReadback(intentId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: GitWriteApprovalRequest) =>
      recordGitWriteApproval(intentId as string, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["git-write", "intent", intentId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["git-write", "audit", intentId],
        }),
      ]);
    },
  });
}
