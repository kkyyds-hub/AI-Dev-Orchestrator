import { requestJson } from "../../lib/http";
import type {
  ProjectRoleSkillBindingGroup,
  ProjectRoleSkillBindingUpdateInput,
  ProjectSkillBindingSnapshot,
  SkillRegistrySkill,
  SkillRegistrySnapshot,
  SkillUpsertInput,
} from "./types";

export function fetchSkillRegistry(): Promise<SkillRegistrySnapshot> {
  return requestJson<SkillRegistrySnapshot>("/skills/registry");
}

export function upsertSkill(input: {
  skillCode: string;
  payload: SkillUpsertInput;
}): Promise<SkillRegistrySkill> {
  return requestJson<SkillRegistrySkill>(`/skills/${input.skillCode}`, {
    method: "PUT",
    body: JSON.stringify(input.payload),
  });
}

export function fetchProjectSkillBindings(
  projectId: string,
): Promise<ProjectSkillBindingSnapshot> {
  return requestJson<ProjectSkillBindingSnapshot>(
    `/skills/projects/${projectId}/bindings`,
  );
}

export function updateProjectRoleSkillBindings(input: {
  projectId: string;
  roleCode: string;
  payload: ProjectRoleSkillBindingUpdateInput;
}): Promise<ProjectRoleSkillBindingGroup> {
  return requestJson<ProjectRoleSkillBindingGroup>(
    `/skills/projects/${input.projectId}/bindings/${input.roleCode}`,
    {
      method: "PUT",
      body: JSON.stringify(input.payload),
    },
  );
}
