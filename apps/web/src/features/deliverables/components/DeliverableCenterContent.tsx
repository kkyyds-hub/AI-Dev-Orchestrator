import type { DeliverableDetail, DeliverableSummary } from "../types";
import { DeliverableListPanel } from "./DeliverableListPanel";
import { DeliverableSummaryPanel } from "./DeliverableSummaryPanel";

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
    <div className="grid gap-6 xl:grid-cols-[minmax(280px,0.85fr)_minmax(0,1.35fr)]">
      <DeliverableListPanel
        deliverables={props.deliverables}
        generatedAt={props.generatedAt}
        selectedDeliverableId={props.selectedDeliverableId}
        onSelectDeliverable={props.onSelectDeliverable}
      />

      <DeliverableSummaryPanel
        deliverable={props.selectedDeliverable}
        detail={props.detail}
        isLoading={props.isDetailLoading}
        errorMessage={props.detailErrorMessage}
        onNavigateToTask={props.onNavigateToTask}
      />
    </div>
  );
}
