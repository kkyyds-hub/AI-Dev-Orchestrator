import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchMemoryGovernanceState,
  runMemoryGovernanceProbe,
  triggerMemoryGovernanceCompact,
  triggerMemoryGovernanceRehydrate,
  triggerMemoryGovernanceReset,
} from "./api";

function governanceStateQueryKey(projectId: string | null) {
  return ["memory-governance", projectId, "state"] as const;
}

export function useMemoryGovernanceState(projectId: string | null) {
  return useQuery({
    queryKey: governanceStateQueryKey(projectId),
    queryFn: () => fetchMemoryGovernanceState(projectId ?? ""),
    enabled: projectId !== null,
    staleTime: 10_000,
  });
}

export function useMemoryGovernanceRehydrate(projectId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input?: { taskId?: string | null }) => {
      if (!projectId) {
        throw new Error("No project selected for memory governance rehydrate.");
      }

      return triggerMemoryGovernanceRehydrate({
        projectId,
        taskId: input?.taskId ?? null,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: governanceStateQueryKey(projectId),
      });
    },
  });
}

export function useMemoryGovernanceCompact(projectId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { targetChars: number }) => {
      if (!projectId) {
        throw new Error("No project selected for memory governance compact.");
      }

      return triggerMemoryGovernanceCompact({
        projectId,
        targetChars: input.targetChars,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: governanceStateQueryKey(projectId),
      });
    },
  });
}

export function useMemoryGovernanceReset(projectId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => {
      if (!projectId) {
        throw new Error("No project selected for memory governance reset.");
      }

      return triggerMemoryGovernanceReset(projectId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: governanceStateQueryKey(projectId),
      });
    },
  });
}

export function useMemoryGovernanceProbe(projectId: string | null) {
  return useMutation({
    mutationFn: () => {
      if (!projectId) {
        throw new Error("No project selected for memory governance probe.");
      }

      return runMemoryGovernanceProbe(projectId);
    },
  });
}
