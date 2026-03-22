import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchProjectSkillBindings,
  fetchSkillRegistry,
  updateProjectRoleSkillBindings,
  upsertSkill,
} from "./api";
import type {
  ProjectRoleSkillBindingUpdateInput,
  SkillUpsertInput,
} from "./types";

export function useSkillRegistry() {
  return useQuery({
    queryKey: ["skill-registry"],
    queryFn: fetchSkillRegistry,
    staleTime: 60_000,
  });
}

export function useUpsertSkill() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: { skillCode: string; payload: SkillUpsertInput }) =>
      upsertSkill(input),
    onSuccess: async (skill) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["skill-registry"] }),
        queryClient.invalidateQueries({ queryKey: ["project-skill-bindings"] }),
        queryClient.invalidateQueries({
          queryKey: ["project-skill-bindings", "all"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["skill-registry", skill.code],
        }),
      ]);
    },
  });
}

export function useProjectSkillBindings(projectId: string | null) {
  return useQuery({
    queryKey: ["project-skill-bindings", projectId ?? "all"],
    queryFn: () => fetchProjectSkillBindings(projectId ?? ""),
    enabled: projectId !== null,
  });
}

export function useUpdateProjectRoleSkillBindings(projectId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: {
      roleCode: string;
      payload: ProjectRoleSkillBindingUpdateInput;
    }) => {
      if (!projectId) {
        throw new Error("当前没有可编辑 Skill 绑定的项目。");
      }

      return updateProjectRoleSkillBindings({
        projectId,
        roleCode: input.roleCode,
        payload: input.payload,
      });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["project-skill-bindings"] }),
        queryClient.invalidateQueries({
          queryKey: ["project-skill-bindings", projectId ?? "all"],
        }),
        queryClient.invalidateQueries({ queryKey: ["skill-registry"] }),
      ]);
    },
  });
}
