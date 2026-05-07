import type {
  ProjectRoleCatalog,
  ProjectRoleConfig,
  SystemRoleCatalogItem,
} from "../types";

export type RoleCatalogDisplayRole = {
  key: string;
  projectRole: ProjectRoleConfig | null;
  systemRole: SystemRoleCatalogItem | null;
};

export function getDisabledRoleCount(
  projectCatalog: ProjectRoleCatalog | undefined,
  systemRoles: SystemRoleCatalogItem[],
) {
  if (!projectCatalog) {
    return systemRoles.filter((role) => !role.enabled_by_default).length;
  }

  return projectCatalog.available_role_count - projectCatalog.enabled_role_count;
}

export function buildRoleCatalogDisplayRoles(input: {
  selectedProjectId: string | null;
  projectRoles: ProjectRoleConfig[];
  systemRoles: SystemRoleCatalogItem[];
}): RoleCatalogDisplayRole[] {
  if (!input.selectedProjectId) {
    return input.systemRoles.map((systemRole) => ({
      key: systemRole.code,
      projectRole: null,
      systemRole,
    }));
  }

  return input.projectRoles.map((projectRole) => ({
    key: projectRole.id,
    projectRole,
    systemRole:
      input.systemRoles.find((item) => item.code === projectRole.role_code) ?? null,
  }));
}
