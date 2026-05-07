import { DeliverableVersionList } from "../DeliverableVersionList";
import type { DeliverableDetail, DeliverableSummary } from "../types";
import { DeliverableListPanel } from "./DeliverableListPanel";

type DeliverableCenterContentProps = {
  deliverables: DeliverableSummary[];
  generatedAt?: string | null;
  selectedDeliverable: DeliverableSummary | null;
  selectedDeliverableId: string | null;
  detail: DeliverableDetail | null;
  isDetailLoading: boolean;
  detailErrorMessage: string | null;
  onSelectDeliverable: (deliverableId: string) => void;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
};

export function DeliverableCenterContent(props: DeliverableCenterContentProps) {
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1.4fr)]">
      <DeliverableListPanel
        deliverables={props.deliverables}
        generatedAt={props.generatedAt}
        selectedDeliverableId={props.selectedDeliverableId}
        onSelectDeliverable={props.onSelectDeliverable}
      />

      <DeliverableVersionList
        deliverable={props.selectedDeliverable}
        detail={props.detail}
        isLoading={props.isDetailLoading}
        errorMessage={props.detailErrorMessage}
        onNavigateToTask={props.onNavigateToTask}
      />
    </div>
  );
}
