import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchProjectStrategyPreview,
  fetchStrategyRules,
  updateStrategyRules,
} from "./api";

export function useProjectStrategyPreview(projectId: string | null) {
  return useQuery({
    queryKey: ["strategy-preview", projectId],
    queryFn: () => fetchProjectStrategyPreview(projectId as string),
    enabled: Boolean(projectId),
    refetchInterval: 5_000,
  });
}

export function useStrategyRules() {
  return useQuery({
    queryKey: ["strategy-rules"],
    queryFn: fetchStrategyRules,
    staleTime: 30_000,
  });
}

export function useUpdateStrategyRules(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateStrategyRules,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["strategy-rules"] }),
        queryClient.invalidateQueries({ queryKey: ["strategy-preview"] }),
        ...(projectId
          ? [
              queryClient.invalidateQueries({
                queryKey: ["strategy-preview", projectId],
              }),
            ]
          : []),
      ]);
    },
  });
}
