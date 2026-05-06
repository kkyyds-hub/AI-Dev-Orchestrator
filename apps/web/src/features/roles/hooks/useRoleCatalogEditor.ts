import { useState } from "react";

import type {
  ProjectRoleConfig,
  ProjectRoleUpdateInput,
  SystemRoleCatalogItem,
} from "../types";

type UseRoleCatalogEditorInput = {
  projectRoles: ProjectRoleConfig[];
  systemRoles: SystemRoleCatalogItem[];
  onSaveRole: (roleCode: string, payload: ProjectRoleUpdateInput) => Promise<void>;
};

export function useRoleCatalogEditor(input: UseRoleCatalogEditorInput) {
  const [editingRoleCode, setEditingRoleCode] = useState<string | null>(null);

  const editingRole =
    input.projectRoles.find((role) => role.role_code === editingRoleCode) ?? null;
  const editingSystemRole =
    input.systemRoles.find((role) => role.code === editingRoleCode) ?? null;

  const openRoleEditor = (roleCode: string | null) => {
    setEditingRoleCode(roleCode);
  };

  const closeRoleEditor = () => {
    setEditingRoleCode(null);
  };

  const saveRole = async (payload: ProjectRoleUpdateInput) => {
    if (!editingRole) {
      throw new Error("?????????????");
    }

    await input.onSaveRole(editingRole.role_code, payload);
  };

  return {
    editingRole,
    editingSystemRole,
    closeRoleEditor,
    openRoleEditor,
    saveRole,
  };
}
