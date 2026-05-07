import { useEffect, useMemo, useState } from "react";

import type { DeliverableSummary } from "../types";

type UseDeliverableSelectionInput = {
  deliverables: DeliverableSummary[];
  requestedDeliverableId?: string | null;
  onRequestedDeliverableHandled?: () => void;
};

export function useDeliverableSelection(input: UseDeliverableSelectionInput) {
  const [selectedDeliverableId, setSelectedDeliverableId] = useState<string | null>(null);

  useEffect(() => {
    if (!input.deliverables.length) {
      setSelectedDeliverableId(null);
      return;
    }

    const requestedStillExists = Boolean(
      input.requestedDeliverableId &&
        input.deliverables.some(
          (deliverable) => deliverable.id === input.requestedDeliverableId,
        ),
    );
    const selectedStillExists = input.deliverables.some(
      (deliverable) => deliverable.id === selectedDeliverableId,
    );

    if (requestedStillExists) {
      setSelectedDeliverableId(input.requestedDeliverableId ?? null);
      input.onRequestedDeliverableHandled?.();
      return;
    }

    if (!selectedDeliverableId || !selectedStillExists) {
      setSelectedDeliverableId(input.deliverables[0].id);
    }
  }, [
    input.deliverables,
    input.onRequestedDeliverableHandled,
    input.requestedDeliverableId,
    selectedDeliverableId,
  ]);

  const selectedDeliverable = useMemo<DeliverableSummary | null>(
    () =>
      input.deliverables.find((deliverable) => deliverable.id === selectedDeliverableId) ??
      null,
    [input.deliverables, selectedDeliverableId],
  );

  return {
    selectedDeliverable,
    selectedDeliverableId,
    setSelectedDeliverableId,
  };
}
