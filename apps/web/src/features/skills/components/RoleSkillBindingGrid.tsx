import type {
  ProjectRoleSkillBindingGroup,
  ProjectSkillBindingSnapshot,
  SkillRegistrySkill,
} from "../types";
import { RoleSkillBindingRoleCard } from "./RoleSkillBindingRoleCard";

type RoleSkillBindingGridProps = {
  applicableSkillMap: Map<string, SkillRegistrySkill[]>;
  bindingSnapshot: ProjectSkillBindingSnapshot | null;
  draftSkillCodes: string[];
  editingRoleCode: string | null;
  isSaving: boolean;
  onCancelEdit: () => void;
  onEditRole: (role: ProjectRoleSkillBindingGroup) => void;
  onSaveRoleBindings: () => void;
  onToggleSkillCode: (skillCode: string) => void;
};

export function RoleSkillBindingGrid(props: RoleSkillBindingGridProps) {
  if (!props.bindingSnapshot) {
    return null;
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {props.bindingSnapshot.roles.map((role) => (
        <RoleSkillBindingRoleCard
          key={role.role_code}
          applicableSkills={props.applicableSkillMap.get(role.role_code) ?? []}
          draftSkillCodes={props.draftSkillCodes}
          isEditing={props.editingRoleCode === role.role_code}
          isSaving={props.isSaving}
          role={role}
          onCancelEdit={props.onCancelEdit}
          onEditRole={props.onEditRole}
          onSaveRoleBindings={props.onSaveRoleBindings}
          onToggleSkillCode={props.onToggleSkillCode}
        />
      ))}
    </div>
  );
}
