import { RoleSkillBindingPanel } from "./RoleSkillBindingPanel";
import { SkillRegistryAlerts } from "./components/SkillRegistryAlerts";
import { SkillRegistryEditor } from "./components/SkillRegistryEditor";
import { SkillRegistryHeader } from "./components/SkillRegistryHeader";
import { SkillRegistryList } from "./components/SkillRegistryList";
import { SkillRegistryMetricGrid } from "./components/SkillRegistryMetricGrid";
import { useProjectSkillBindings, useSkillRegistry } from "./hooks";
import { useSkillRegistryEditor } from "./hooks/useSkillRegistryEditor";

type SkillRegistryPageProps = {
  selectedProjectId: string | null;
  selectedProjectName: string | null;
};

export function SkillRegistryPage(props: SkillRegistryPageProps) {
  const registryQuery = useSkillRegistry();
  const bindingQuery = useProjectSkillBindings(props.selectedProjectId);
  const registry = registryQuery.data ?? null;
  const skills = registry?.skills ?? [];
  const editor = useSkillRegistryEditor(skills);

  return (
    <section className="space-y-5 border-b border-[#333333] pb-6">
      <SkillRegistryHeader
        selectedProjectName={props.selectedProjectName}
        registry={registry}
      />

      <SkillRegistryMetricGrid
        registry={registry}
        bindingSnapshot={bindingQuery.data ?? null}
        selectedProjectName={props.selectedProjectName}
      />

      <SkillRegistryAlerts
        registryError={registryQuery.isError ? registryQuery.error.message : null}
        formError={editor.formError}
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
        <SkillRegistryList
          isLoading={registryQuery.isLoading}
          registryLoaded={Boolean(registry)}
          selectedSkillCode={editor.selectedSkill?.code ?? null}
          skills={skills}
          onCreateSkill={editor.createSkill}
          onSelectSkill={editor.selectSkill}
        />

        <SkillRegistryEditor
          draft={editor.draft}
          isSaving={editor.isSaving}
          selectedSkill={editor.selectedSkill}
          onCreateSkill={editor.createSkill}
          onSaveSkill={editor.saveSkill}
          onToggleRole={editor.toggleRole}
          onUpdateDraft={editor.updateDraft}
        />
      </div>

      <RoleSkillBindingPanel
        projectId={props.selectedProjectId}
        projectName={props.selectedProjectName}
      />
    </section>
  );
}
