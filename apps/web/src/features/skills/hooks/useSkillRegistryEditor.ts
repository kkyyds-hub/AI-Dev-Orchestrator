import { useEffect, useState } from "react";

import { useUpsertSkill } from "../hooks";
import type { SkillRegistrySkill, SkillUpsertInput } from "../types";
import {
  buildSkillDraft,
  EMPTY_SKILL_DRAFT,
  normalizeSkillCode,
  type SkillDraft,
} from "../components/skillRegistryDraft";

const NEW_SKILL_SENTINEL = "__new__";

export function useSkillRegistryEditor(skills: SkillRegistrySkill[]) {
  const upsertSkillMutation = useUpsertSkill();
  const [editingSkillCode, setEditingSkillCode] = useState<string | null>(null);
  const [draft, setDraft] = useState<SkillDraft>(EMPTY_SKILL_DRAFT);
  const [formError, setFormError] = useState<string | null>(null);

  const selectedSkill = skills.find((skill) => skill.code === editingSkillCode) ?? null;

  useEffect(() => {
    if (editingSkillCode !== null || skills.length === 0) {
      return;
    }

    setEditingSkillCode(skills[0].code);
    setDraft(buildSkillDraft(skills[0]));
  }, [editingSkillCode, skills]);

  function selectSkill(skill: SkillRegistrySkill) {
    setEditingSkillCode(skill.code);
    setDraft(buildSkillDraft(skill));
    setFormError(null);
  }

  function createSkill() {
    setEditingSkillCode(NEW_SKILL_SENTINEL);
    setDraft(EMPTY_SKILL_DRAFT);
    setFormError(null);
  }

  function updateDraft(patch: Partial<SkillDraft>) {
    setDraft((currentDraft) => ({
      ...currentDraft,
      ...patch,
    }));
  }

  function toggleRole(roleCode: string) {
    setDraft((currentDraft) => ({
      ...currentDraft,
      applicable_role_codes: currentDraft.applicable_role_codes.includes(roleCode)
        ? currentDraft.applicable_role_codes.filter((code) => code !== roleCode)
        : [...currentDraft.applicable_role_codes, roleCode],
    }));
  }

  async function saveSkill() {
    const normalizedCode = normalizeSkillCode(draft.code);
    if (!normalizedCode) {
      setFormError("请先填写 Skill code。建议使用英文小写和下划线。");
      return;
    }

    if (draft.applicable_role_codes.length === 0) {
      setFormError("请至少选择一个适用角色。");
      return;
    }

    setFormError(null);

    const payload: SkillUpsertInput = {
      name: draft.name,
      summary: draft.summary,
      purpose: draft.purpose,
      applicable_role_codes: draft.applicable_role_codes,
      enabled: draft.enabled,
      version: draft.version,
      change_note: draft.change_note.trim() || null,
    };

    try {
      const savedSkill = await upsertSkillMutation.mutateAsync({
        skillCode: normalizedCode,
        payload,
      });
      setEditingSkillCode(savedSkill.code);
      setDraft(buildSkillDraft(savedSkill));
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Skill 保存失败。");
    }
  }

  return {
    draft,
    formError,
    isSaving: upsertSkillMutation.isPending,
    selectedSkill,
    createSkill,
    saveSkill,
    selectSkill,
    toggleRole,
    updateDraft,
  };
}
