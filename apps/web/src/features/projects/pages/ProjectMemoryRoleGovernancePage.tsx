import { MemoryGovernanceSection } from "../../memory-governance/sections/MemoryGovernanceSection";
import { RoleCatalogPage } from "../../roles/RoleCatalogPage";
import { RoleWorkbenchPage } from "../../roles/RoleWorkbenchPage";
import { SkillRegistryPage } from "../../skills/SkillRegistryPage";
import { MemorySearchPanel } from "../MemorySearchPanel";
import { ProjectMemoryPanel } from "../ProjectMemoryPanel";
import { ProjectSubviewTabs } from "../components/ProjectSubviewTabs";
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
      className="space-y-4"
    >
      <ProjectSubviewTabs
        ariaLabel="项目记忆治理视图"
        defaultTabId="memory"
        items={[
          {
            id: "memory",
            label: "记忆",
            panelId: "governance-memory-panel",
            content: (
              <ProjectMemoryPanel
                projectId={props.selectedProjectId}
                projectName={props.selectedProjectName}
                onNavigateToApproval={props.onNavigateToApproval}
                onNavigateToDeliverable={props.onNavigateToDeliverable}
                onNavigateToTask={props.onNavigateToTask}
              />
            ),
          },
          {
            id: "governance",
            label: "治理",
            panelId: "governance-policy-panel",
            content: (
              <MemoryGovernanceSection
                projectId={props.selectedProjectId}
                projectName={props.selectedProjectName}
              />
            ),
          },
          {
            id: "search",
            label: "检索",
            panelId: "governance-memory-search",
            content: (
              <MemorySearchPanel
                projectId={props.selectedProjectId}
                projectName={props.selectedProjectName}
                onNavigateToApproval={props.onNavigateToApproval}
                onNavigateToDeliverable={props.onNavigateToDeliverable}
                onNavigateToTask={props.onNavigateToTask}
              />
            ),
          },
          {
            id: "roles",
            label: "角色",
            panelId: "governance-roles",
            content: (
              <RoleCatalogPage
                selectedProjectId={props.selectedProjectId}
                selectedProjectName={props.selectedProjectName}
              />
            ),
          },
          {
            id: "skills",
            label: "技能",
            panelId: "governance-skills",
            content: (
              <SkillRegistryPage
                selectedProjectId={props.selectedProjectId}
                selectedProjectName={props.selectedProjectName}
              />
            ),
          },
          {
            id: "workbench",
            label: "工作台",
            panelId: "governance-role-workbench",
            content: (
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
            ),
          },
        ]}
      />
    </section>
  );
}
