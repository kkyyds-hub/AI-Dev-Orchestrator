import type { SkillRegistrySkill } from "../types";

export type SkillDraft = {
  code: string;
  name: string;
  summary: string;
  purpose: string;
  applicable_role_codes: string[];
  enabled: boolean;
  version: string;
  change_note: string;
};

export const EMPTY_SKILL_DRAFT: SkillDraft = {
  code: "",
  name: "",
  summary: "",
  purpose: "",
  applicable_role_codes: [],
  enabled: true,
  version: "1.0.0",
  change_note: "",
};

export function buildSkillDraft(skill: SkillRegistrySkill): SkillDraft {
  return {
    code: skill.code,
    name: skill.name,
    summary: skill.summary,
    purpose: skill.purpose,
    applicable_role_codes: [...skill.applicable_role_codes],
    enabled: skill.enabled,
    version: skill.current_version,
    change_note: "",
  };
}

export function normalizeSkillCode(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "_");
}
