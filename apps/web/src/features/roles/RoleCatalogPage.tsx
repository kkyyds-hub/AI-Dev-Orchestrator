import { useMemo } from "react";

import { RoleEditorDrawer } from "./RoleEditorDrawer";
import { RoleCatalogGrid } from "./components/RoleCatalogGrid";
import { RoleCatalogHeader } from "./components/RoleCatalogHeader";
import { RoleCatalogLoadingState } from "./components/RoleCatalogLoadingState";
import { RoleCatalogMetricGrid } from "./components/RoleCatalogMetricGrid";
import { RoleCatalogQueryState } from "./components/RoleCatalogQueryState";
import {
  useProjectRoleCatalog,
  useSystemRoleCatalog,
  useUpdateProjectRoleConfig,
} from "./hooks";
import { useRoleCatalogEditor } from "./hooks/useRoleCatalogEditor";
import {
  buildRoleCatalogDisplayRoles,
  getDisabledRoleCount,
} from "./lib/roleCatalogRoles";

type RoleCatalogPageProps = {
  selectedProjectId: string | null;
  selectedProjectName: string | null;
};

export function RoleCatalogPage(props: RoleCatalogPageProps) {
  const systemRoleQuery = useSystemRoleCatalog();
  const projectRoleQuery = useProjectRoleCatalog(props.selectedProjectId);
  const updateRoleMutation = useUpdateProjectRoleConfig(props.selectedProjectId);

  const systemRoles = systemRoleQuery.data ?? [];
  const projectRoles = projectRoleQuery.data?.roles ?? [];

  const disabledRoleCount = useMemo(
    () => getDisabledRoleCount(projectRoleQuery.data, systemRoles),
    [projectRoleQuery.data, systemRoles],
  );
  const displayRoles = useMemo(
    () =>
      buildRoleCatalogDisplayRoles({
        selectedProjectId: props.selectedProjectId,
        projectRoles,
        systemRoles,
      }),
    [projectRoles, props.selectedProjectId, systemRoles],
  );

  const roleEditor = useRoleCatalogEditor({
    projectRoles,
    systemRoles,
    onSaveRole: async (roleCode, payload) => {
      await updateRoleMutation.mutateAsync({
        roleCode,
        payload,
      });
    },
  });

  return (
    <section className="space-y-6">
      <RoleCatalogHeader
        selectedProjectName={props.selectedProjectName}
        projectRoleConnected={projectRoleQuery.data !== undefined}
      />

      <RoleCatalogMetricGrid
        systemRoleCount={systemRoles.length}
        enabledRoleCount={projectRoleQuery.data?.enabled_role_count ?? 0}
        disabledRoleCount={disabledRoleCount}
        selectedProjectName={props.selectedProjectName}
      />

      <RoleCatalogQueryState
        selectedProjectId={props.selectedProjectId}
        systemRoleErrorMessage={
          systemRoleQuery.isError ? systemRoleQuery.error.message : undefined
        }
        projectRoleErrorMessage={
          projectRoleQuery.isError ? projectRoleQuery.error.message : undefined
        }
      />

      <RoleCatalogGrid
        roles={displayRoles}
        projectSelected={props.selectedProjectId !== null}
        onEditRole={roleEditor.openRoleEditor}
      />

      <RoleCatalogLoadingState
        selectedProjectId={props.selectedProjectId}
        isProjectRoleLoading={projectRoleQuery.isLoading}
        hasProjectRoleData={projectRoleQuery.data !== undefined}
        isSystemRoleLoading={systemRoleQuery.isLoading}
        hasSystemRoleData={systemRoleQuery.data !== undefined}
      />

      <RoleEditorDrawer
        open={roleEditor.editingRole !== null}
        role={roleEditor.editingRole}
        systemRole={roleEditor.editingSystemRole}
        projectName={props.selectedProjectName}
        isSaving={updateRoleMutation.isPending}
        onClose={roleEditor.closeRoleEditor}
        onSave={roleEditor.saveRole}
      />
    </section>
  );
}
