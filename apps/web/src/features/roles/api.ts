import { requestJson } from "../../lib/http";
import type {
  ProjectRoleCatalog,
  ProjectRoleConfig,
  ProjectRoleSkillConsumption,
  ProjectRoleUpdateInput,
  RoleWorkbenchSnapshot,
  SystemRoleCatalogItem,
} from "./types";

export function fetchSystemRoleCatalog(): Promise<SystemRoleCatalogItem[]> {
  return requestJson<SystemRoleCatalogItem[]>("/roles/catalog");
}

export function fetchProjectRoleCatalog(
  projectId: string,
): Promise<ProjectRoleCatalog> {
  return requestJson<ProjectRoleCatalog>(`/roles/projects/${projectId}`);
}

export function fetchProjectRoleSkillConsumption(
  projectId: string,
): Promise<ProjectRoleSkillConsumption> {
  return requestJson<ProjectRoleSkillConsumption>(
    `/roles/projects/${projectId}/consumption`,
  );
}

export function updateProjectRoleConfig(input: {
  projectId: string;
  roleCode: string;
  payload: ProjectRoleUpdateInput;
}): Promise<ProjectRoleConfig> {
  return requestJson<ProjectRoleConfig>(
    `/roles/projects/${input.projectId}/${input.roleCode}`,
    {
      method: "PUT",
      body: JSON.stringify(input.payload),
    },
  );
}

export function fetchRoleWorkbenchSnapshot(
  projectId: string | null,
): Promise<RoleWorkbenchSnapshot> {
  const searchParams = new URLSearchParams();
  if (projectId) {
    searchParams.set("project_id", projectId);
  }

  const query = searchParams.toString();
  return requestJson<RoleWorkbenchSnapshot>(
    query ? `/console/role-workbench?${query}` : "/console/role-workbench",
  );
}
