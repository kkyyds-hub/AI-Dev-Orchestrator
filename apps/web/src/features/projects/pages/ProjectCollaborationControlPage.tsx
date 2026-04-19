import { TeamControlCenterSection } from "../../agent-teams/sections/TeamControlCenterSection";
import { AgentThreadControlSection } from "../../agents/sections/AgentThreadControlSection";
import { CostDashboardSection } from "../../costs/sections/CostDashboardSection";

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
      className="space-y-6"
    >
      <AgentThreadControlSection
        projectId={props.selectedProjectId}
        projectName={props.selectedProjectName}
      />

      <TeamControlCenterSection
        projectId={props.selectedProjectId}
        projectName={props.selectedProjectName}
      />

      <CostDashboardSection
        projectId={props.selectedProjectId}
        projectName={props.selectedProjectName}
      />
    </section>
  );
}
