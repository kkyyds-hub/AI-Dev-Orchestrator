import { TeamControlCenterSection } from "../../agent-teams/sections/TeamControlCenterSection";
import { AgentThreadControlSection } from "../../agents/sections/AgentThreadControlSection";
import { CostDashboardSection } from "../../costs/sections/CostDashboardSection";
import { ProjectSubviewTabs } from "../components/ProjectSubviewTabs";

type ProjectCollaborationControlPageProps = {
  selectedProjectId: string | null;
  selectedProjectName: string | null;
};

export function ProjectCollaborationControlPage(
  props: ProjectCollaborationControlPageProps,
) {
  return (
    <section
      id="collaboration-control"
      data-testid="project-overview-view-collaboration-control"
      className="space-y-4"
    >
      <ProjectSubviewTabs
        ariaLabel="项目协作视图"
        defaultTabId="agent-thread"
        variant="inline"
        items={[
          {
            id: "agent-thread",
            label: "线程",
            panelId: "project-agent-thread-panel",
            content: (
              <AgentThreadControlSection
                projectId={props.selectedProjectId}
                projectName={props.selectedProjectName}
              />
            ),
          },
          {
            id: "team-control",
            label: "团队",
            panelId: "project-team-control-panel",
            content: (
              <TeamControlCenterSection
                projectId={props.selectedProjectId}
                projectName={props.selectedProjectName}
              />
            ),
          },
          {
            id: "costs",
            label: "成本",
            panelId: "project-cost-dashboard-panel",
            content: (
              <CostDashboardSection
                projectId={props.selectedProjectId}
                projectName={props.selectedProjectName}
              />
            ),
          },
        ]}
      />
    </section>
  );
}
