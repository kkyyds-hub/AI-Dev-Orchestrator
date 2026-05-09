import { ProjectRetrospectivePanel } from "../ProjectRetrospectivePanel";
import { ProjectSubviewTabs } from "../components/ProjectSubviewTabs";
import { ProjectTimelinePage } from "../ProjectTimelinePage";

type ProjectTimelineRetrospectivePageProps = {
  selectedProjectId: string | null;
  selectedProjectName: string | null;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToDeliverable: (input: { projectId: string; deliverableId: string }) => void;
  onNavigateToApproval: (input: { projectId: string; approvalId: string }) => void;
};

export function ProjectTimelineRetrospectivePage(
  props: ProjectTimelineRetrospectivePageProps,
) {
  return (
    <section
      id="timeline-retrospective"
      data-testid="project-overview-view-timeline-retrospective"
      className="space-y-4"
    >
      <ProjectSubviewTabs
        ariaLabel="Project timeline views"
        defaultTabId="timeline"
        variant="inline"
        items={[
          {
            id: "timeline",
            label: "Events",
            panelId: "project-timeline-panel",
            content: (
              <ProjectTimelinePage
                projectId={props.selectedProjectId}
                projectName={props.selectedProjectName}
                onNavigateToTask={props.onNavigateToTask}
                onNavigateToDeliverable={props.onNavigateToDeliverable}
                onNavigateToApproval={props.onNavigateToApproval}
              />
            ),
          },
          {
            id: "retrospective",
            label: "Retrospective",
            panelId: "project-retrospective-panel",
            content: (
              <ProjectRetrospectivePanel
                projectId={props.selectedProjectId}
                projectName={props.selectedProjectName}
                onNavigateToApproval={props.onNavigateToApproval}
                onNavigateToTask={props.onNavigateToTask}
              />
            ),
          },
        ]}
      />
    </section>
  );
}
