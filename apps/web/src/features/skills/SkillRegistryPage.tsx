import { useState } from "react";

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

type SkillLocalView = "registry" | "bindings";

export function SkillRegistryPage(props: SkillRegistryPageProps) {
  const [activeView, setActiveView] = useState<SkillLocalView>("registry");
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

      <SkillLocalViewSwitch
        activeView={activeView}
        bindingCount={bindingQuery.data?.total_bound_skills ?? 0}
        roleCount={bindingQuery.data?.total_roles ?? 0}
        skillCount={registry?.total_skill_count ?? skills.length}
        onChange={setActiveView}
      />

      {activeView === "registry" ? (
        <section
          className="grid gap-5 xl:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]"
          aria-label="Skill 注册局部视图"
        >
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
        </section>
      ) : (
        <RoleSkillBindingPanel
          projectId={props.selectedProjectId}
          projectName={props.selectedProjectName}
        />
      )}
    </section>
  );
}

function SkillLocalViewSwitch(props: {
  activeView: SkillLocalView;
  bindingCount: number;
  roleCount: number;
  skillCount: number;
  onChange: (view: SkillLocalView) => void;
}) {
  const items: Array<{
    id: SkillLocalView;
    label: string;
    meta: string;
    description: string;
  }> = [
    {
      id: "registry",
      label: "Skill 注册",
      meta: `${props.skillCount} 个 Skill`,
      description: "维护能力条目、版本和适用角色。",
    },
    {
      id: "bindings",
      label: "角色绑定",
      meta: `${props.roleCount} 个角色 / ${props.bindingCount} 个绑定`,
      description: "把已注册 Skill 分配给当前项目角色。",
    },
  ];

  return (
    <nav
      aria-label="技能页局部子视图"
      className="grid gap-3 border-b border-[#333333] pb-4 md:grid-cols-2"
    >
      {items.map((item) => {
        const isActive = props.activeView === item.id;
        return (
          <button
            key={item.id}
            type="button"
            aria-current={isActive ? "page" : undefined}
            onClick={() => props.onChange(item.id)}
            className={`border-l px-3 py-2 text-left transition ${
              isActive
                ? "border-zinc-100 text-zinc-100"
                : "border-[#333333] text-zinc-500 hover:border-zinc-500 hover:text-zinc-200"
            }`}
          >
            <span className="block text-sm font-medium">{item.label}</span>
            <span className="mt-1 block text-xs text-zinc-600">{item.meta}</span>
            <span className="mt-2 block text-xs leading-5 text-zinc-500">
              {item.description}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
