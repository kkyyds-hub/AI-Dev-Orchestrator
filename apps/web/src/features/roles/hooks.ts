import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchProjectRoleCatalog,
  fetchRoleWorkbenchSnapshot,
  fetchSystemRoleCatalog,
  updateProjectRoleConfig,
} from "./api";
import type { ProjectRoleUpdateInput } from "./types";

export function useSystemRoleCatalog() {
  return useQuery({
    queryKey: ["system-role-catalog"],
    queryFn: fetchSystemRoleCatalog,
    staleTime: 60_000,
  });
}

export function useProjectRoleCatalog(projectId: string | null) {
  return useQuery({
    queryKey: ["project-role-catalog", projectId],
    queryFn: () => fetchProjectRoleCatalog(projectId ?? ""),
    enabled: projectId !== null,
  });
}

export function useUpdateProjectRoleConfig(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: { roleCode: string; payload: ProjectRoleUpdateInput }) => {
      if (!projectId) {
        throw new Error("当前没有可编辑角色配置的项目。");
      }

      return updateProjectRoleConfig({
        projectId,
        roleCode: input.roleCode,
        payload: input.payload,
      });
    },
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["system-role-catalog"] }),
        queryClient.invalidateQueries({ queryKey: ["project-role-catalog"] }),
        queryClient.invalidateQueries({
          queryKey: ["project-role-catalog", result.project_id],
        }),
      ]);
    },
  });
}

export function useRoleWorkbenchSnapshot(projectId: string | null) {
  return useQuery({
    queryKey: ["role-workbench", projectId ?? "all"],
    queryFn: () => fetchRoleWorkbenchSnapshot(projectId),
    refetchInterval: 5_000,
  });
}
