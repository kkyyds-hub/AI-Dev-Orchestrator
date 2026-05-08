import { ChangeEvidencePanel } from "./ChangeEvidencePanel";
import { DeliverableDiffPanel } from "./DeliverableDiffPanel";
import { DeliverableVersionEmptyState } from "./components/DeliverableVersionEmptyState";
import { DeliverableVersionHeader } from "./components/DeliverableVersionHeader";
import { DeliverableVersionQueryState } from "./components/DeliverableVersionQueryState";
import { DeliverableVersionSnapshotSection } from "./components/DeliverableVersionSnapshotSection";
import type { DeliverableDetail, DeliverableSummary } from "./types";

type DeliverableVersionListProps = {
  deliverable: DeliverableSummary | null;
  detail: DeliverableDetail | null;
  isLoading: boolean;
  errorMessage: string | null;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function DeliverableVersionList(props: DeliverableVersionListProps) {
  if (!props.deliverable) {
    return <DeliverableVersionEmptyState />;
  }

  const deliverable = props.deliverable;
  const hasVersions = Boolean(props.detail && props.detail.versions.length > 0);
  const shouldShowQueryState =
    props.isLoading || props.errorMessage !== null || !hasVersions;

  return (
    <section className="space-y-5 border-b border-[#333333] pb-5">
      <DeliverableVersionHeader deliverable={deliverable} />

      {shouldShowQueryState || !props.detail ? (
        <DeliverableVersionQueryState
          isLoading={props.isLoading}
          errorMessage={props.errorMessage}
          hasVersions={hasVersions}
        />
      ) : (
        <>
          <DeliverableVersionSnapshotSection
            deliverableType={deliverable.type}
            versions={props.detail.versions}
            onNavigateToTask={props.onNavigateToTask}
          />

          <DeliverableDiffPanel
            deliverable={deliverable}
            detail={props.detail}
            onNavigateToTask={props.onNavigateToTask}
          />

          <ChangeEvidencePanel deliverableId={deliverable.id} />
        </>
      )}
    </section>
  );
}
