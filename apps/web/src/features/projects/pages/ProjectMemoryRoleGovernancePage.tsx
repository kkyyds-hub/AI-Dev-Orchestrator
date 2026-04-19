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
      <ProjectMemoryPanel
        projectId={props.selectedProjectId}
        projectName={props.selectedProjectName}
        onNavigateToApproval={props.onNavigateToApproval}
        onNavigateToDeliverable={props.onNavigateToDeliverable}
        onNavigateToTask={props.onNavigateToTask}
      />

      <MemoryGovernanceSection
        projectId={props.selectedProjectId}
        projectName={props.selectedProjectName}
      />

      <MemorySearchPanel
        projectId={props.selectedProjectId}
        projectName={props.selectedProjectName}
        onNavigateToApproval={props.onNavigateToApproval}
        onNavigateToDeliverable={props.onNavigateToDeliverable}
        onNavigateToTask={props.onNavigateToTask}
      />

      <RoleCatalogPage
        selectedProjectId={props.selectedProjectId}
        selectedProjectName={props.selectedProjectName}
      />

      <SkillRegistryPage
        selectedProjectId={props.selectedProjectId}
        selectedProjectName={props.selectedProjectName}
      />

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
    </section>
  );
}
