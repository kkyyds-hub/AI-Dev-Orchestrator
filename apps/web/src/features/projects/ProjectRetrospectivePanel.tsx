import { useProjectApprovalRetrospective } from "../approvals/hooks";
import { ProjectRetrospectiveApprovalCycles } from "./components/ProjectRetrospectiveApprovalCycles";
import { ProjectRetrospectiveEmptyState } from "./components/ProjectRetrospectiveEmptyState";
import { ProjectRetrospectiveFailureClusters } from "./components/ProjectRetrospectiveFailureClusters";
import { ProjectRetrospectiveHeader } from "./components/ProjectRetrospectiveHeader";
import {
  ProjectRetrospectiveErrorState,
  ProjectRetrospectiveLoadingState,
} from "./components/ProjectRetrospectiveQueryState";
import { ProjectRetrospectiveRecentFailures } from "./components/ProjectRetrospectiveRecentFailures";
import { ProjectRetrospectiveSummaryGrid } from "./components/ProjectRetrospectiveSummaryGrid";

type ProjectRetrospectivePanelProps = {
  projectId: string | null;
  projectName: string | null;
  onNavigateToApproval?: (input: { projectId: string; approvalId: string }) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function ProjectRetrospectivePanel(props: ProjectRetrospectivePanelProps) {
  const retrospectiveQuery = useProjectApprovalRetrospective(props.projectId);

  if (!props.projectId) {
    return <ProjectRetrospectiveEmptyState />;
  }

  const projectId = props.projectId;
  const retrospective = retrospectiveQuery.data;

  return (
    <section
      id="project-retrospective"
      className="space-y-6 border-b border-[#333333] pb-7"
    >
      <ProjectRetrospectiveHeader
        projectName={props.projectName}
        summary={retrospective?.summary ?? null}
      />

      {retrospectiveQuery.isLoading && !retrospective ? (
        <ProjectRetrospectiveLoadingState />
      ) : retrospectiveQuery.isError ? (
        <ProjectRetrospectiveErrorState message={retrospectiveQuery.error.message} />
      ) : retrospective ? (
        <>
          <ProjectRetrospectiveSummaryGrid summary={retrospective.summary} />

          <ProjectRetrospectiveApprovalCycles
            projectId={projectId}
            generatedAt={retrospective.generated_at}
            approvalCycles={retrospective.approval_cycles}
            onNavigateToApproval={props.onNavigateToApproval}
          />

          <div className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
            <ProjectRetrospectiveFailureClusters
              failureClusters={retrospective.failure_clusters}
            />

            <ProjectRetrospectiveRecentFailures
              recentFailures={retrospective.recent_failures}
              onNavigateToTask={props.onNavigateToTask}
            />
          </div>
        </>
      ) : null}
    </section>
  );
}
