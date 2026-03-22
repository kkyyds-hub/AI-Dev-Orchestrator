import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  captureProjectChangeSession,
  fetchProjectChangeSession,
  fetchProjectRepositorySnapshot,
  refreshProjectRepositorySnapshot,
} from "./api";

export function useProjectRepositorySnapshot(projectId: string | null) {
  return useQuery({
    queryKey: ["repository-snapshot", projectId],
    queryFn: () => fetchProjectRepositorySnapshot(projectId ?? ""),
    enabled: projectId !== null,
  });
}

export function useRefreshProjectRepositorySnapshot(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      if (!projectId) {
        throw new Error("当前没有可刷新的项目仓库。");
      }

      return refreshProjectRepositorySnapshot(projectId);
    },
    onSuccess: async (snapshot) => {
      queryClient.setQueryData(["repository-snapshot", snapshot.project_id], snapshot);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["project-detail", snapshot.project_id] }),
        queryClient.invalidateQueries({ queryKey: ["repository-snapshot", snapshot.project_id] }),
      ]);
    },
  });
}

export function useProjectChangeSession(projectId: string | null) {
  return useQuery({
    queryKey: ["change-session", projectId],
    queryFn: () => fetchProjectChangeSession(projectId ?? ""),
    enabled: projectId !== null,
    retry: false,
  });
}

export function useCaptureProjectChangeSession(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      if (!projectId) {
        throw new Error("当前没有可记录变更会话的项目仓库。");
      }

      return captureProjectChangeSession(projectId);
    },
    onSuccess: async (changeSession) => {
      queryClient.setQueryData(
        ["change-session", changeSession.project_id],
        changeSession,
      );
      await queryClient.invalidateQueries({
        queryKey: ["change-session", changeSession.project_id],
      });
    },
  });
}
