import { ProjectMemoryEmptyState } from "./components/ProjectMemoryEmptyState";
import { ProjectMemoryHeader } from "./components/ProjectMemoryHeader";
import { ProjectMemoryLatestList } from "./components/ProjectMemoryLatestList";
import { ProjectMemoryOverview } from "./components/ProjectMemoryOverview";
import {
  ProjectMemoryErrorState,
  ProjectMemoryLoadingState,
} from "./components/ProjectMemoryQueryState";
import { useProjectMemorySnapshot } from "./hooks";

type ProjectMemoryPanelProps = {
  projectId: string | null;
  projectName: string | null;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
  onNavigateToApproval?: (input: {
    projectId: string;
    approvalId: string;
  }) => void;
};

export function ProjectMemoryPanel(props: ProjectMemoryPanelProps) {
  const snapshotQuery = useProjectMemorySnapshot(props.projectId);

  if (!props.projectId) {
    return <ProjectMemoryEmptyState />;
  }

  const projectId = props.projectId;
  const snapshot = snapshotQuery.data;

  return (
    <section className="space-y-6 border-b border-[#333333] pb-7">
      <ProjectMemoryHeader
        projectName={props.projectName}
        totalMemories={snapshot?.total_memories ?? 0}
        onRefresh={() => void snapshotQuery.refetch()}
      />

      {snapshotQuery.isLoading && !snapshot ? (
        <ProjectMemoryLoadingState />
      ) : snapshotQuery.isError ? (
        <ProjectMemoryErrorState message={snapshotQuery.error.message} />
      ) : (
        <>
          <ProjectMemoryOverview
            generatedAt={snapshot?.generated_at ?? null}
            counts={snapshot?.counts ?? []}
          />

          <ProjectMemoryLatestList
            projectId={projectId}
            latestItems={snapshot?.latest_items ?? []}
            onNavigateToTask={props.onNavigateToTask}
            onNavigateToDeliverable={props.onNavigateToDeliverable}
            onNavigateToApproval={props.onNavigateToApproval}
          />
        </>
      )}
    </section>
  );
}
