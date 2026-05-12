import { RoleSkillBindingEmptyState } from "./components/RoleSkillBindingEmptyState";
import { RoleSkillBindingGrid } from "./components/RoleSkillBindingGrid";
import { RoleSkillBindingHeader } from "./components/RoleSkillBindingHeader";
import { RoleSkillBindingQueryState } from "./components/RoleSkillBindingQueryState";
import { useProjectSkillBindings, useSkillRegistry } from "./hooks";
import { useRoleSkillBindingEditor } from "./hooks/useRoleSkillBindingEditor";

type RoleSkillBindingPanelProps = {
  projectId: string | null;
  projectName: string | null;
};

export function RoleSkillBindingPanel(props: RoleSkillBindingPanelProps) {
  const bindingQuery = useProjectSkillBindings(props.projectId);
  const registryQuery = useSkillRegistry();
  const bindingSnapshot = bindingQuery.data ?? null;
  const registrySkills = registryQuery.data?.skills ?? [];
  const editor = useRoleSkillBindingEditor(
    props.projectId,
    bindingSnapshot,
    registrySkills,
  );

  if (!props.projectId) {
    return <RoleSkillBindingEmptyState />;
  }

  return (
    <section className="space-y-5 border-b border-[#333333] pb-7">
      <RoleSkillBindingHeader
        bindingSnapshot={bindingSnapshot}
        projectName={props.projectName}
      />

      <RoleSkillBindingQueryState
        bindingError={bindingQuery.isError ? bindingQuery.error.message : null}
        isLoading={bindingQuery.isLoading && !bindingSnapshot}
        localError={editor.localError}
        registryError={registryQuery.isError ? registryQuery.error.message : null}
      />

      <RoleSkillBindingGrid
        applicableSkillMap={editor.applicableSkillMap}
        bindingSnapshot={bindingSnapshot}
        draftSkillCodes={editor.draftSkillCodes}
        editingRoleCode={editor.editingRoleCode}
        isSaving={editor.isSaving}
        onCancelEdit={editor.cancelEdit}
        onEditRole={editor.editRole}
        onSaveRoleBindings={editor.saveRoleBindings}
        onToggleSkillCode={editor.toggleSkillCode}
      />
    </section>
  );
}