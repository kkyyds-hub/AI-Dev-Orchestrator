import { MemoryGovernanceSection } from "../../memory-governance/sections/MemoryGovernanceSection";
import { RoleCatalogPage } from "../../roles/RoleCatalogPage";
import { RoleWorkbenchPage } from "../../roles/RoleWorkbenchPage";
import { SkillRegistryPage } from "../../skills/SkillRegistryPage";
import { MemorySearchPanel } from "../MemorySearchPanel";
import { ProjectMemoryPanel } from "../ProjectMemoryPanel";
import type { BossProjectItem } from "../types";

type ProjectMemoryRoleGovernancePageProps = {
  selectedProjectId: string | null;
  selectedProjectName: string | null;
  projects: BossProjectItem[];
  onSelectProject: (projectId: string) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToDeliverable: (input: { projectId: string; deliverableId: string }) => void;
  onNavigateToApproval: (input: { projectId: string; approvalId: string }) => void;
};

export function ProjectMemoryRoleGovernancePage(
  props: ProjectMemoryRoleGovernancePageProps,
) {
  return (
    <section
      id="memory-role-governance"
      data-testid="project-overview-view-memory-role-governance"
      className="space-y-6"
    >
      <div id="governance-memory-panel" className="scroll-mt-24">
        <ProjectMemoryPanel
          projectId={props.selectedProjectId}
          projectName={props.selectedProjectName}
          onNavigateToApproval={props.onNavigateToApproval}
          onNavigateToDeliverable={props.onNavigateToDeliverable}
          onNavigateToTask={props.onNavigateToTask}
        />
      </div>

      <MemoryGovernanceSection
        projectId={props.selectedProjectId}
        projectName={props.selectedProjectName}
      />

      <div id="governance-memory-search" className="scroll-mt-24">
        <MemorySearchPanel
          projectId={props.selectedProjectId}
          projectName={props.selectedProjectName}
          onNavigateToApproval={props.onNavigateToApproval}
          onNavigateToDeliverable={props.onNavigateToDeliverable}
          onNavigateToTask={props.onNavigateToTask}
        />
      </div>

      <div id="governance-roles" className="scroll-mt-24">
        <RoleCatalogPage
          selectedProjectId={props.selectedProjectId}
          selectedProjectName={props.selectedProjectName}
        />
      </div>

      <div id="governance-skills" className="scroll-mt-24">
        <SkillRegistryPage
          selectedProjectId={props.selectedProjectId}
          selectedProjectName={props.selectedProjectName}
        />
      </div>

      <div id="governance-role-workbench" className="scroll-mt-24">
        <RoleWorkbenchPage
          selectedProjectId={props.selectedProjectId}
          selectedProjectName={props.selectedProjectName}
          projectOptions={props.projects.map((project) => ({
            id: project.id,
            name: project.name,
            stage: project.stage,
            status: project.status,
          }))}
          onNavigateToProject={props.onSelectProject}
          onNavigateToTask={props.onNavigateToTask}
        />
      </div>
    </section>
  );
}
