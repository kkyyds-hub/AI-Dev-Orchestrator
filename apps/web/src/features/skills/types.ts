export type SkillVersionRecord = {
  id: string;
  skill_id: string;
  version: string;
  name: string;
  summary: string;
  purpose: string;
  applicable_role_codes: string[];
  enabled: boolean;
  change_note: string | null;
  created_at: string;
};

export type SkillRegistrySkill = {
  id: string;
  code: string;
  name: string;
  summary: string;
  purpose: string;
  applicable_role_codes: string[];
  enabled: boolean;
  current_version: string;
  created_at: string;
  updated_at: string;
  version_history: SkillVersionRecord[];
};

export type SkillRegistrySnapshot = {
  total_skill_count: number;
  enabled_skill_count: number;
  version_record_count: number;
  skills: SkillRegistrySkill[];
  generated_at: string;
};

export type SkillUpsertInput = {
  name: string;
  summary: string;
  purpose: string;
  applicable_role_codes: string[];
  enabled: boolean;
  version: string;
  change_note: string | null;
};

export type ProjectRoleBoundSkill = {
  skill_id: string;
  skill_code: string;
  skill_name: string;
  summary: string;
  purpose: string;
  bound_version: string;
  registry_current_version: string | null;
  registry_enabled: boolean;
  upgrade_available: boolean;
  applicable_role_codes: string[];
  binding_source: "default_seed" | "manual";
  created_at: string;
  updated_at: string;
};

export type ProjectRoleSkillBindingGroup = {
  role_code: string;
  role_name: string;
  role_enabled: boolean;
  default_skill_slots: string[];
  bound_skill_count: number;
  skills: ProjectRoleBoundSkill[];
};

export type ProjectSkillBindingSnapshot = {
  project_id: string;
  project_name: string;
  total_roles: number;
  enabled_roles: number;
  total_bound_skills: number;
  outdated_binding_count: number;
  roles: ProjectRoleSkillBindingGroup[];
  generated_at: string;
};

export type ProjectRoleSkillBindingUpdateInput = {
  skill_codes: string[];
};

export const SKILL_BINDING_SOURCE_LABELS: Record<string, string> = {
  default_seed: "默认映射",
  manual: "手动绑定",
};
