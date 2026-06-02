import { useMemo } from "react";

import { DeliverableCenterContent } from "./components/DeliverableCenterContent";
import { DeliverableCenterHeader } from "./components/DeliverableCenterHeader";
import { DeliverableCenterQueryState } from "./components/DeliverableCenterQueryState";
import { useDeliverableSelection } from "./hooks/useDeliverableSelection";
import { useDeliverableDetail, useProjectDeliverableSnapshot } from "./hooks";
import type { DeliverableSummary, DeliverableStatus } from "./types";

type DeliverableCenterPageProps = {
  projectId: string | null;
  projectName: string | null;
  requestedDeliverableId?: string | null;
  onRequestedDeliverableHandled?: () => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function DeliverableCenterPage(props: DeliverableCenterPageProps) {
  const snapshotQuery = useProjectDeliverableSnapshot(props.projectId);
  const snapshotDeliverables = snapshotQuery.data?.deliverables ?? [];
  const deliverables = useMemo(
    () => sortDeliverablesByHandlingPriority(snapshotDeliverables),
    [snapshotDeliverables],
  );
  const deliverableSelection = useDeliverableSelection({
    deliverables,
    requestedDeliverableId: props.requestedDeliverableId,
    onRequestedDeliverableHandled: props.onRequestedDeliverableHandled,
  });
  const detailQuery = useDeliverableDetail(
    deliverableSelection.selectedDeliverable?.id ?? null,
  );

  const shouldShowQueryState =
    !props.projectId ||
    (snapshotQuery.isLoading && !snapshotQuery.data) ||
    snapshotQuery.isError;

  return (
    <section
      id="deliverable-center"
      data-testid="deliverable-center-section"
      className="project-quiet-workspace scroll-mt-24 space-y-7"
    >
      <DeliverableCenterHeader
        projectName={props.projectName}
        totalDeliverables={snapshotQuery.data?.total_deliverables ?? 0}
        totalVersions={snapshotQuery.data?.total_versions ?? 0}
      />

      {shouldShowQueryState ? (
        <DeliverableCenterQueryState
          projectId={props.projectId}
          isLoading={snapshotQuery.isLoading}
          hasData={snapshotQuery.data !== undefined}
          errorMessage={snapshotQuery.isError ? snapshotQuery.error.message : null}
        />
      ) : (
        <DeliverableCenterContent
          deliverables={deliverables}
          generatedAt={snapshotQuery.data?.generated_at}
          selectedDeliverable={deliverableSelection.selectedDeliverable}
          selectedDeliverableId={deliverableSelection.selectedDeliverableId}
          detail={detailQuery.data ?? null}
          isDetailLoading={detailQuery.isLoading && !detailQuery.data}
          detailErrorMessage={
            detailQuery.isError ? detailQuery.error.message : null
          }
          onSelectDeliverable={deliverableSelection.setSelectedDeliverableId}
          onNavigateToTask={props.onNavigateToTask}
        />
      )}
    </section>
  );
}

const DELIVERABLE_HANDLING_PRIORITY: Record<DeliverableStatus, number> = {
  pending_review: 0,
  needs_rework: 1,
  draft: 2,
  approved: 3,
  archived: 4,
};

function sortDeliverablesByHandlingPriority(
  deliverables: DeliverableSummary[],
): DeliverableSummary[] {
  return [...deliverables].sort((a, b) => {
    const priorityDiff =
      DELIVERABLE_HANDLING_PRIORITY[a.status] -
      DELIVERABLE_HANDLING_PRIORITY[b.status];
    if (priorityDiff !== 0) {
      return priorityDiff;
    }

    const updatedDiff =
      Date.parse(b.updated_at || b.created_at) -
      Date.parse(a.updated_at || a.created_at);
    if (updatedDiff !== 0 && Number.isFinite(updatedDiff)) {
      return updatedDiff;
    }

    return a.title.localeCompare(b.title) || a.id.localeCompare(b.id);
  });
}
