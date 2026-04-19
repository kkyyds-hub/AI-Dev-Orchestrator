import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchTeamControlCenterSnapshot,
  updateTeamControlCenterSnapshot,
} from "./api";
import type { TeamControlCenterUpdateRequest } from "./types";

function teamControlCenterKey(projectId: string | null) {
  return ["team-control-center", projectId] as const;
}

export function useTeamControlCenterSnapshot(projectId: string | null) {
  return useQuery({
    queryKey: teamControlCenterKey(projectId),
    queryFn: () =>
      fetchTeamControlCenterSnapshot({
        projectId: projectId ?? "",
      }),
    enabled: Boolean(projectId),
    staleTime: 5_000,
  });
}

export function useUpdateTeamControlCenterSnapshot(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: TeamControlCenterUpdateRequest) => {
      if (!projectId) {
        throw new Error("No project selected for team control center save.");
      }
      return updateTeamControlCenterSnapshot({
        projectId,
        payload,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: teamControlCenterKey(projectId),
      });
    },
  });
}
