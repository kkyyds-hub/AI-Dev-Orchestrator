import { useEffect, useMemo, useState } from "react";

import { useUpdateProjectRoleSkillBindings } from "../hooks";
import type {
  ProjectRoleSkillBindingGroup,
  ProjectSkillBindingSnapshot,
  SkillRegistrySkill,
} from "../types";

export function useRoleSkillBindingEditor(
  projectId: string | null,
  bindingSnapshot: ProjectSkillBindingSnapshot | null,
  registrySkills: SkillRegistrySkill[],
) {
  const updateBindingMutation = useUpdateProjectRoleSkillBindings(projectId);
  const [editingRoleCode, setEditingRoleCode] = useState<string | null>(null);
  const [draftSkillCodes, setDraftSkillCodes] = useState<string[]>([]);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    setEditingRoleCode(null);
    setDraftSkillCodes([]);
    setLocalError(null);
  }, [projectId]);

  const applicableSkillMap = useMemo(() => {
    const nextMap = new Map<string, SkillRegistrySkill[]>();
    for (const role of bindingSnapshot?.roles ?? []) {
      nextMap.set(
        role.role_code,
        registrySkills.filter((skill) =>
          skill.applicable_role_codes.includes(role.role_code),
        ),
      );
    }

    return nextMap;
  }, [bindingSnapshot?.roles, registrySkills]);

  function editRole(role: ProjectRoleSkillBindingGroup) {
    setEditingRoleCode(role.role_code);
    setDraftSkillCodes(role.skills.map((skill) => skill.skill_code));
    setLocalError(null);
  }

  function toggleSkillCode(skillCode: string) {
    setDraftSkillCodes((currentCodes) =>
      currentCodes.includes(skillCode)
        ? currentCodes.filter((code) => code !== skillCode)
        : [...currentCodes, skillCode],
    );
  }

  function cancelEdit() {
    setEditingRoleCode(null);
    setDraftSkillCodes([]);
    setLocalError(null);
  }

  async function saveRoleBindings() {
    if (!editingRoleCode) {
      return;
    }

    setLocalError(null);
    try {
      await updateBindingMutation.mutateAsync({
        roleCode: editingRoleCode,
        payload: { skill_codes: draftSkillCodes },
      });
      setEditingRoleCode(null);
      setDraftSkillCodes([]);
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : "角色 Skill 绑定保存失败。",
      );
    }
  }

  return {
    applicableSkillMap,
    draftSkillCodes,
    editingRoleCode,
    isSaving: updateBindingMutation.isPending,
    localError,
    cancelEdit,
    editRole,
    saveRoleBindings,
    toggleSkillCode,
  };
}
