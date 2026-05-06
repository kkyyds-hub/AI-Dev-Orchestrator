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
    <section className="space-y-6 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
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

      <div className="grid gap-5 xl:grid-cols-[1.08fr_0.92fr]">
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
